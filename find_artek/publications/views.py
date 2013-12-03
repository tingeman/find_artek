import random
import string
import datetime as dt
import copy

from django.template import Context, loader
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.http import HttpResponse
from django import forms
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Q
from django.contrib import messages

import simplejson
import pdb
import re
import os.path

from olwidget.widgets import EditableLayer, InfoLayer, InfoMap

from find_artek.search import get_query
from find_artek.publications.models import Publication, Person, Feature,        \
                                            PubType, Keyword, Topic,            \
                                            FileObject, ImageObject,            \
                                            Authorship, Editorship, Supervisorship
from find_artek.publications.person_utils import get_person
from find_artek.publications.forms import AddReportForm,                        \
                                            UserAddReportForm,                  \
                                            AddPersonForm,         \
                                            AddPublicationsFromFileForm,        \
                                            AddFeatureMapForm,                  \
                                            AddFeatureCoordsForm,               \
                                            AddFeaturesFromFileForm
from find_artek.publications.utils import CyclicList, get_tag, remove_tags
from find_artek.publications.person_utils import parse_name_list
from find_artek.publications import import_from_file

from multiuploader.models import MultiuploaderImage

# for styling of features, see openlayers documentation at:
# http://docs.openlayers.org/library/feature_styling.html


#    messages.info(request, "Just testing...")
#    messages.warning(request, "Just testing...")
#    messages.error(request, "Just testing...")
#    messages.debug(request, "Finished testing...")





def get_olwidget_params(features):
    """Function takes a list of Feature entities, and returns:

    info:     a list of two-tuples, containing the feature and the formatting

    The info list is then passed to ol_widget to produce a map of features.

    """
    feature_colors = dict((
        ('PHOTO',             'red'),
        ('SAMPLE',            'green'),
        ('BOREHOLE',          'yellow'),
        ('GEOPHYSICAL DATA',  'blue'),
        ('FIELD MEASUREMENT', 'Purple'),
        ('LAB MEASUREMENT',   'pink'),
        ('RESOURCE',          'brown'),
        ('OTHER',             'white')))

    def info_append(info, g, f, html, gtype='point'):
        if gtype == 'point':
            info.append((g, {
                'html': html,
                'style': {
                    'fill_color': feature_colors[f.type],
                    'fill_opacity': 1,
                    'stroke_color': 'black',
                    'point_radius': 4,
                    'stroke_width': 1,
                },
            }))
        elif gtype == 'line':
            info.append((g, {
                'html': html,
                'style': {
                    'fill_color': feature_colors[f.type],
                    'stroke_color': feature_colors[f.type],
                    'stroke_width': 2,
                },
            }))
        elif gtype == 'poly':
            info.append((g, {
                'html': html,
                'style': {
                    'fill_color': feature_colors[f.type],
                    'fill_opacity': 0.3,
                    'stroke_color': 'black',
                    'stroke_width': 1,
                },
            }))


    def feature_popup_html(f):
        t = loader.get_template('publications/feature_popup.html')
        c = Context({
            'feature': f,
        })
        return t.render(c)

    info = []
    for i, f in enumerate(features):
        if f.points:
            info_append(info, f.points, f, feature_popup_html(f), gtype='point')
        if f.lines:
            info_append(info, f.lines, f, feature_popup_html(f), gtype='line')
        if f.polys:
            info_append(info, f.polys, f, feature_popup_html(f), gtype='poly')

    return info, feature_colors




class CaseInsensitively(object):
    """Wrap CaseInsensitively around an object to make comparisons
    case-insensitive.

    example:
    if CaseInsensitively('Hello world') in ['hello world', 'Hej Verden']:
        print "The if clause evaluates True!"

    """
    def __init__(self, s):
        self.__s = s.lower()

    def __hash__(self):
        return hash(self.__s)

    def __eq__(self, other):
        # ensure proper comparison between instances of this class
        try:
            other = other.__s
        except (TypeError, AttributeError):
            try:
                other = other.lower()
            except:
                pass
        return self.__s == other



def overview(request):
    feature_colors = dict((
        ('PHOTO',             'red'),
        ('SAMPLE',            'green'),
        ('BOREHOLE',          'yellow'),
        ('GEOPHYSICAL DATA',  'blue'),
        ('FIELD MEASUREMENT', 'Purple'),
        ('LAB MEASUREMENT',   'pink'),
        ('RESOURCE',          'brown'),
        ('OTHER',             'white')))

    def info_append(info, g, f, html, gtype='point'):
        if gtype == 'point':
            info.append((g, {
                'html': html,
                'style': {
                    'fill_color': feature_colors[f.type],
                    'fill_opacity': 1,
                    'stroke_color': 'black',
                    'point_radius': 4,
                    'stroke_width': 1,
                },
            }))
        elif gtype == 'line':
            info.append((g, {
                'html': html,
                'style': {
                    'fill_color': feature_colors[f.type],
                    'stroke_color': feature_colors[f.type],
                    'stroke_width': 3,
                },
            }))
        elif gtype == 'poly':
            info.append((g, {
                'html': html,
                'style': {
                    'fill_color': feature_colors[f.type],
                    'fill_opacity': 0.3,
                    'stroke_color': 'black',
                    'stroke_width': 1,
                },
            }))

    def feature_popup_html(f):
        t = loader.get_template('publications/feature_popup.html')
        c = Context({
            'feature': f,
        })
        return t.render(c)

    # default zoom:
    zl = 8
    clon = -52.5
    clat = 67

    #print request.GET
    features = Feature.objects.all()

    ftypes = Feature.feature_type_list()
    show_ftypes = copy.copy(ftypes)
    #print show_ftypes
    if request.GET:
        #print "This is a GET request"
        if ('ftype' in request.GET):
            show_ftypes = request.GET.getlist('ftype')

        # Get map coordinates and zoom level if present:
        zl = request.GET.get('zl' or zl)
        clon = request.GET.get('clon' or clon)
        clat = request.GET.get('clat' or clon)

    #print show_ftypes

    for ft in ftypes:
        if ft not in show_ftypes:
            #print "Excluding {0}".format(ft)
            features = features.exclude(type=ft)

    info = []
    for i, f in enumerate(features):
        if f.points:
            info_append(info, f.points, f, feature_popup_html(f), gtype='point')
        if f.lines:
            info_append(info, f.lines, f, feature_popup_html(f), gtype='line')
        if f.polys:
            info_append(info, f.polys, f, feature_popup_html(f), gtype='poly')

    options = {'layers': ['osm.mapnik', 'google.satellite'],
               'zoom_to_data_extent': False,
               'default_lon': clon,
               'default_lat': clat,
               'default_zoom': zl,
               'map_options': {
                   'controls': [
                                "LayerSwitcher",
                                "NavToolbar",
                                "PanZoom",
                                "Attribution",
#                                "MousePosition",
                                "ScaleLine"
                                ],
                   'projection': "EPSG:900913",
                   'display_projection': "EPSG:4326",
                   'max_extent': [-20037508.34, -20037508.34, 20037508.34, 20037508.34]
                },
               'popups_outside': True,
               }

    map_ = InfoMap(info, options)
    return render_to_response("publications/overview.html",
                              {"map": map_, "colors": feature_colors,
                              "feature_type_select": True,
                              "show_ftypes": show_ftypes},
                              context_instance=RequestContext(request))


def index(request):
    return HttpResponse("Hello, world. You're at the publication index.")


def publist(request):
    pub_list = Publication.objects.all()  # .order_by('-year').order_by('number')

    pub_list = pub_list.extra(select={'year_int': 'CAST(year AS INTEGER)'}).extra(order_by=['-year_int', '-number'])

    return render_to_response('publications/publist.html', {'pub_list': pub_list},
        context_instance=RequestContext(request))


def person_list(request):
    """Displays a list of all persons in database

    """
    person_list = Person.objects.all().extra(order_by=['last', 'first'])  # .order_by('-year').order_by('number')

    return render_to_response('publications/person_list.html', {'pers_list': person_list},
        context_instance=RequestContext(request))


def keyword_list(request):
    """Displays a list of all keywords in database

    """
    keyword_list = Keyword.objects.all().extra(order_by=['keyword'])  # .order_by('-year').order_by('number')

    return render_to_response('publications/keyword_list.html', {'keyword_list': keyword_list},
        context_instance=RequestContext(request))


def studreps(request):
    return HttpResponse("You're looking at student reports.")


def featlist(request):
    return HttpResponse("You're looking at all features")


