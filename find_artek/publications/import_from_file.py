# -*- coding: utf-8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"


import xlrd
import os.path
import pdb
import datetime
import dateutil.parser
import chardet
import string
import simplejson as json
import re

from pybtex.database import Person as pybtexPerson

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.shortcuts import get_object_or_404
from django.contrib import messages

#from find_artek.publications.models import Publication, Person, Feature, PubType, Authorship
from find_artek.publications import models, person_utils, utils
from find_artek.publications import ldap_person


import logging
logger = logging.getLogger(__name__)


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




def xlsx_pubs(filepath, user=None):
    current_user = user  # User.objects.get(username='thin')

    filemessages = []  # Will hold tuples of e.g. (messages.INFO, "info text")

    wb = xlrd.open_workbook(os.path.join(settings.MEDIA_ROOT, filepath), formatting_info=False)

    sheet_counter = 0
    for s in wb.sheets():
        current_sheet_name = wb.sheet_names()[s.number]
        # ignore empty sheets
        if s.ncols == 0 and s.nrows == 0:
            filemessages.append((messages.WARNING, "Sheet '{0}' is empty, nothing imported.".format(current_sheet_name)))
            continue

        sheet_counter += 1

        # Make list of column names
        col_names = []
        for col in range(s.ncols):
            if s.cell_type(0, col) == 1:
                col_names.append(s.cell_value(0, col).strip())
            else:
                col_names.append(s.cell_value(0, col))

        # ignore sheets that don't provide a title column
        if not (col_names.index('title') or col_names.index('booktitle')):
            filemessages.append((messages.WARNING, "Sheet '{0}' doesn't have a title column, nothing imported.".format('')))
            continue

        number_col = col_names.index('number')

        # iterate over report entries
        report_counter = 0
        for row in range(1, s.nrows):
            print " "
            print "processing report {0}".format(s.cell_value(row, number_col))

            # create dictionary of field:value pairs
            kwargs = dict()
            for col in range(s.ncols):
                if s.cell_value(row, col) and col_names[col]:
                    try:
                        kwargs[col_names[col]] = s.cell_value(row, col).strip()
                    except:
                        kwargs[col_names[col]] = s.cell_value(row, col)

            # extract the foreignkey entries
            fk_dict = dict()
            for k in kwargs.keys():
                if k in ['type', 'journal']:
                    fk_dict[k] = kwargs.pop(k)

            # extract the m2m entries
            m2m_dict = dict()
            for k in kwargs.keys():
                if k in ['author', 'editor', 'supervisor', 'keywords',
                         'topic', 'URLs']:
                    m2m_dict[k] = kwargs.pop(k)

            # handle user information
            kwargs['created_by'] = current_user
            kwargs['modified_by'] = current_user


            ### HANDLE FOREIGNKEY RELATIONSHIPS ###

            # Handle the publication type
            kwargs['type'] = models.PubType.objects.get(type=fk_dict.pop('type', 'STUDENTREPORT'))

            # handle journal if present
            if 'journal' in fk_dict and fk_dict['journal']:
                kwargs['journal'] = models.Journal.objects.get(type=fk_dict.pop('journal'))


            # If year is not given, and this is a report,
            # compose the year from the report number
            if (kwargs['type'].type in ['STUDENTREPORT', 'MASTERTHESIS', 'PHDTHESIS']) and  \
                    ('year' not in kwargs.keys()) and  \
                    ('number' in kwargs.keys()):
                # Construct report publication year from the report number
                if kwargs['number'][0:2] > '90':
                    kwargs['year'] = '19'+kwargs['number'][0:2]
                else:
                    kwargs['year'] = '20'+kwargs['number'][0:2]


            # Create or update publication
            instance, created = models.Publication.objects.get_or_create(
                                    number=s.cell_value(row, number_col),
                                    defaults=kwargs)

            report_counter += 1
            if created:
                print "Publication registered!"

                ### HANDLE M2M RELATIONSHIPS

                # Handle authors, editors, supervisors etc. here!
                for f in ['author', 'supervisor', 'editor']:
                    names = m2m_dict.pop(f, None)
                    add_persons_to_publication(names, instance, f, current_user)

                # Handle the topics
                topics = m2m_dict.pop('topic', None)
                add_topics_to_publication(topics, instance, current_user)

            else:
                print "Publication [id:{0}] exist in database!".format(instance.id)
                # A report with this number was already in the database
                # update any missing values
                updated = False
                for attr, value in kwargs.iteritems():
                    if not getattr(instance, attr):
                        setattr(instance, attr, value)
                        print "Attribute '{0}' set.".format(attr)
                        updated = True

                instance.save()

                if m2m_dict:
                    # handle authors, editors, supervisors etc. here!
                    for f in ['author', 'supervisor', 'editor']:
                        names = m2m_dict.pop(f, None)
                        if len(getattr(instance, f).all()) == 0 and names:
                            pdb.set_trace()
                            # Add persons if no persons are registered already
                            add_persons_to_publication(names, instance, f, current_user)
                            updated = True

                    #pdb.set_trace()
                    # Handle the topics
                    topics = m2m_dict.pop('topic', None)
                    if len(instance.topics.all()) == 0 and topics:
                        add_topics_to_publication(topics, instance, current_user)
                        updated = True

                if not updated:
                    filemessages.append((messages.WARNING, "Publication '{0}' exists in database, no attributes changed.".format(instance.title)))
                    print "No attributes updated!"
                else:
                    filemessages.append((messages.WARNING, "Publication '{0}' exists in database, some attributes were updated.".format(instance.title)))
                instance.save()

        if report_counter != s.nrows-1:
            filemessages.append((messages.INFO, "{0} of {1} publications registered/updated from sheet '{2}'.".format(report_counter, s.nrows-1, current_sheet_name)))
        else:
            filemessages.append((messages.SUCCESS, "{0} of {1} publications registered/updated from sheet '{2}'.".format(report_counter, s.nrows-1, current_sheet_name)))
    return filemessages



def add_persons_to_publication(names, pub, field, user):
    # return if no names passed
    if not names or not names.strip():
        return

#    if getattr(pub, field).all():
#        # Skip if field is already populated.
#        return

    #define pubplication-person through-table
    through_tbl = getattr(models, field[0].upper() + field[1:] + 'ship')

    kwargs = dict()

    # Parse author names to a list, use only non-empty items
    kwargs[field] = [s for s in person_utils.parse_name_list(names) if s]

    for id, s in enumerate(kwargs[field]):
        print "Processing person: {0}".format(s.encode('ascii', 'replace'))
        exact_match = False
        multiple_match = False
        relaxed_match = False

        if re.search('[a-zA-Z]{1}[0-9]{6}', s):
            # This is a study number...

            # See if it is in our own database
            p, match = person_utils.get_person(id_number=s, exact=True)
            if not p:
                # Now see if it is in LDAP directory
                result = ldap_person.find_ldap_person(name=s)
                if result:
                    p = ldap_person.get_or_create_person_from_ldap(person=result[0],
                                                                   user=user)
                    exact_match = True
                    print "   LDAP match"
                else:
                    # ISSUE A WARNING!
                    continue
            else:
                print "   DB match"
        elif len(re.split('[^A-Za-z]',s)) == 1:
            # this is an entry with only consecutive letters = initials

            # See if it is in our own database
            p, match = person_utils.get_person(initials=s, exact=True)
            if not p:
                # Now see if it is in LDAP directory
                result = ldap_person.find_ldap_person(initials=s)
                if result:
                    p = ldap_person.get_or_create_person_from_ldap(person=result[0],
                                                                   user=user)
                    exact_match = True
                    print "   LDAP match"
                else:
                    # ISSUE A WARNING!
                    continue
            else:
                print "   DB match"
        else:
            # otherwise... this is just a name...
            person = pybtexPerson(s)

            if not (hasattr(person, 'first') and hasattr(person, 'last')):
                raise ValueError("Missing parts of name, cannot create database entry")

            print "   Processing person {0}: {1}".format(id, utils.unidecode(unicode(person)))

            # Get existing persons using relaxed naming
            p, match = person_utils.get_person(person=person)

            if len(p) > 1:
                # More than one exact return, flag multiple_match
                multiple_match = True
            if match == 'exact' and len(p) > 0:
                # if exact match flag exact_match
                exact_match = True
            elif match == 'relaxed' and len(p) > 0:
                # if relaxed match flag relaxed_match
                relaxed_match = True

            # Create new person, also if matched
            p = person_utils.create_person_from_pybtex(person=person, user=user)

        if p:
            # add the person to the author/supervisor/editor-relationship
            tmp = through_tbl(person=p[0],
                              publication=pub,
                              exact_match=exact_match,
                              multiple_match=multiple_match,
                              relaxed_match=relaxed_match,
                              **{field+'_id': id})
            tmp.save()