def detail(request, pub_id):

    feature_colors = dict((
        ('PHOTO',             'red'),
        ('SAMPLE',            'green'),
        ('BOREHOLE',          'yellow'),
        ('GEOPHYSICAL DATA',  'blue'),
        ('FIELD MEASUREMENT', 'Purple'),
        ('LAB MEASUREMENT',   'pink'),
        ('RESOURCE',          'brown'),
        ('OTHER',             'white')))

    def info_append(info, g, f, html, gtype='point'):
        if gtype == 'point':
            info.append((g, {
                'html': html,
                'style': {
                    'fill_color': feature_colors[f.type],
                    'fill_opacity': 1,
                    'stroke_color': 'black',
                    'point_radius': 4,
                    'stroke_width': 1,
                },
            }))
        elif gtype == 'line':
            info.append((g, {
                'html': html,
                'style': {
                    'fill_color': feature_colors[f.type],
                    'stroke_color': feature_colors[f.type],
                    'stroke_width': 2,
                },
            }))
        elif gtype == 'poly':
            info.append((g, {
                'html': html,
                'style': {
                    'fill_color': feature_colors[f.type],
                    'fill_opacity': 0.3,
                    'stroke_color': 'black',
                    'stroke_width': 1,
                },
            }))


    def feature_popup_html(f):
        t = loader.get_template('publications/feature_popup.html')
        c = Context({
            'feature': f,
        })
        return t.render(c)

    p = get_object_or_404(Publication, pk=pub_id)
    features = p.feature_set.all()

    info = []
    for i, f in enumerate(features):
        if f.points:
            info_append(info, f.points, f, feature_popup_html(f), gtype='point')
        if f.lines:
            info_append(info, f.lines, f, feature_popup_html(f), gtype='line')
        if f.polys:
            info_append(info, f.polys, f, feature_popup_html(f), gtype='poly')

    options = {'layers': ['osm.mapnik','google.satellite'],
                'map_options': {
                    'controls': [
                                 "LayerSwitcher",
                                 "NavToolbar",
                                 "PanZoom",
                                 "Attribution"], },
                'popups_outside': True,
                'popup_direction': 'auto',
                'map_div_style': {'width': '600px', 'height': '360px'},
    }

    map_ = InfoMap(info, options)
    return render_to_response("publications/detail.html",
            {"pub": p,
             "map": map_,
             "colors": feature_colors},
            context_instance=RequestContext(request))


def person_detail(request, person_id):
    p = get_object_or_404(Person, pk=person_id)
    return render_to_response('publications/person_detail.html', {'person': p},
            context_instance=RequestContext(request))


def feature_detail(request, feature_id):
    f = get_object_or_404(Feature, pk=feature_id)
    return render_to_response('publications/feature_detail.html', {'feature': f},
            context_instance=RequestContext(request))


def frontpage(request):
    return render_to_response('publications/frontpage_3.html', {'None': None},
            context_instance=RequestContext(request))
    #return render_to_response('publications/frontpage.html', {'None': None},
    #        context_instance=RequestContext(request))


def search(request):
    query_string = ''
    topic_string = ''
    found_entries = None
    if ('q' in request.GET) and request.GET['q'].strip():
        query_string = request.GET['q']
        entry_query = get_query(query_string, ['title', 'abstract', 'keywords__keyword'])
        found_entries = Publication.objects.filter(entry_query)  # .order_by('number')
    elif ('topic' in request.GET) and request.GET['topic'].strip():
        query_string = request.GET['topic']
        entry_query = get_query(query_string, ['topics__topic', ])
        found_entries = Publication.objects.filter(entry_query)  # .order_by('number')
    elif ('keyword' in request.GET) and request.GET['keyword'].strip():
        query_string = request.GET['keyword']
        entry_query = get_query(query_string, ['keywords__keyword', ])
        found_entries = Publication.objects.filter(entry_query)  # .order_by('number')
    else:
        raise ValueError('Search key not recognized!')

    found_entries = found_entries.extra(select={'year_int': 'CAST(year AS INTEGER)'}).extra(order_by=['-year_int'])

    return render_to_response('publications/publist.html', {'pub_list': found_entries.distinct(), 'query': query_string, 'topic': topic_string},
                              context_instance=RequestContext(request))