#    kwargs[field] = [pybtexPerson(s) for s in
#                     person_utils.parse_name_list(names) if s]

    # # Cycle through persons
    # for id, pers in enumerate(kwargs[field]):
    #     if not (hasattr(pers, 'first') and hasattr(pers, 'last')):
    #         raise ValueError("Missing parts of name, cannot create database entry")

    #     print "   Processing person {0}: {1}".format(id, utils.unidecode(unicode(pers)))

    #     exact_match = False
    #     multiple_match = False
    #     relaxed_match = False

    #     # Get existing persons using relaxed naming
    #     p, match = person_utils.get_person(person=pers)

    #     if len(p) > 1:
    #         # More than one exact return, flag multiple_match
    #         multiple_match = True
    #     if match == 'exact' and len(p) > 0:
    #         # if exact match flag exact_match
    #         exact_match = True
    #     elif match == 'relaxed' and len(p) > 0:
    #         # if relaxed match flag relaxed_match
    #         relaxed_match = True

    #     # Create new person, also if matched
    #     p = person_utils.create_person_from_pybtex(person=pers, user=user)

    #     if p:
    #         # add the person to the author/supervisor/editor-relationship

    #         tmp = through_tbl(person=p[0],
    #                           publication=pub,
    #                           exact_match=exact_match,
    #                           multiple_match=multiple_match,
    #                           relaxed_match=relaxed_match,
    #                           **{field+'_id': id})
    #         tmp.save()


def add_topics_to_publication(topics, pub, user):
    # Get list of topics already attached
    # Iterate through posted topics
    # Is topic in existing list: continue
    # Is topic in database? add to m2m relationship
    # Topics cannot be added if they do not exist... drop it
    # remove any remaining model bound topics that were not in post

    mtop = [t.topic for t in pub.topics.all()]  # list of model bound topic

    topics = [word.strip(string.punctuation) for word in topics.split()]

    for t in topics:
        if CaseInsensitively(t) in mtop:
            mtop.remove(CaseInsensitively(t))
            continue

        mt = models.Topic.objects.filter(topic__iexact=t)
        if not mt:
            mt = models.Topic(topic=t)
            mt.save()
            mt = [mt]

        # add only the first topic returned
        pub.topics.add(mt[0])

    # Now remove any remaining topic
    if mtop:
        for t in mtop:
            pub.topics.remove(r.topics.get(topic=t))

    pub.save()