def rand_generator(size=8, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


def generate_batch_tag(size=8):
    """Generates a unique tag consisting of the date, time and a unique number:
    e.g. "20130220_105216_" followed by a random number with n digits.
    """
    tag = str(dt.datetime.now())[:-7].replace(' ', '_').replace('-', '').replace(':', '')
    return tag + "_" + rand_generator(size)


@login_required(login_url='/accounts/login/')
def add_edit_report(request, pub_id=None):

    msg = []
    new_entity = True

    if pub_id:
        p = get_object_or_404(Publication, pk=pub_id)
        initial = None
        new_entity = False
        if not p.is_editable_by(request.user):
            error = "You do not have permissions to edit this publication!"
            return render_to_response('publications/access_denied.html',
                                      {'pub': p, 'error': error},
                                      context_instance=RequestContext(request))
    else:
        p = None
        initial = {'type': PubType.objects.get(type='STUDENTREPORT').id}
        if not request.user.has_perm("{0}.add_publication".format(Publication._meta.app_label)):
            error = "You do not have permissions to a add new publication!"
            return render_to_response('publications/access_denied.html',
                                      {'pub': p, 'error': error},
                                      context_instance=RequestContext(request))

    #pdb.set_trace()
    if request.user.is_superuser:
        form = AddReportForm(data=request.POST or initial, instance=p)
    else:
        form = UserAddReportForm(data=request.POST or initial, instance=p)

    # Temporary thing, while testing...
    #current_user = User.objects.get(username='thin')
    current_user = request.user

    # Some set up operations
    if request.POST:

        if form.is_valid():
            # some other operations and model save if any
            # redirect to results page

            r = form.save(commit=False)

            if not p:
                r.created_by = current_user

            r.modified_by = current_user
            r.save()

            if not p:
                messages.success(request, "Report '{0}' was created.".format(r.number))
            else:
                messages.success(request, "Report '{0}' was updated.".format(r.number))

            if ('authors' in request.POST) and request.POST['authors'].strip():
                # remove any existing author-relationships
                a_set = r.authorship_set.all()
                if a_set:
                    for a in a_set:
                        a.delete()

                # Parse author list!
                name_list = parse_name_list(request.POST['authors'])

                for id, n in enumerate(name_list):
                    n = n.strip()
                    pid = get_tag(n, 'id')

                    if pid == '0':
                        # tag [id:0]
                        # create new person
                        # ...
                        n = remove_tags(n)
                        if n:
                            p = Person(name=n)
                            p.created_by = current_user
                            p.modified_by = current_user
                            p.save()
                            messages.info(request, "Person '{0}' [id:{1}] created".format(p, p.id))

                            tmp = Authorship(person=p,
                                         publication=r,
                                         author_id=id)
                            tmp.save()
                    elif pid:
                        # tag [id:XX] where xx is supposed to be integer.
                        # get specified person and add to authorship
                        try:
                            p = Person.objects.get(id=pid)
                        except ObjectDoesNotExist:
                            if n:
                                # This is only an error, if n is not empty
                                messages.error(request, "Person with id:{0} does not exist in database".format(pid))
                            continue
                            #return HttpResponse('Person with id:{0} does not exist in database!'.format(pid))
                        #name_list[id] = 'DB: '+p.__unicode__()
                        tmp = Authorship(person=p,
                                         publication=r,
                                         author_id=id)
                        tmp.save()
                    else:
                        # No tag...

                        # Check if person exists   (exact or loose match)
                        # otherwise create person
                        messages.warning(request, "No person ID was specified for '{0}' and the person was not added as author. You can add manually later.".format(n))

                        #  msg.append([messages.WARNING,
                        #             "No person ID was specified for '{0}' and the person was not added as author. You can add manually later.".format(n)])


            if ('supervisors' in request.POST) and request.POST['supervisors'].strip():
                # remove any existing author-relationships
                s_set = r.supervisorship_set.all()
                if s_set:
                    for s in s_set:
                        s.delete()

                # Parse author list!
                name_list = parse_name_list(request.POST['supervisors'])

                for id, n in enumerate(name_list):
                    n = n.strip()
                    pid = get_tag(n, 'id')

                    if pid == '0':
                        # tag [id:0]
                        # create new person
                        # ...
                        n = remove_tags(n)
                        if n:
                            p = Person(name=n)
                            p.created_by = current_user
                            p.modified_by = current_user
                            p.save()
                            messages.info(request, "Person '{0}' [id:{1}] created".format(p, p.id))

                            tmp = Supervisorship(person=p,
                                         publication=r,
                                         supervisor_id=id)
                            tmp.save()
                    elif pid:
                        # tag [id:XX] where xx is supposed to be integer.
                        # get specified person and add to supervisorship
                        try:
                            p = Person.objects.get(id=pid)
                        except ObjectDoesNotExist:
                            if n:
                                # This is only an error, if n is not empty
                                messages.error(request, "Person with id:{0} does not exist in database".format(pid))
                            continue
                            #return HttpResponse('Person with id:{0} does not exist in database!'.format(pid))
                        #name_list[id] = 'DB: '+p.__unicode__()
                        tmp = Supervisorship(person=p,
                                         publication=r,
                                         supervisor_id=id)
                        tmp.save()
                    else:
                        # No tag...

                        # Check if person exists   (exact or loose match)
                        # otherwise create person
                        messages.warning(request, "No person ID was specified for '{0}' and the person was not added as supervisor. You can add manually later.".format(n))

                        #  msg.append([messages.WARNING,
                        #             "No person ID was specified for '{0}' and the person was not added as supervisor. You can add manually later.".format(n)])


            if ('keywords' in request.POST) and request.POST['keywords']:
                # Get list of keywords already attached
                # Iterate through posted keywords
                # Is keyword in existing list: continue
                # Is keyword in database? add to m2m relationship
                # Else add to database and add to m2m relationship.
                # remove any remaining model bound keywords that were not in post
                mkw = [k.keyword for k in r.keywords.all()]  # list of model bound keywords

                pkw = form.cleaned_data['keywords']  # posted keywords
                for k in pkw:
                    if CaseInsensitively(k) in mkw:
                        mkw.remove(CaseInsensitively(k))
                        continue

                    mk = Keyword.objects.filter(keyword__iexact=k)
                    if not mk:
                        mk = Keyword(keyword=k)
                        mk.save()
                        mk = [mk]

                    # add only the first keyword returned
                    r.keywords.add(mk[0])

                # Now remove any remaining keywords not posted
                if mkw:
                    for k in mkw:
                        r.keywords.remove(r.keywords.get(keyword=k))

                r.save()

            if ('topic' in request.POST) and request.POST['topic']:
                # Get list of topics already attached
                # Iterate through posted topics
                # Is topic in existing list: continue
                # Is topic in database? add to m2m relationship
                # Topics cannot be added if they do not exist... drop it
                # remove any remaining model bound topics that were not in post
                mtop = [t.topic for t in r.topics.all()]  # list of model bound topic

                ptop = form.cleaned_data['topic']  # posted topic
                for t in ptop:
                    if CaseInsensitively(t) in mtop:
                        mtop.remove(CaseInsensitively(t))
                        continue

                    mt = Topic.objects.filter(topic__iexact=t)
                    if not mt:
                        mt = Topic(topic=t)
                        mt.save()
                        mt = [mt]

                    # add only the first topic returned
                    r.topics.add(mt[0])

                # Now remove any remaining topic not posted
                if mtop:
                    for t in mtop:
                        r.topics.remove(r.topics.get(topic=t))

                r.save()

            if 'pdffile-clear' in request.POST and request.POST['pdffile-clear']:
                f = r.file
                fname = f.file.name
                f.file.delete(save=True)
                f.delete()
                r.file = None
                messages.info(request, "File deleted: {0}".format(fname))

            if 'pdffile' in request.FILES and request.FILES['pdffile']:
                if r.file:
                    # If a file is already bound, delete it and its associated FileObject
                    r.file.file.delete()
                    r.file.delete()

                pdffile = request.FILES['pdffile']
                f = FileObject()
                f.modified_by = current_user
                f.created_by = current_user
                f.description = "Uploaded report pdf-file"

                # Upload files to /reports/[year]/xxxx.pdf
                upload_dir = ['reports', '{0}'.format(r.year)]

                # Bypass normal 'upload_to' path generation by setting it directly
                f.upload_to = os.path.join(*upload_dir).replace(' ', '_')
                # All spaces are replaced by underscores...

                # Save to database to generate primary_key before adding file
                f.save()

                # New filename = xx-xx.yyy
                _u, fext = os.path.splitext(os.path.basename(pdffile.name))
                if not r.number:
                    fname = pdffile.name
                else:
                    fname = r.number + fext

                # Save the temp file to an actual file at the correct location
                f.file.save(fname, pdffile, save=True)

                # Add the file to the m2m field on the publication
                r.file = f
                r.save()

            if 'appendix_batch_tag' in request.POST:

                # THIS FUNCTIONALITY REMOVED FROM THE TEMPLATE!!!

                # batch_tag is used to identify uploads through the
                # multiuploader plugin. If it is present, check for any
                # uploaded files and add them to appendix-field.

                # Upload files to /reports/[year]/xxxx.pdf
                upload_dir = ['reports', '{0}'.format(r.year), '{0}'.format(r.number)]
                upload_dir = os.path.join(*upload_dir).replace(' ', '_')

                appendix_batch_tag = request.POST['appendix_batch_tag']
                afiles = MultiuploaderImage.objects.filter(batch_tag=appendix_batch_tag)
                for af in afiles:
                    f = FileObject()
                    f.modified_by = current_user
                    f.created_by = current_user
                    f.description = "Uploaded appendix file"

                    # Bypass normal 'upload_to' path generation by setting it directly
                    f.upload_to = upload_dir

                    # Save to database to generate primary_key before adding file
                    f.save()

                    f.file.save(af.image.name, af.image.file, save=True)

                    # Add the file to the m2m field on the publication
                    r.appendices.add(f)
                    r.save()

                    af.image.delete(save=True)
                    af.delete()

            return redirect('/pubs/detail/{0}/'.format(r.id))
        else:
            raise ValueError('Problem!')

    # Form was not yet posted...
#    for k in form.fields.keys():
#        if not p or request.user.is_superuser:
#            # Show these fields if we are registering a new report
#            show_fields =  ['type', 'title', 'number', 'authors', 'supervisors',
#                            'abstract', 'year', 'topic', 'keywords', 'pdffile',
#                            'comment']   # This should handle the proper Report type, get list from PubType table.
#        else:
#            # Show these fields if we are editing a report
#            show_fields =  ['type', 'title', 'authors', 'supervisors',
#                            'abstract', 'year', 'topic', 'keywords', 'pdffile',
#                            'comment']   # This should handle the proper Report type, get list from PubType table.
#        if k not in show_fields:
#            try:
#                form.exclude.append(k)
#            except:
#                form.exclude = []
#                form.exclude.append(k)
#            #del form.fields[k]
#            #pass
#        elif isinstance(form.fields[k].widget, forms.TextInput):
#            #print "TextInput: {0}".format(k)
#            #form.fields[k].widget.attrs['size'] = 90
#            pass
#        else:
#            #print "Field: {0}".format(k)
#            pass

    # generate unique tag for identifying uploaded appendix-files.
    # It is maybe useles to test uniquenss in this way, since the tags will
    # only exist in the database once files have been uploaded.
    # Since the tag includes time-stamp, the rare event where time-stamp and
    # random character tags have already been given to some other form-view,
    # it would not be caught, since the files have not yet been uploaded.

    # A better way would be to store generated tags in a separate table, and
    # query that table to see if newly generated tag already exist.
    # Tags MultiuploaderImages should be removed automatically after say 5 days.

    while 1:
        appendix_batch_tag = generate_batch_tag()
        if not MultiuploaderImage.objects.filter(batch_tag=appendix_batch_tag):
            break

    return render_to_response('publications/add_report.html',
            {'form': form, 'pub': p, 'appendix_batch_tag': appendix_batch_tag},
            context_instance=RequestContext(request))



#def upload_report_files(request, batch_tag, pub_id=None):
#    if pub_id:
#        p = get_object_or_404(Publication, pk=pub_id)
#    else:
#        p = None
#
#    return render_to_response('publications/upload_report_files.html',
#        {'pub': p, 'batch_tag': batch_tag}, context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def upload_report_files(request, pub_id=None, batch_tag=None):

    # Should fail, if we don't get a valid feature number
    p = get_object_or_404(Publication, pk=pub_id)

    current_user = request.user

    if not p.is_editable_by(request.user):
        error = "You do not have permissions to edit this publication!"
        return render_to_response('publications/access_denied.html',
                                  {'publication': p, 'error': error},
                                  context_instance=RequestContext(request))

    # Some set up operations
    if p and request.POST:
        if 'appendix_batch_tag' in request.POST:
            # batch_tag is used to identify uploads through the
            # multiuploader plugin. If it is present, check for any
            # uploaded files and add them to appendix-field.

            # Upload files to /reports/[year]/xxxx.pdf
            upload_dir = ['reports', '{0}'.format(p.year), '{0}'.format(p.number)]
            upload_dir = os.path.join(*upload_dir).replace(' ', '_')

            appendix_batch_tag = request.POST['appendix_batch_tag']
            afiles = MultiuploaderImage.objects.filter(batch_tag=appendix_batch_tag)
            for af in afiles:
                f = FileObject()
                f.modified_by = current_user
                f.created_by = current_user
                f.description = "Uploaded appendix file"

                # Bypass normal 'upload_to' path generation by setting it directly
                f.upload_to = upload_dir

                # Save to database to generate primary_key before adding file
                f.save()

                f.file.save(af.image.name, af.image.file, save=True)

                # Add the file to the m2m field on the publication
                p.appendices.add(f)
                p.save()

                af.image.delete(save=True)
                af.delete()

            return redirect('/pubs/report/{0}/'.format(p.id))


    # Form was not yet posted...

    # generate unique tag for identifying uploaded files.
    # It is maybe useles to test uniquenss in this way, since the tags will
    # only exist in the database once files have been uploaded.
    # Since the tag includes time-stamp, the rare event where time-stamp and
    # random character tags have already been given to some other form-view,
    # it would not be caught, since the files have not yet been uploaded.

    # A better way would be to store generated tags in a separate table, and
    # query that table to see if newly generated tag already exist.
    # Tags MultiuploaderImages should be removed automatically after say 5 days.

    while 1:
        batch_tag = generate_batch_tag()
        if not MultiuploaderImage.objects.filter(batch_tag=batch_tag):
            break


    return render_to_response('publications/upload_report_files.html',
        {'pub': p, 'batch_tag': batch_tag}, context_instance=RequestContext(request))









@login_required(login_url='/accounts/login/')
def upload_feature_files(request, feat_id=None, batch_tag=None):

    # Should fail, if we don't get a valid feature number
    f = get_object_or_404(Feature, pk=feat_id)

    current_user = request.user

    if not f.is_editable_by(request.user):
        error = "You do not have permissions to edit this feature!"
        return render_to_response('publications/access_denied.html',
                                  {'feature': f, 'error': error},
                                  context_instance=RequestContext(request))

    # Some set up operations
    if f and request.POST:
        if 'batch_tag' in request.POST:
            # batch_tag is used to identify uploads through the
            # multiuploader plugin. If it is present, check for any
            # uploaded files and add them to the files field of the feature.

            if f.date and f.date.year:
                # Upload files to /reports/[year]/features/[year]_[feat_id]/
                upload_dir = ['reports', '{0}'.format(f.date.year), 'features',
                          '{0}_{1}'.format(f.date.year, f.id)]
            else:
                # Upload files to /reports/[year]/features/[year]_[feat_id]/
                upload_dir = ['reports', 'features', '{0}'.format(f.id)]

            upload_dir = os.path.join(*upload_dir).replace(' ', '_')

            batch_tag = request.POST['batch_tag']

            ffiles = MultiuploaderImage.objects.filter(batch_tag=batch_tag)
            for ff in ffiles:
                fo = FileObject()
                fo.modified_by = current_user
                fo.created_by = current_user
                fo.description = "Uploaded feature file"

                # Bypass normal 'upload_to' path generation by setting it directly
                fo.upload_to = upload_dir

                # Save to database to generate primary_key before adding file
                fo.save()

                fo.file.save(ff.image.name, ff.image.file, save=True)

                # Add the file to the m2m field on the publication
                f.files.add(fo)
                f.save()

                ff.image.delete(save=True)
                ff.delete()

            return redirect('/pubs/feature/{0}/'.format(f.id))


    # Form was not yet posted...

    # generate unique tag for identifying uploaded files.
    # It is maybe useles to test uniquenss in this way, since the tags will
    # only exist in the database once files have been uploaded.
    # Since the tag includes time-stamp, the rare event where time-stamp and
    # random character tags have already been given to some other form-view,
    # it would not be caught, since the files have not yet been uploaded.

    # A better way would be to store generated tags in a separate table, and
    # query that table to see if newly generated tag already exist.
    # Tags MultiuploaderImages should be removed automatically after say 5 days.

    while 1:
        batch_tag = generate_batch_tag()
        if not MultiuploaderImage.objects.filter(batch_tag=batch_tag):
            break


    return render_to_response('publications/upload_feature_files.html',
        {'feature': f, 'batch_tag': batch_tag}, context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def upload_feature_images(request, feat_id=None, batch_tag=None):

    # Should fail, if we don't get a valid feature number
    f = get_object_or_404(Feature, pk=feat_id)

    current_user = request.user

    if not f.is_editable_by(request.user):
        error = "You do not have permissions to edit this feature!"
        return render_to_response('publications/access_denied.html',
                                  {'feature': f, 'error': error},
                                  context_instance=RequestContext(request))

    current_user = request.user

    # Some set up operations
    if f and request.POST:
        if 'batch_tag' in request.POST:
            # batch_tag is used to identify uploads through the
            # multiuploader plugin. If it is present, check for any
            # uploaded files and add them to the files field of the feature.

            if f.date and f.date.year:
                # Upload files to /reports/[year]/features/[year]_[feat_id]/
                upload_dir = ['reports', '{0}'.format(f.date.year), 'features',
                          '{0}_{1}'.format(f.date.year, f.id)]
            else:
                # Upload files to /reports/[year]/features/[year]_[feat_id]/
                upload_dir = ['reports', 'features', '{0}'.format(f.id)]

            upload_dir = os.path.join(*upload_dir).replace(' ', '_')

            batch_tag = request.POST['batch_tag']

            ffiles = MultiuploaderImage.objects.filter(batch_tag=batch_tag)
            for ff in ffiles:
                fo = ImageObject()
                fo.modified_by = current_user
                fo.created_by = current_user
                fo.caption = "Uploaded feature image"

                # Bypass normal 'upload_to' path generation by setting it directly
                fo.upload_to = upload_dir

                # Save to database to generate primary_key before adding file
                fo.save()

                fo.image.save(ff.image.name, ff.image.file, save=True)

                # Add the file to the m2m field on the publication
                f.images.add(fo)
                f.save()

                ff.image.delete(save=True)
                ff.delete()

            return redirect('/pubs/feature/{0}/'.format(f.id))


    # Form was not yet posted...

    # generate unique tag for identifying uploaded files.
    # It is maybe useles to test uniquenss in this way, since the tags will
    # only exist in the database once files have been uploaded.
    # Since the tag includes time-stamp, the rare event where time-stamp and
    # random character tags have already been given to some other form-view,
    # it would not be caught, since the files have not yet been uploaded.

    # A better way would be to store generated tags in a separate table, and
    # query that table to see if newly generated tag already exist.
    # Tags MultiuploaderImages should be removed automatically after say 5 days.

    while 1:
        batch_tag = generate_batch_tag()
        if not MultiuploaderImage.objects.filter(batch_tag=batch_tag):
            break


    return render_to_response('publications/upload_feature_images.html',
        {'feature': f, 'batch_tag': batch_tag}, context_instance=RequestContext(request))




































def person_ajax(request):
    return render_to_response('publications/ajax/person_ajax.html', {'None': None},
            context_instance=RequestContext(request))


def person_ajax_search(request):
    if ('term' in request.GET) and request.GET['term'].strip():
        query_string = request.GET['term']
        entry_query = get_query(query_string, ['first_relaxed', 'last_relaxed',
                                'first', 'middle', 'prelast', 'last', 'lineage',
                                'initials'])
        found_entries = Person.objects.filter(entry_query).order_by('first')

        json_entries = []
        for e in found_entries:
            if e.position == CaseInsensitively('student'):
                json_entries.append({'label': e.__unicode__() + ' [id:{0}], {1}'.format(e.id, e.id_number),
                                     'value': e.__unicode__() + ' [id:{0}]'.format(e.id)})
            else:
                label = e.__unicode__() + ' [id:{0}]'.format(e.id)
                if e.position:
                    label += ', {0}'.format(e.position)
                if e.department:
                    label += ', {0}'.format(e.department)
                if e.id_number:
                    label += ', {0}'.format(e.id_number)

                json_entries.append({'label': label,
                                     'value': e.__unicode__() + ' [id:{0}]'.format(e.id)})

#        my_array = [{'label': 'This is a Test', 'value': 'The test value inserted'},
#                    {'label': 'Second option', 'value': request.GET['term']+'_123'}]

#        return HttpResponse(simplejson.dumps(my_array))
        return HttpResponse(simplejson.dumps(json_entries))
    else:
        return HttpResponse('Nope')




def check_person_ajax(request):
    """This function is called from the add/edit report view in order to check
    the author list and provide a list of possible matches to choose from
    in case similar names exist in the database.

    html code will be returned for each of the fields "authors", "supervisors" and
    "editors" present in the ajax call, and html code will be returned for a
    dialog box for each of them, if necessary.
    """

    def process_field(request, name_field):
        """Code to check all names/id tags from specific field, e.g. "authors",
        "supervisors" or "editors", and provide back the html code needed to
        choose the right one or create new.

        This code will be called for each field present in the ajax call, and
        provide html code for a dialog box for each of them.

        """

        json_response = {}
        context = {'name_field': name_field,
                   'persons': []}

        for p in request.GET.getlist(name_field+'[]'):
            pid = get_tag(p, 'id')  # get the value of "[id:147]" tags, get_tag will return 147.
            if pid:
                # check that person with id exists in database
                # should not be included in choice-list
                # or should be included with an nice OK icon
                #print "Person with id {0} found in database.".format(pid)
                pass
            elif pid == 0:
                # handle case where [id:0]
                # should not be included in choice-list
                # or included with some other indication (also OK icon?)
                #print "Person should be created."
                pass
            else:
                # No id-tag, thus make choice
                # First get possible matches from database
                #print "No id found in name. Getting list of relaxed matches"
                dbp_list = get_person(p, exact=False)
                #pdb.set_trace()
                if dbp_list[1] == 'exact':
                    # Include exact match only
                    context['persons'].append({'name': p, 'p_exact': dbp_list[0], 'p_relaxed': []})
                elif dbp_list[1] == 'relaxed':
                    # Include list of relaxed matches.
                    context['persons'].append({'name': p, 'p_exact': [], 'p_relaxed': dbp_list[0]})

        try:
            if 'persons' in context and len(context['persons']) > 0:
                # If choices are to be made, render appropriate form.
                json_response['html'] = render_to_string(
                    'publications/ajax/choose_person_form.html',
                    {'data': context},
                    context_instance=RequestContext(request))
            else:
                # Otherwise return that all is ok.
                json_response['html'] = ''
                json_response['message'] = 'ok'
        except Exception, e:
            #print str(e)
            json_response['error'] = str(e)

        #print json_response
        return json_response


    if not request.is_ajax():
        # Make sure to only respond to ajax-requests!
        return HttpResponse(status=400)

    #pdb.set_trace()

    json_response = dict()

    if request.GET:
        #print request.GET
        context = {'persons': []}
        if ('authors[]' in request.GET):
            #print "processing authors"
            json_response['authors'] = process_field(request, 'authors')
        if ('supervisors[]' in request.GET):
            #print "processing supervisors"
            json_response['supervisors'] = process_field(request, 'supervisors')
        if ('editors[]' in request.GET):
            #print "processing editors"
            json_response['editors'] = process_field(request, 'editors')

        resp = simplejson.dumps(json_response)
        #print resp
        #print 'Json to be sent:  {0}'.format(resp)
        return HttpResponse(resp)
    else:
        # If POST request, or no persons included in request, return an error.
        json_response['error'] = 'No authors specified!'
        resp = simplejson.dumps(json_response)
        #print resp
        #print 'Json to be sent:  {0}'.format(resp)
        return HttpResponse(resp)



def ajax_list_reports(request):
    """This function is called from the overview map page to produce
    a list of reports that have features within the map view.

    """

    if not request.is_ajax():
        # Make sure to only respond to ajax-requests!
        return HttpResponse(status=400)

    #pdb.set_trace()

    json_response = dict()
    #print request.GET

    if request.GET:
        if ('wkt' in request.GET) and request.GET['wkt']:
            viewportWKT = request.GET['wkt']

        if ('srid' in request.GET) and request.GET['srid']:
            srid = request.GET['srid']
            if not srid.startswith('EPSG:'):
                if 'error' in json_response and json_response['error']:
                    json_response['error'] += '\n'
                else:
                    json_response['error'] = ''
                json_response['error'] += 'Unknown srid format: {0}'.format(srid)
                srid = None
            else:
                srid = int(srid[5:])

        viewport = GEOSGeometry(viewportWKT, srid=srid)

        Q_points = Q(points__bboverlaps=viewport)
        Q_lines = Q(lines__bboverlaps=viewport)
        Q_polys = Q(polys__bboverlaps=viewport)

        f_set = Feature.objects.filter(Q_points | Q_lines | Q_polys)
        p_set = Publication.objects.filter(feature__in=f_set).distinct()

        json_response['html'] = render_to_string(
                'publications/snippets/report_list.html',
                {'pub_list': p_set},
                context_instance=RequestContext(request))

#        if 'error' in json_response and json_response['error']:
#            json_response['error'] += '\n'
#        else:
#            json_response['error'] = ''
#        json_response['error'] += 'Number of features: {0}'.format(len(p_set))

#        json_response['error'] = ""
#        if ('wkt' in request.GET) and request.GET['wkt']:
#            json_response['error'] += 'wkt: ' + request.GET['wkt'] + '\n'
#        else:
#            json_response['error'] += 'wkt: EMPTY!!\n'
#        if ('srid' in request.GET) and request.GET['srid']:
#            json_response['error'] += 'srid: ' + request.GET['srid']
#        else:
#            json_response['error'] += 'srid: EMPTY!!\n'

#            try:
#                if context['persons']:
#                    json_response['html'] = render_to_string('publications/ajax/choose_person_form.html', {'data': context})
#                else:
#                    json_response['html'] = ''
#                    json_response['message'] = 'ok'
#            except Exception, e:
#                print str(e)

        return HttpResponse(simplejson.dumps(json_response))
    else:
        json_response['error'] = 'Not a valid GET request!'
        return HttpResponse(simplejson.dumps(json_response))


def ajax_keyword_search(request):
    if ('term' in request.GET) and request.GET['term'].strip():
        query_string = request.GET['term']
        entry_query = get_query(query_string, ['keyword'])
        found_entries = Keyword.objects.filter(entry_query).order_by('keyword')

        json_entries = []
        for e in found_entries:
            json_entries.append({'label': e.__unicode__(),
                                 'value': e.__unicode__()})

        return HttpResponse(simplejson.dumps(json_entries))
    else:
        return HttpResponse('Nope')


def ajax_topic_search(request):
    if ('term' in request.GET) and request.GET['term'].strip():
        query_string = request.GET['term']
        entry_query = get_query(query_string, ['topic'])
        found_entries = Topic.objects.filter(entry_query).order_by('topic')

        json_entries = []
        for e in found_entries:
            json_entries.append({'label': e.__unicode__(),
                                 'value': e.__unicode__()})

        return HttpResponse(simplejson.dumps(json_entries))
    else:
        return HttpResponse('Nope')


def add_person_ajax_test(request):
    form = AddPersonForm()
    return render_to_response('publications/ajax/person_form.html', {'form': form},
            context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def add_person_ajax(request):
    form = AddPersonForm(request.POST or None)
    json_response = dict()

    if request.POST:
        if form.is_valid():
            json_response['success'] = 'The form validated, person would have been created!'

        else:
            json_response['error'] = 'The form didn''t validate... there must have been an error!'
    else:
        json_response['error'] = 'Apparently no valid form data in request!?'

    return HttpResponse(simplejson.dumps(json_response), mimetype="application/json")


def multi_uploader_image_view(request, pub_id):
    items = MultiuploaderImage.objects.all()
    return render_to_response('publications/test/multi_uploader_images.html',
                              {'items': items},
                              context_instance=RequestContext(request))


def add_menu(request):
    return render_to_response('publications/add_menu_2.html', {'None': None},
                              context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def add_pubs_from_file(request):

    if not request.user.has_perm("{0}.add_publication".format(Publication._meta.app_label)):
        error = "You do not have permissions to add new publication!"
        return render_to_response('publications/access_denied.html',
                                  {'pub': None, 'error': error},
                                  context_instance=RequestContext(request))

    if request.method == 'POST':
        form = AddPublicationsFromFileForm(request.POST, request.FILES)
        if form.is_valid():
            if ('type' in request.POST):
                fpath = os.path.join('tmp', request.FILES['file'].name)
                filepath = default_storage.save(fpath, ContentFile(request.FILES['file'].read()))
                try:
                    if request.POST['type'] == 'bib':
                        #import_bibtex(request.FILES['file'])
                        response = 'Bibtex upload not implemented yet!'
                        pass
                    elif request.POST['type'] == 'xlsx':
                        import_from_file.xlsx_pubs(filepath, user=request.user)
                        response = 'success'
                    elif request.POST['type'] == 'csv':
                        #import_bibtex(request.FILES['file'])
                        response = 'csv upload not implemented yet!'
                        pass
                    else:
                        response = 'Unknown publication type!'
                finally:
                    default_storage.delete(filepath)

                return HttpResponse(response)

    else:
        form = AddPublicationsFromFileForm()
    return render_to_response('publications/add_pubs_from_file.html',
                              {'form': form},
                              context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def add_features_from_file(request, pub_id=None):

    if pub_id:
        pub_id = int(pub_id)  # Converted to integer for the purpose of comparison later.
        p = get_object_or_404(Publication, pk=pub_id)
        initial = None
        new_entity = False
        if not p.is_editable_by(request.user):
            error = "You do not have permissions to edit this publication!"
            return render_to_response('publications/access_denied.html',
                                      {'pub': p, 'error': error},
                                      context_instance=RequestContext(request))
        next_on_validate = "/pubs/report/{0}/".format(pub_id)
        next_on_cancel = "/pubs/report/{0}/add/features/from_file/".format(pub_id)
    else:
        p = None
        next_on_validate = "/pubs/frontpage/"
        next_on_cancel = "/pubs/add/features_from_file/".format(pub_id)

    fdict = {}
    msg = None
    features_added = []


    if request.method == 'POST':
        form = AddFeaturesFromFileForm(request.POST, request.FILES)
        if form.is_valid():
            if ('type' in request.POST):
                fpath = os.path.join('tmp', request.FILES['file'].name)
                filepath = default_storage.save(fpath, ContentFile(request.FILES['file'].read()))
                try:
                    if request.POST['type'] == 'bib':
                        #import_bibtex(request.FILES['file'])
                        response = 'Bibtex upload not implemented yet!'
                        pass
                    elif request.POST['type'] == 'xlsx':
                        fdict, file_messages = import_from_file.xlsx_features(filepath)

                    elif request.POST['type'] == 'csv':
                        #import_bibtex(request.FILES['file'])
                        response = 'csv upload not implemented yet!'
                        pass
                    else:
                        response = 'Unknown feature file type!'
                finally:
                    default_storage.delete(filepath)


            #messages.info(request, 'Parsed the file ok')

            # Process general file level messages.
            for level, msg in file_messages:
                messages.add_message(request, level, msg)

            for fnum, feat in iter(sorted(fdict.iteritems())):

                for level, msg in feat['messages']:
                    messages.add_message(request, level, msg)

                #messages.info(request, 'Parsing errors written!')

                if not feat['skip']:

                    if not pub_id and not feat['pub_id']:
                        msg = "No Publication ID specified for feature# {0} "+ \
                              "({1}). This feature is skipped!"
                        msg = msg.format(fnum, feat['data']['name'])
                        messages.error(request, msg)
                        continue

                    if feat['pub_id'] and pub_id and feat['pub_id'] != pub_id:
                        msg = "Publication ID mismatch. The uploaded file specifies that feature# {0} "+ \
                        "({1}) should be attached to publication {2}, while you are trying to attach it to "+ \
                        "publication {3}. This feature is skipped!"
                        msg = msg.format(fnum, feat['data']['name'],
                                         feat['pub_id'], pub_id )
                        messages.error(request, msg)
                        continue

                    try:
                        geom = GEOSGeometry(simplejson.dumps(feat['GeoJSON']),
                                            srid=fdict[fnum]['srid'])
                    except:
                        msg = "The coordinate(s) and srid(s) of feature# {0} "+ \
                              "({1}) do not evaluate to a valid geographical "+ \
                              "entity. This feature is skipped!"
                        msg = msg.format(fnum, feat['data']['name'])
                        messages.error(request, msg)
                        continue

                    # Create feature
                    feat['data']['created_by'] = request.user
                    feat['data']['modified_by'] = request.user
                    f = Feature(**feat['data'])

                    if feat['GeoJSON']['type'] in ['Point', 'MultiPoint']:
                        f.points = geom
                    elif feat['GeoJSON']['type'] in ['LineString', 'MultiLineString']:
                        f.lines = geom
                    elif feat['GeoJSON']['type'] in ['Polygon', 'MultiPolygon']:
                        f.polys = geom
                    else:
                        messages.error(request,
                            "Feature# {0} ({1}): Feature type '{2}' unknown. This feature is skipped!".format(f.name, fnum, feat['GeoJSON']['type']))
                        continue

                    f.save()
                    features_added.append(f.id)
                    msg = "Feature# {0} ({1}) created".format(fnum, f.name)

                    p = get_object_or_404(Publication, pk=pub_id or feat['pub_id'])
                    # If pub_id evaluates False (is None),  use feat information instead

                    if not p in f.publications.all():
                        # Add the publication to the feature m2m relationship
                        f.publications.add(p)
                        msg += ", and added to publication {0}".format(p.id)

                    messages.info(request, msg)
                    f.save()


            if features_added:
                messages.success(request,
                        "{0} features added from file {1}!".format(len(features_added), os.path.basename(filepath)))
                messages.warning(request,
                        "Please check the locations of added features!")
            else:
                messages.error(request,
                        "No features added from file {0}!".format(os.path.basename(filepath)))
                return redirect(next_on_cancel)


            # Prepare map to show on validation page

            # Show all available feature types in the map
            show_ftypes = Feature.feature_type_list()

            features = Feature.objects.filter(id__in=features_added)
            info, feature_colors = get_olwidget_params(features)

            options = {'layers': ['osm.mapnik','google.satellite'],
                        'map_options': {
                            'controls': [
                                         "LayerSwitcher",
                                         "NavToolbar",
                                         "PanZoom",
                                         "Attribution"], },
                        'popups_outside': True,
                        'map_div_style': {'width': '600px', 'height': '360px'},
            }



            map_ = InfoMap(info, options)
            return render_to_response("publications/validate_features_from_file.html",
                                      {"map": map_, "colors": feature_colors,
                                      "feature_type_select": False,      # type select is not implemented in this template
                                      "show_ftypes": show_ftypes,
                                      "features": features,
                                      'hide_language_choices': True,
                                      'next_on_validate': next_on_validate,
                                      'next_on_cancel': next_on_cancel},
                                      context_instance=RequestContext(request))

    else:
        form = AddFeaturesFromFileForm()

    return render_to_response('publications/add_features_from_file.html',
                              {'form': form, 'pub_id': pub_id, 'pub': p},
                              context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def validate_features_from_file(request):

    if request.method == 'POST':
        if 'features-pk' in request.POST:
            features = request.POST['features-pk'].strip(',').split(',')
            features = Feature.objects.filter(id__in=features)
            #print features
        else:
            features = []

        if 'cancel' in request.POST:
            for f in features:
                msg = "Feature id {0} ({1}) deleted!".format(f.id, f.name)
                f.delete()
                messages.info(request, msg)
            return redirect(request.POST['next_on_cancel'])

        else:
            msg = "{0} features validated.".format(len(features))
            messages.success(request, msg)
            return redirect(request.POST['next_on_validate'])





def test_keyword_tag(request):
    return render_to_response('publications/test/test_keyword.html',
                              {'None': None},
                              context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def verify_report(request, pub_id):

    if pub_id:
        p = get_object_or_404(Publication, pk=pub_id)
    else:
        return redirect('/pubs/publist/')

    if not p.is_verifiable_by(request.user):
        error = "You do not have permissions to verify this report!"
        return render_to_response('publications/access_denied.html',
                                  {'pub': p, 'error': error},
                                  context_instance=RequestContext(request))

    p.verified = True
    p.save()
    messages.success(request, "Report ({0}) '{1}' was verified.".format(p.id, p.number))
    return redirect('/pubs/detail/{0}'.format(pub_id))


@login_required(login_url='/accounts/login/')
def add_edit_feature_wcoords(request, pub_id=None, feat_id=None):
    """View to add or edit a feature using coordinate input

    View can be requested in the following ways:
    1) To create a new feature, not bound to a publication
    2) To create a new feature, bound to one specific publication
    3) To edit an existing feature, not bound to a publication
    4) To edit an existing feature, bound to one or more publications

    For these cases:
    1) pub_id = None,   feat_id = None
    2) pub_id = X,      feat_id = None
    3) pub_id = None,   feat_id = Y
    4) pub_id = None,   feat_id = Y

    Thus:
    feat_id = None   -->    This is a new feature, create
    feat_id = Y      -->    This is an existing feature, edit

    """

    pub_list = []
    f = None
    p = None
    new_feature = True

    # Get feature if id passed
    if feat_id:
        # This is an existing, feature, edit it!
        f = get_object_or_404(Feature, pk=feat_id)
        pub_list = f.publications.all()

        # If we have only one publication associated, make sure this publication
        # is represented in variable "p", otherwise leave "p" empty.
        if len(pub_list) == 1:
            p = pub_list[0]

        new_feature = False

        if not f.is_editable_by(request.user):
            error = "You do not have permissions to edit this feature!"
            return render_to_response('publications/access_denied.html',
                                      {'feature': f, 'error': error},
                                      context_instance=RequestContext(request))

    else:
        # This is a new feature...

        # check permission to add feature
        if not request.user.has_perm("{0}.add_feature".format(Feature._meta.app_label)):
            error = "You do not have permissions to add new feature!"
            return render_to_response('publications/access_denied.html',
                                      {'feature': f, 'error': error},
                                      context_instance=RequestContext(request))

        # Get publication if id passed
        if pub_id:
            p = get_object_or_404(Publication, pk=pub_id)
        else:
            p = None

    # Some set up operations
    if request.POST:
        # The form was posted, bind to posted data
        form = AddFeatureCoordsForm(data=request.POST, instance=f)
        if form.is_valid():
            # all form fields validated, process the form
            f = form.save(commit=False)

            if new_feature:
                f.created_by = request.user
            f.modified_by = request.user
            f.save()

            if 'publication-pk' in request.POST and request.POST['publication-pk']:
                # Here we assign again to p...
                # That is not a problem, since if the form was posted, the
                # pub_id was not passed through the url. (see the template form action)
                p = get_object_or_404(Publication, pk=request.POST['publication-pk'])
                if not p in f.publications.all():
                    # Add the publication to the feature m2m relationship
                    f.publications.add(p)
            else:
                messages.warning(request, "Feature added/updated but not linked to a report")
            f.save()

            if ('easting' in request.POST and request.POST['easting']) and      \
                ('northing' in request.POST and request.POST['northing']) and   \
                ('spatial_reference_system' in request.POST and                 \
                    request.POST['spatial_reference_system']):

                # All information is here, create the point
                x, y = (request.POST['easting'], request.POST['northing'])
                fWKT = "MULTIPOINT({0} {1})".format(x, y)
                srid = int(request.POST['spatial_reference_system'])
                geom = GEOSGeometry(fWKT, srid=srid)
                f.points = geom
                f.save()

            if new_feature:
                messages.success(request, "Feature added [id:{0}]".format(f.id))
            else:
                messages.success(request, "Feature updated [id:{0}]".format(f.id))

            messages.warning(request, "Please check the geographical location of the added feature!")

            if p:
                return redirect('/pubs/report/{0}/'.format(p.id))
            else:
                return redirect('/pubs/feature/{0}/'.format(f.id))

    else:  # this is a get request
        form = AddFeatureCoordsForm(instance=f)

    return render_to_response('publications/add_feature_wcoords.html',
                              {'form': form, 'pub': p, 'pub_list': pub_list,
                              'new_feature': new_feature},
                              context_instance=RequestContext(request))



@login_required(login_url='/accounts/login/')
def add_feature_choice(request, pub_id=None, feat_id=None):

    f = None
    p = None
    new_feature = True

    # Get feature if id passed
    if feat_id:
        # This is an existing, feature, edit it!
        f = get_object_or_404(Feature, pk=feat_id)
        new_feature = False

        if not f.is_editable_by(request.user):
            error = "You do not have permissions to edit this feature!"
            return render_to_response('publications/access_denied.html',
                                      {'feature': f, 'error': error},
                                      context_instance=RequestContext(request))

    else:
        # This is a new feature...

        # check permission to add feature
        if not request.user.has_perm("{0}.add_feature".format(Feature._meta.app_label)):
            error = "You do not have permissions to add new feature!"
            return render_to_response('publications/access_denied.html',
                                      {'feature': f, 'error': error},
                                      context_instance=RequestContext(request))

        # Get publication if id passed
        if pub_id:
            p = get_object_or_404(Publication, pk=pub_id)
        else:
            p = None

    return render_to_response('publications/add_feature_choice.html',
                              {'pub': p, "feat": f},
                              context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def add_edit_feature(request, pub_id=None, feat_id=None):
    """View to add or edit a feature.

    View can be requested in the following ways:
    1) To create a new feature, not bound to a publication
    2) To create a new feature, bound to one specific publication
    3) To edit an existing feature, not bound to a publication
    4) To edit an existing feature, bound to one or more publications

    For these cases:
    1) pub_id = None,   feat_id = None
    2) pub_id = X,      feat_id = None
    3) pub_id = None,   feat_id = Y
    4) pub_id = None,   feat_id = Y

    Thus:
    feat_id = None   -->    This is a new feature, create
    feat_id = Y      -->    This is an existing feature, edit

    """

    pub_list = []
    f = None
    p = None
    new_feature = True

    # Get feature if id passed
    if feat_id:
        # This is an existing, feature, edit it!
        f = get_object_or_404(Feature, pk=feat_id)

        pub_list = f.publications.all()

        # If we have only one publication associated, make sure this publication
        # is represented in variable "p", otherwise leave "p" empty.
        if len(pub_list) == 1:
            p = pub_list[0]

        new_feature = False

        if not f.is_editable_by(request.user):
            error = "You do not have permissions to edit this feature!"
            return render_to_response('publications/access_denied.html',
                                      {'feature': f, 'error': error},
                                      context_instance=RequestContext(request))

    else:
        # This is a new feature...

        # check permission to add feature
        if not request.user.has_perm("{0}.add_feature".format(Feature._meta.app_label)):
            error = "You do not have permissions to add new feature!"
            return render_to_response('publications/access_denied.html',
                                      {'feature': f, 'error': error},
                                      context_instance=RequestContext(request))

        # Get publication if id passed
        if pub_id:
            p = get_object_or_404(Publication, pk=pub_id)
        else:
            p = None

    # Some set up operations
    if request.POST:
        # The form was posted, bind to posted data
        form = AddFeatureMapForm(data=request.POST, instance=f)
        if form.is_valid():
            # all form fields validated, process the form
            f = form.save(commit=False)

            if new_feature:
                f.created_by = request.user
            f.modified_by = request.user
            f.save()

            if 'publication-pk' in request.POST and request.POST['publication-pk']:
                # Here we assign again to p...
                # That is not a problem, since if the form was posted, the
                # pub_id was not passed through the url. (see the template form action)
                p = get_object_or_404(Publication, pk=request.POST['publication-pk'])
                if not p in f.publications.all():
                    # Add the publication to the feature m2m relationship
                    f.publications.add(p)
            else:
                messages.warning(request, "Feature added/updated but not linked to a report")
            f.save()

            if new_feature:
                messages.success(request, "Feature added [id:{0}]".format(f.id))
            else:
                messages.success(request, "Feature updated [id:{0}]".format(f.id))

            if p:
                return redirect('/pubs/report/{0}/'.format(p.id))
            else:
                return redirect('/pubs/feature/{0}/'.format(f.id))

    else:  # this is a get request
        form = AddFeatureMapForm(instance=f)

    return render_to_response('publications/add_feature.html',
                              {'form': form, 'pub': p, 'pub_list': pub_list},
                              context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def add_edit_person(request, person_id=None, name=None):
    """This function takes care of adding or editing a person object.
    The url may capture either an id of the person object to edit, or may
    pass a string containing the name of the new person to add.
    """

    add_person = True
    p = None
    initial = None

    if ('name' in request.GET) and request.GET['name'].strip():
        initial = {'name': request.GET['name'].strip()}

    if person_id:
        p = get_object_or_404(Person, pk=person_id)
        add_person = False
        initial = None
        if not p.is_editable_by(request.user):
            error = "You do not have permissions to edit this person!"
            return render_to_response('publications/access_denied.html',
                                      {'person': p, 'error': error},
                                      context_instance=RequestContext(request))
    else:
        if not request.user.has_perm("{0}.add_person".format(Person._meta.app_label)):
            error = "You do not have permissions to add new person!"
            return render_to_response('publications/access_denied.html',
                                      {'pers': p, 'error': error},
                                      context_instance=RequestContext(request))

    form = AddPersonForm(data=request.POST or initial, instance=p)

    # Some set up operations
    if request.POST:

        #raise NotImplementedError()
        # must implement handling the 'name' field in the form definition in forms.py

        if form.is_valid():
            """Here we should first check if the id-number field was filled.
            if so, check if this number exist in database... it must be unique.
            If it exists, check the name,
                if exact match, notify user that person already exists
                if no match or relaxed match, notify user that other person exist with same id

            If id does not exist
                create the new person.
            """

            # some other operations and model save if any
            # redirect to results page
            p = form.save(commit=False)

            current_user = request.user

            # # Temporary thing, while testing...
            # current_user = User.objects.get(username='thin')
            if add_person:  # assign created by, if this is new object.
                p.created_by = current_user
            p.modified_by = current_user
            p.save()

            return redirect('/pubs/person/{0}/'.format(p.id))
        else:
            raise ValueError('Problem!')

    # # Form was not yet posted...
    # for k in form.fields.keys():
    #     if k not in ['type', 'number', 'title', 'authors', 'abstract',
    #                     'year', 'topic', 'keywords', 'pdffile']:   # This should handle the proper Report type, get list from PubType table.
    #         del form.fields[k]
    #         pass
    #     elif isinstance(form.fields[k].widget, forms.TextInput):
    #         print "TextInput: {0}".format(k)
    #         #form.fields[k].widget.attrs['size'] = 90
    #         pass
    #     else:
    #         print "Field: {0}".format(k)

    return render_to_response('publications/add_person_form.html', {'form': form},
            context_instance=RequestContext(request))


def logout(request):
    auth.logout(request)
    #pdb.set_trace()
    try:
        return redirect(request.GET['next'])
    except:
        return redirect('/pubs/frontpage/')


@login_required(login_url='/accounts/login/')
def person_merge(request, person_id=None):
    """This function is responsible for a view used to merge different person
    entries in the database.

    When called with a person primary key (pers_id) it should search the database
    for any exact or relaxed matches and produce a form where one may choose
    to merge two db person entries.

    For now, it will be a simple overwrite, the current object will be deleted,
    and any relationships will be moved to the chosen person entry.

    In the future, it should be possible to choose which fields should be chosen
    from which model instance.

    """

    if not request.user.is_superuser:
        error = "You do not have permissions to merge person records! Please contact a superuser or database administrator."
        return render_to_response('publications/access_denied.html',
                                  {'pub': p, 'error': error},
                                  context_instance=RequestContext(request))

    #return HttpResponse('Testing submit')
    p = get_object_or_404(Person, pk=person_id)

    if request.POST:
        if 'clear_flags' in request.POST:
                authorships = Authorship.objects.filter(person_id=person_id)
                for pmt in authorships:   # pmt ~ person match through, refers to authorship object
                    pmt.clear_match_indicators()

                editorships = Editorship.objects.filter(person_id=person_id)
                for pmt in editorships:   # pmt ~ person match through, refers to authorship object
                    pmt.clear_match_indicators()

                supervisorships = Supervisorship.objects.filter(person_id=person_id)
                for pmt in supervisorships:   # pmt ~ person match through, refers to authorship object
                    pmt.clear_match_indicators()

                return redirect('/pubs/person/{0}/'.format(person_id))

        if 'select_merge' in request.POST and request.POST['select_merge']:
            for pid in request.POST.getlist('select_merge'):
                pid = int(pid)
                #print "Will merge {0} into {1}".format(pid, person_id)

                """
                Here we should do the following:
                1) update all publication/author relationships
                2) update all publication/supervisor relationships
                3) update all publication/editor relationships

                Could possibly be easily done through accessing the through-tables (using update command)

                Also clear the flagging of this author.

                REMEMBER TO ADD MENU TO PERSON DETAIL PAGE
                MENU SHOULD ALLOW MERGING...
                """
                authorships = Authorship.objects.filter(person_id=pid)

                for pmt in authorships:   # pmt ~ person match through, refers to authorship object
                    tmp = Authorship(person=p,
                                     publication_id=pmt.publication_id,
                                     author_id=pmt.author_id)
                    tmp.save()
                    pmt.delete()

                editorships = Editorship.objects.filter(person_id=pid)

                for pmt in editorships:   # pmt ~ person match through, refers to authorship object
                    tmp = Editorship(person=p,
                                     publication_id=pmt.publication_id,
                                     editor_id=pmt.editor_id)
                    tmp.save()
                    pmt.delete()

                supervisorships = Supervisorship.objects.filter(person_id=pid)

                for pmt in supervisorships:   # pmt ~ person match through, refers to authorship object
                    tmp = Supervisorship(person=p,
                                         publication_id=pmt.publication_id,
                                         supervisor_id=pmt.supervisor_id)
                    tmp.save()
                    pmt.delete()

                # After detaching person from other models, delete it.
                Person.objects.get(pk=pid).delete()

            # Finished iterating, now return to merged person.
            return redirect('/pubs/person/{0}/'.format(person_id))
        elif 'select_merge' in request.POST:
            return redirect('/pubs/person/{0}/'.format(person_id))

    # If form not posted, or invalid post request:

    # Get matches to this person in the database.
    dbp_list = get_person(person=p.get_pybtex_person(), exact=False, relaxed=True)
    # Remove self from resulting QuerySet
    dbp_list = (dbp_list[0].exclude(pk=p.id), dbp_list[1])

    data = {}
    data['person'] = p
    data['choose_person_list'] = dbp_list[0]
    if dbp_list[1] == 'exact':
        data['exact'] = True
    elif dbp_list[1] == 'relaxed':
        data['exact'] = True

    return render_to_response('publications/merge_person_form.html', data,
                              context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def delete_publication(request, pub_id):
    """Delete a publication based on the specified pub_id.
    Will ask for confirmation before deleting.

    """

    p = get_object_or_404(Publication, pk=pub_id)

    if not p.is_deletable_by(request.user):
        error = "You do not have permissions to delete this publication!"
        return render_to_response('publications/access_denied.html',
                                  {'pub': p, 'error': error},
                                  context_instance=RequestContext(request))

    if request.POST:
        if 'cancel' in request.POST:
            return redirect('/pubs/report/{0}/'.format(pub_id))
        elif 'delete' in request.POST:
            p.delete()
            return redirect('/pubs/frontpage/')

    # If form not posted, or invalid post request:

    # Get matches to this person in the database.

    return render_to_response('publications/delete_report_form.html', {'pub': p},
                              context_instance=RequestContext(request))

@login_required(login_url='/accounts/login/')
def delete_publication_features(request, pub_id):
    """Delete all features from the specified publication.
    Will ask for confirmation before deleting.

    """

    p = get_object_or_404(Publication, pk=pub_id)

    if not p.is_deletable_by(request.user):
        error = "You do not have permissions to delete features from this publication!"
        return render_to_response('publications/access_denied.html',
                                  {'pub': pub_id, 'error': error},
                                  context_instance=RequestContext(request))

    feat_list = p.feature_set.all()

    if request.POST:
        if 'cancel' in request.POST:
            return redirect('/pubs/report/{0}/'.format(pub_id))
        elif 'delete' in request.POST:
            for f in feat_list:
                f.delete()
            return redirect('/pubs/report/{0}/'.format(pub_id))

    # If form not posted, or invalid post request:
    return render_to_response('publications/delete_publication_features_form.html', {'pub': p},
                              context_instance=RequestContext(request))




@login_required(login_url='/accounts/login/')
def delete_feature(request, feature_id):
    """Delete a feature based on the specified feat_id.
    Will ask for confirmation before deleting.

    """

    f = get_object_or_404(Feature, pk=feature_id)

    if not f.is_deletable_by(request.user):
        error = "You do not have permissions to delete this feature!"
        return render_to_response('publications/access_denied.html',
                                  {'pub': None, 'error': error},
                                  context_instance=RequestContext(request))

    if request.POST:
        if 'cancel' in request.POST:
            return redirect('/pubs/feature/{0}/'.format(feature_id))
        elif 'delete' in request.POST:
            f.delete()
            return redirect('/pubs/frontpage/')

    # If form not posted, or invalid post request:

    # Get matches to this person in the database.

    return render_to_response('publications/delete_feature_form.html', {'feature': f},
                              context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def person_delete(request, person_id):
    """Delete a person based on the specified person_id.
    Will ask for confirmation before deleting.

    """

    p = get_object_or_404(Person, pk=person_id)

    if not p.is_deletable_by(request.user):
        error = "You do not have permissions to delete this person!"
        return render_to_response('publications/access_denied.html',
                                  {'person': p, 'error': error},
                                  context_instance=RequestContext(request))

    if request.POST:

        if 'cancel' in request.POST:
            return redirect('/pubs/person/{0}/'.format(person_id))
        elif 'delete' in request.POST:
            p.delete()
            return redirect('/pubs/frontpage/')

    # If form not posted, or invalid post request:

    # Get matches to this person in the database.

    return render_to_response('publications/delete_person_form.html', {'person': p},
            context_instance=RequestContext(request))



@login_required(login_url='/accounts/login/')
def delete_publication_file(request, pub_id):
    """Delete the publication file (pdf-file) from the specified publication.
    Will ask for confirmation before deleting.

    """

    p = get_object_or_404(Publication, pk=pub_id)

    if not p.is_deletable_by(request.user):
        error = "You do not have permissions to delete files from this publication!"
        return render_to_response('publications/access_denied.html',
                                  {'pub': pub_id, 'error': error},
                                  context_instance=RequestContext(request))

    if request.POST:
        if 'cancel' in request.POST:
            return redirect('/pubs/report/{0}/'.format(pub_id))
        elif 'delete' in request.POST:
            func_delete_publication_file(request, p.file)
            return redirect('/pubs/report/{0}/'.format(pub_id))

    # If form not posted, or invalid post request:
    return render_to_response('publications/delete_publication_file_form.html', {'pub': p},
                              context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def delete_publication_appendix(request, pub_id, apx_id):
    """Delete an appendix file from the specified publication.
    Will ask for confirmation before deleting.

    """

    p = get_object_or_404(Publication, pk=pub_id)

    if not p.is_deletable_by(request.user):
        error = "You do not have permissions to delete files from this publication!"
        return render_to_response('publications/access_denied.html',
                                  {'pub': pub_id, 'error': error},
                                  context_instance=RequestContext(request))

    apx = p.appendices.get(id=apx_id)

    if request.POST:
        if 'cancel' in request.POST:
            return redirect('/pubs/report/{0}/'.format(pub_id))
        elif 'delete' in request.POST:
            func_delete_publication_file(request, apx)
            return redirect('/pubs/report/{0}/'.format(pub_id))

    # If form not posted, or invalid post request:
    return render_to_response('publications/delete_publication_appendix_form.html', {'pub': p, 'apx': apx},
                              context_instance=RequestContext(request))


def func_delete_publication_file(request, f):
    """Delete the appendix from the database, including dletion of the file
    from the file system.

    """
    fname = f.file.name
    f.file.delete(save=True)
    f.file = None
    f.delete()
    messages.info(request, "File deleted: {0}".format(fname))