def xlsx_features(filepath):
    """Function to read an Excel workbook and return feature information from a
    sheet named "Features" as a json object. The ´json object has the following
    structure:

    fdict is a dictionary
        pub_id     Integer id value corresponding to the publication primary key
        data:      dictionary of field values for Feature instance
        GEOjson:   dictionary óf fields which is translatable to a GEOSGeometry
        srid:      The EPSG spatial reference id. see http://spatialreference.org/
        skip:      Flag to skip the feature if an error has occurrde
        messages:  List of error and warning messages for the feature
                    format: [ [messages.ERROR, "ErrorMessage"], ... ]

    """

    filemessages = []  # Will hold tuples of e.g. (messages.INFO, "info text")

    wb = xlrd.open_workbook(os.path.join(settings.MEDIA_ROOT, filepath))

    s = wb.sheet_by_name('Features')

    if not s:
        logger.error("Excel file does not hold a sheet by the name 'Features'. Import aborted.")
        filemessages.append((messages.ERROR, "Excel file does not hold a sheet by the name 'Features'. Import aborted."))
        return ([], filemessages)

    # Expected column names in the xlsx file.
    col_names = ['Publication_ID', 'Feature#', 'Feature_type', 'Name', 'Geometry_type',
                 'SRID', 'UTMX/LON', 'UTMY/LAT', 'Pos_quality', 'Date',
                 'Description', 'Comment', 'Direction']

    # Make list of column names in actual document
    sheet_col_names = []
    for col in range(s.ncols):
        if s.cell_type(0, col) == 1:
            sheet_col_names.append(s.cell_value(0, col).strip())
        else:
            sheet_col_names.append(s.cell_value(0, col))

    # Check that all expected columns are actually in the sheet
    # Abort if at least one column is not present.
    for cn in col_names:
        if cn not in sheet_col_names:
            msg = "Excel feature col_name problem: " + cn + " missing in file. Import aborted."
            logger.error(msg)
            filemessages.append((messages.ERROR, msg))
            return ([], filemessages)

    fdict = {} # Dictionary to hold feature information

    # iterate over rows in sheet (Feature entries)
    for row in range(1, s.nrows):

        # Get the feature number
        fnum = s.cell_value(row, col_names.index('Feature#'))
        if not fnum:
            # if no feature number is given, skip the line
            msg = "The 'Feature#' field of row {0} is blank! The row is ignored.".format(row+1)
            filemessages.append((messages.WARNING, msg))
            continue

        try:
            # Try to format the feature number as a normal number format
            fnum = "{0:g}".format(fnum)
        except:
            pass

        # If this is a new feature number, get all properties
        if fnum and fnum not in fdict:

            # Add the feature number to the dictionary
            fdict[fnum] = {
                'pub_id': None,
                'data': {},
                'GeoJSON': {},
                'srid': {},
                'skip': False,
                'messages': []}


            # Find related publication:
            pub_id = s.cell_value(row, col_names.index('Publication_ID'))
            if pub_id:
                try:
                    fdict[fnum]['pub_id'] = int(pub_id)
                except:
                    fdict[fnum]['skip'] = True
                    msg = "Row {0} (feature# {1}) does not have a valid Publication_ID. This feature is skipped!".format(row+1, fnum)
                    fdict[fnum]['messages'].append((messages.ERROR, msg))

            fdict[fnum]['data']['comment'] = s.cell_value(row, col_names.index('Comment'))
            fdict[fnum]['data']['name'] = s.cell_value(row, col_names.index('Name'))
            fdict[fnum]['data']['type'] = s.cell_value(row, col_names.index('Feature_type'))
            fdict[fnum]['data']['date'] = s.cell_value(row, col_names.index('Date'))
            orig_date = fdict[fnum]['data']['date']
            date_ctype = s.cell_type(row, col_names.index('Date'))   # get the cell type e.g. XL_CELL_TEXT, XL_CELL_NUMBER, XL_CELL_DATE
            if fdict[fnum]['data']['date']:
                if date_ctype == 3:
                    # This is a date type cell, use xlrd's date conversion
                    fdict[fnum]['data']['date'] = xlrd.xldate_as_tuple(fdict[fnum]['data']['date'], wb.datemode)
                    fdict[fnum]['data']['date'] = datetime.datetime(*fdict[fnum]['data']['date']).date()
                else:
                    # This is a number or text type
                    try:
                        # Try parsing the expected date format
                        fdict[fnum]['data']['date'] = datetime.datetime.strptime(fdict[fnum]['data']['date'], '%Y-%m-%d').date()
                    except:
                        # if error, try using dateutils parser
                        fdict[fnum]['data']['date'] = dateutil.parser.parse(fdict[fnum]['data']['date'],
                                                               dayfirst=True,
                                                               yearfirst=True,
                                                               default=datetime.date(1900, 1, 1),
                                                               fuzzy=True)
                        # Add warning to messages
                        msg = "Feature ({1}) '{0}': Unexpected date format, parsed date may be wrong ('{2}' == '{3}' ??)".format(fdict[fnum]['data']['name'], fnum, orig_date, fdict[fnum]['data']['date'])
                        fdict[fnum]['messages'].append((messages.WARNING, msg))

                        # Add warning to feature comment.
                        if not fdict[fnum]['data']['comment']:
                            fdict[fnum]['data']['comment'] += '\r\n'
                        fdict[fnum]['data']['comment'] += '[Date of feature may be wrong!]'

            fdict[fnum]['data']['direction'] = s.cell_value(row, col_names.index('Direction'))
            fdict[fnum]['data']['description'] = s.cell_value(row, col_names.index('Description'))
            fdict[fnum]['data']['pos_quality'] = s.cell_value(row, col_names.index('Pos_quality'))
#            fdict[fnum]['data']['created_by'] = current_user
#            fdict[fnum]['data']['modified_by'] = current_user

#            # Create feature
#            f = models.Feature(**kwargs)
#            f.save()
#            fmsg = [messages.INFO, "Feature ({1}) '{0}' created".format(f.name, fnum)]

            # Parse the spatial reference id

            # Get the srid and remove EPSG: or epsg: if it is present.
            srid = s.cell_value(row, col_names.index('SRID'))
            if s.cell_type(row, col_names.index('SRID')) == 1:
                # If this is text input, try removing "epsg:""
                srid = srid[len('epsg:'):] if srid.startswith('epsg:') else srid
            try:
                fdict[fnum]['srid'] = int(srid)
            except:
                fdict[fnum]['skip'] = True
                msg = "The 'SRID' field of row {0} (feature# {1}) is blank or not an integer. This feature is skipped!".format(row+1, fnum)
                fdict[fnum]['messages'].append((messages.ERROR, msg))
                continue

            if s.cell_value(row, col_names.index('Geometry_type')) == 'point':
                # This is a point we can finish the handling here
                x, y = (s.cell_value(row, col_names.index('UTMX/LON')),
                        s.cell_value(row, col_names.index('UTMY/LAT')))

                fdict[fnum]['GeoJSON']['type'] = "MultiPoint"
                fdict[fnum]['GeoJSON']['coordinates'] =  [ [x, y] ]

#                try:
#                    geom = GEOSGeometry(fWKT, srid=fdict[fnum]['srid'])
#                except:
#                    fdict[fnum]['skip'] = True
#                    msg = "The coordinate and srid fiels of row {0} (feature# {1}) do not evaluate to a valid geographical point This feature is skipped!".format(row, fnum)
#                    fdict[fnum]['messages'].append((messages.ERROR, msg))
#                    continue

#                f.points = geom


            #######
            #######   UPDATE HAS REACHED THIS POINT   ######
            #######




            elif s.cell_value(row, col_names.index('Geometry_type')) == 'line':
                # This is a line, we must expect more segments to be added

                # Encode to GeoJSON and store temporarily, e.g. make feature_list
                # a dictionary, where the key is the feature number/name, and
                # the value holds the GeoJSON for lines and polygons

                # THen if an existing feature_number/name is encountered
                # add the coordinate info to the GeoJSON, taking care of
                # coordinate transform (or assuming same SRID??)

                # When all features are processed add the valid GeoJSON to
                # the respective features.
                # This requires that we keep track of the feature ID of the
                # created features also.

                # Also handle possible errors during parsing... so that all
                # lines/polygons are not lost if errors occur.

                # Could save GeoJSON already after two points. And then replace
                # everytime a new coordinate is added.

                x, y = (s.cell_value(row, col_names.index('UTMX/LON')),
                        s.cell_value(row, col_names.index('UTMY/LAT')))

                fdict[fnum]['GeoJSON']['type'] = "MultiLineString"
                fdict[fnum]['GeoJSON']['coordinates'] =  [ [[x, y]] ]


            elif s.cell_value(row, col_names.index('Geometry_type')) == 'polygon':
                # This is a polygon, we must expect more segments to be added

                x, y = (s.cell_value(row, col_names.index('UTMX/LON')),
                        s.cell_value(row, col_names.index('UTMY/LAT')))

                fdict[fnum]['GeoJSON']['type'] = "MultiPolygon"
                fdict[fnum]['GeoJSON']['coordinates'] =  [ [[[x, y], [x, y]]] ]


            """Here we should handle multiple rows with the same feature#.
            if point, a new point should be added to multipoint geometry
            if line, a new point should be added to the line geometry
            if polygon, a new point should be added to the polygon geometry
            """

#            f.save()


        elif fnum:
            """The feature number is not empty, and already exists in the
            dictionary, which means it must be an additional point to a line
            or polygon (multi-points are not intended implemented).

            """

            # If skip-flag is set, continue to next feature without processing
            if fdict[fnum]['skip']:
                continue

            # Parse the spatial reference id

            # Get the srid and remove EPSG: or epsg: if it is present.
            srid = s.cell_value(row, col_names.index('SRID'))
            if s.cell_type(row, col_names.index('SRID')) == 1:
                # If this is text input, try removing "epsg:""
                srid = srid[len('epsg:'):] if srid.startswith('epsg:') else srid
            try:
                srid = int(srid)
            except:
                fdict[fnum]['skip'] = True
                msg = "The 'SRID' field of row {0} (feature# {1}) is blank or not an integer. This feature is skipped!".format(row+1, fnum)
                fdict[fnum]['messages'].append((messages.ERROR, msg))
                continue

            if srid != fdict[fnum]['srid']:
                msg = "SRID mismatch for feature# {1} ({0}), row {2}. "+ \
                      "Point was not added to geometry!"
                msg = msg.format(fdict[fnum]['data']['name'], fnum, row+1)
                fdict[fnum]['messages'].append((messages.WARNING, msg))
            else:
                if fdict[fnum]['GeoJSON']['type'] == 'MultiLineString':
                    """The first time the feature number was encountered, it was
                    registered as a line. We consider it a line, no matter what is
                    registered for additional points, but may raise a warning, if
                    the registered feature types do not match.

                    """

                    x, y = (s.cell_value(row, col_names.index('UTMX/LON')),
                            s.cell_value(row, col_names.index('UTMY/LAT')))

                    fdict[fnum]['GeoJSON']['coordinates'][0].append([x,y])

                    gtype = s.cell_value(row, col_names.index('Geometry_type'))
                    ctype = s.cell_type(row, col_names.index('Geometry_type'))
                    if ctype not in [0, 1] or (ctype == 1 and gtype.lower() not in ['line', 'multiline', 'linestring', 'multilinestring']):
                        msg = "Geometry type mismatch for feature# {1} ({0}), "+ \
                              "row {2}. Coordinates were added to geometry "+          \
                              "anyway"
                        msg = msg.format(fdict[fnum]['data']['name'], fnum, row+1)
                        fdict[fnum]['messages'].append((messages.WARNING, msg))

#                    geom = GEOSGeometry(json.dumps(fdict[fnum]['data']['GeoJSON']),
#                                        srid=fdict[fnum]['data']['srid'])
#                    f.lines = geom
#                    f.save()


                elif fdict[fnum]['GeoJSON']['type'] == 'MultiPolygon':
                    """The first time the feature number was encountered, it was
                    registered as a polygon. We consider it a polygon, no matter
                    what is registered for additional points, but may raise a
                    warning, if the registered feature types do not match.

                    """

                    x, y = (s.cell_value(row, col_names.index('UTMX/LON')),
                            s.cell_value(row, col_names.index('UTMY/LAT')))

                    fdict[fnum]['GeoJSON']['coordinates'][0][0].insert(-1, [x,y])

                    gtype = s.cell_value(row, col_names.index('Geometry_type'))
                    ctype = s.cell_type(row, col_names.index('Geometry_type'))
                    if ctype not in [0, 1] or (ctype == 1 and gtype.lower() not in ['polygon', 'multipolygon']):
                        msg = "Geometry type mismatch for feature {1} ({0}), "+ \
                              "row {2}. Coordinates were added to geometry "+          \
                              "anyway"
                        msg = msg.format(fdict[fnum]['data']['name'], fnum, row+1)
                        fdict[fnum]['messages'].append((messages.WARNING, msg))

#                    print json.dumps(fdict[fnum]['data']['GeoJSON'])

#                    if len(fdict[fnum]['data']['GeoJSON']['coordinates'][0][0]) >= 4:
#                        # We must have at least four points to a polygon (=triangle).
#                        geom = GEOSGeometry(json.dumps(fdict[fnum]['data']['GeoJSON']),
#                                            srid=fdict[fnum]['data']['srid'])
#                        f.polys = geom
#                        f.save()

                    pass   #### UPDATE HERE ####
                else:
                    pass   #### UPDATE HERE ####

    return (fdict, filemessages)
