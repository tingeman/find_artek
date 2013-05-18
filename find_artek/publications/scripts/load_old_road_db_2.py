# -*- coding: utf_8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

print " "
print "*** NOTICE ***"
print "This module must be used in a console that supports unicode!"
print "In windows cmd shell issue the following commands, before starting python:"
print "> chcp 65001"
print "> set PYTHONIOENCODING=utf-8"
print " "


#from django.contrib.gis.db import models
import re
import os.path
import pdb
import sys
import numpy as np
#import urllib
import MySQLdb
from pybtex.database import Person as pybtexPerson


#from django.db.models import Q
#from django.contrib.gis.geos import Point
from django.contrib.gis.geos import GEOSGeometry
from django.utils.encoding import iri_to_uri
from django.contrib.auth.models import User

current_user = User.objects.get(username='thin')
img_ext = ['.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.png', '.bmp']


# According to: http://stackoverflow.com/questions/878972/windows-cmd-encoding-change-causes-python-crash/3259271
#try: import uniconsole
#except ImportError: sys.exc_clear() # could be just pass, of course
#else: del uniconsole # reduce pollution, not needed anymore


#from find_artek.publications import latex_codec
from find_artek.publications import models as pub_models
from find_artek.publications import person_utils

re_name_sep_words = re.compile(r'\s*[;&\n]+\s*|\s+and\s+|\s+AND\s+|\s+And\s+|\s+og\s+|\s+OG\s+|\s+Og\s+')
re_space_sep = re.compile(r'(?<!,)\s(?!,)')  # used to find spaces that are not connected to commas


mysql_ip_address = '192.168.0.105'
#mysql_ip_address = '172.16.1.164'
road_db_path = 'road'


def connect_to_road_db():
    print "Make sure MySQL with old ARTEK road_db is running at {0}!".format(mysql_ip_address)
    print "(or change code...)"
    raw_input('Press enter when ready...')

    mdb = MySQLdb.connect(host=mysql_ip_address, user='tin', passwd='test',
                          db='road_db', use_unicode=True)
#    mdb = MySQLdb.connect(host='127.0.0.1', user='tin', passwd='test',
#                          db='road_db', use_unicode=True)
    return mdb.cursor()


re_separate_names = re.compile(r'\s*[;&]+\s*|\s+and\s+|\s+AND\s+|\s+And\s+|\s+og\s+|\s+OG\s+|\s+Og\s+')
re_comma_separated = re.compile(r'(?<=[A-Za-z]\s[A-Za-z])\s*[,]\s*')
re_comma_separated = re.compile(r'(?:[A-Za-z]+\s[A-Za-z]+)\s*[,]\s*')

re_newline = re.compile(r'\s*[\r\n]+\s*')


def import_reports(get_reports=False):
    print "--------------------------------------------"
    print " Importing reports from old Report database "
    print "--------------------------------------------"
    print " "

    # Connect to old database and get all entries in table Reports
    cur = connect_to_road_db()
    cur.execute('SELECT * from Reports')
    rows = cur.fetchall()

    # These will be registered as STUDENTREPORT
    type = pub_models.PubType.objects.get(type='STUDENTREPORT')

    # Get column names of the Reports table
    columns = [c[0] for c in cur.description]

    # Loop through all entries
    for rid, row in enumerate(rows):
        # Make a dictionary of column names and entry values
        entry = dict(zip(columns, row))

        print " "
        print "Processing entry {0}: {1}".format(rid, entry['RepName'])
        print " - Authors:     {0}".format(entry['Authors'])
        print " - Supervisors: {0}".format(entry['ContactPerson'])

        if pub_models.Publication.objects.filter(number=entry['Number']):
            print 'Report {0} already in database, skipping...'.format(entry['Number'])
            continue

        # Construct report publication year from the report number
        if entry['Number'][0:2] < 90:
            year = '19' + entry['Number'][0:2]
        else:
            year = '20' + entry['Number'][0:2]

        kwargs = dict(type=type,
                      title=re_newline.sub(u' ', entry['RepName']),
                      number=entry['Number'],
                      series='ARTEK student report',
                      comment=entry['Comment'],
                      grade=entry['Grade'],
                      school='Technical University of Denmark',
                      year=year)

        kwargs = dict((k, v) for k, v in kwargs.items() if not v is None)

        # Create the report
        r = pub_models.Publication(**kwargs)
        r.created_by = current_user
        r.modified_by = current_user
        r.save()

        # Parse author names to a list
        entry['Authors'] = [pybtexPerson(s) for s in
                            person_utils.parse_name_list(entry['Authors'])]

        # Cycle through Authors
        for id, auth in enumerate(entry['Authors']):
            print "   Processing author {0}: {1}".format(id, auth)

            # Get existing persons using relaxed naming
            p, match = person_utils.get_person(person=auth)
            if not p:
                print "    - Creating person in database!"
                # if none are found, create new person
                p = person_utils.create_person_from_pybtex(person=auth, user=current_user)
            elif len(p) > 1 or match == 'relaxed':
                # if more than one person is returned,
                # or if relaxed search was used,
                # have user select...
                p = person_utils.choose_person(p, auth)

            if p:
                # add the author to the author-relationship
                tmp = pub_models.Authorship(person=p[0],
                                            publication=r,
                                            author_id=id)
                tmp.save()

        # Parse supervisor initials to a list
        entry['ContactPerson'] = [s.upper() for s in
                                  re_name_sep_words.split(entry['ContactPerson'])]
        # There will be only one supervisor in these cases.

        for id, superv in enumerate(entry['ContactPerson']):
            print "   Processing supervisor {0}: {1}".format(id, superv)

            # Get existing persons using relaxed naming
            p, match = person_utils.get_person(initials=superv, exact=False)
            if not p:
                # if none are found, create new person
                print "    - Creating person in database!"
                p = person_utils.create_person_from_pybtex(
                        pybtexPerson(first='unknown', last='unknown', initials=superv),
                        user=current_user)
            elif len(p) > 1 or match == 'relaxed':
                # if more than one person is returned,
                # or if relaxed search was used,
                # have user select...
                p = person_utils.choose_person(p, superv)

            if p:
                # add the author to the author-relationship
                s = pub_models.Supervisorship(person=p[0],
                                              publication=r,
                                              supervisor_id=id)
                tmp.save()

        if get_reports and entry['RepLink']:
            # load reports from registered URL and save to local server
            # If RepLink is empty, no report is available.

            pubfile = pub_models.FileObject()
            pubfile.created_by = current_user
            pubfile.modified_by = current_user
            pubfile.save()

            # retrieve and save file
            pdf_url = urljoin(mysql_ip_address, road_db_path, entry['BaseDir'], entry['RepLink'])
            pdf_url = 'http://' + pdf_url
            print " "
            print "Retrieving file from: {0}".format(pdf_url)
            pdf_temp = get_file_from_url(pdf_url)

            fname, fext = os.path.splitext(entry['RepLink'])
            pubfile.upload_to = os.path.join('reports', '{0}'.format(r.year))

            pubfile.file.save('{0}{1}'.format(r.number, fext), pdf_temp, save=True)

            print "Report saved to: {0}".format(pubfile.file.name)

            r.file = pubfile
            r.save()
            pdf_temp.close()

    correct_marie_johnsen()


def correct_marie_johnsen():
    print " "
    print "--------------------------------------------"
    print " Correcting wrong entry: Maria Johnsen      "
    print "--------------------------------------------"
    print " "

    queryset, match = person_utils.get_person('Maria Johnsen', exact=True)
    if not queryset:
        print "Person Maria Johnsen not found in database."
        return

    if match == 'exact':
        person = queryset[0]
        person.first = 'Marie'
        person.save()
        print "Correction: Maria --> Marie"


def register_feature_media(feature, media_url, filename, caption):
    from urlparse import urlparse

    # Get the first report registered for the feature
    r = feature.publications.all()[0]
    if not r:
        raise ValueError('No reports registered for Feature!')

    # retrieve and save file to temporary storage
    print " "
    retry = True

    while retry:
        print "Retrieving media from: {0}".format(media_url)
        media_temp = get_file_from_url(media_url)
        if media_temp:
            retry = False
        else:
            # There was a HTTP Error... and None was returned
            if media_url.find('Billede_') >= 0:
                # The MySQL database have some wrong links registered, try if that is the case...
                media_url = media_url.replace('Billede_', 'Billede%20', 1)
            elif media_url.find('%20.') >= 0:
                media_url = media_url.replace('%20.', '.')
            elif media_url.find(' .') >= 0:
                media_url = media_url.replace(' .', '.')
            elif media_url.endswith('%20'):
                media_url = media_url[:-3]
            elif media_url.find('%20d%C3%B8dis.') >= 0:
                media_url = media_url.replace('%20d%C3%B8dis.', '%20d%C3%B8dishul.')
            elif media_url.endswith('.bmp'):
                media_url = media_url.replace('.bmp', '.png')
            elif media_url.endswith('.jpeg'):
                media_url = media_url.replace('.jpeg', '.jpg')
            elif media_url.find('07-18/klassifikation/') >= 0:
                media_url = media_url.replace('07-18/klassifikation/', '07-18/Geoelektrik/')
            else:
                # Return to user...
                pdb.set_trace()
                retry = False

    if media_url.find('_small') >= 0:
        # If the url has _small, it is an image in reduced size.
        # See if the 'non-small' version of the picture exists...
        new_url = media_url.replace('_small', '')
        new_media_temp = get_file_from_url(new_url)
        if new_media_temp:
            # If the file could be downloaded, discard the _small version
            # and replace with regular size version.
            media_temp.close()
            media_temp = new_media_temp
            media_url = new_url
            filename = filename.replace('_small', '')

    # Setup filenames and base path
    fname, fext = os.path.splitext(filename)
    o = urlparse(media_url)

    # Check if the media already exists in FileObject or ImageObject table
    # Do the filtering:
    if fext not in img_ext:
        fo = pub_models.FileObject.objects.filter(original_URL=o.path)
    else:
        fo = pub_models.ImageObject.objects.filter(original_URL=o.path)

    # Check the rows returned, get the File/Image object, if it exists
    newfile = True
    if len(fo) > 1:
        print "More than one object with the specified path...!?"
        newfile = False
        pdb.set_trace()
    elif len(fo) == 1:
        myfile = fo[0]
        newfile = False
        print "Media already in database, registering existing FileObject!"
    elif len(fo) < 0:
        newfile = True

    # Define path where to save the file
    upload_dir = ['reports', '{0}'.format(r.year), r.number]

    # Diferentiate between different file types (presently images and other)
    if fext not in img_ext:
        if newfile:
            # Create media file.
            myfile = pub_models.FileObject()
        file_field = ['file', 'files']
        cap_field = 'description'
    else:
        if newfile:
            # Create image file.
            myfile = pub_models.ImageObject()
        file_field = ['image', 'images']
        cap_field = 'caption'
        upload_dir.append('img')

    # Set mandatory fields
    myfile.modified_by = current_user

    if newfile:
        myfile.created_by = current_user

        myfile.original_URL = o.path

        # Bypass normal 'upload_to' path generation by setting it directly
        myfile.upload_to = os.path.join(*upload_dir).replace(' ', '_')
        # All spaces are replaced by underscores...

        # Store description text in proper field
        if not media_temp:
            caption += '  [Linked media not found during import: {0}]'.format(media_url)

        setattr(myfile, cap_field, caption)

        # Save to database to generate primary_key before adding file
        myfile.save()

        # Save the temp file to an actual file at the correct location
        # The getattr is a way to reuse the same code for several classes (FileObject or ImageObject)
        # see http://stackoverflow.com/questions/1545645/how-to-set-django-model-field-by-name
        if media_temp:
            getattr(myfile, file_field[0]).save('{0}{1}'.format(fname, fext), media_temp, save=True)
            print "Media saved to: {0}".format(getattr(myfile, file_field[0]).name)
            # Make sure temp-file is deleted
            media_temp.close()
            myfile.original_URL = media_url
        else:
            print "Media not available, thus not saved to file-system!"

    # Add the file to the appropriate m2m field on the feature (files or images)
    getattr(feature, file_field[1]).add(myfile)
    feature.save()


def import_features(get_media=False):
    print "--------------------------------------------"
    print " Importing features from old Report database "
    print "--------------------------------------------"
    print " "

    feature_types = dict(pub_models.Feature.feature_types)

    # Connect to old database and get all entries in table Reports
    cur = connect_to_road_db()
    cur.execute('SELECT *,AsText(geo) from objects')
    rows = cur.fetchall()

    # Get column names of the old objects table
    columns = [c[0] for c in cur.description]

    # Loop through all entries
    for rid, row in enumerate(rows):
        # Make a dictionary of column names and entry values
        entry = dict(zip(columns, row))

        entry['Type'] = entry['Type'].upper()

        if entry['Type'] not in feature_types.keys():
            choice_list = []
            ok = False
            while ok == False:
                print "Entry type '{0}' not recognized, please choose:".format(entry['Type'])
                for i, k in feature_types.keys():
                    print "  {0}  {1}".format(i, feature_types[k])
                    choice_list.append(k)
                try:
                    entry['Type'] = choice_list[int(input('Please enter your choice:'))]
                    ok = True
                except:
                    ok = False

        kwargs = dict(type=        entry['Type'],
                      name=        re_newline.sub(u' ', entry['ObjName']),
                      area=        entry['Area'],
                      direction=   entry['Direction'],
                      description= entry['Description'],
                      comment=     entry['Comment'],
                      date=        entry['Date'],
                      )

        # ASSUMING WE HAVE ONLY POINT AND LINESTRING (otherwise the coords handling will fail)
        # Parse Feature geometry WKT
        geom_type = entry['AsText(geo)'].partition('(')
        #coords = ''.join(geom_type[1:])
        coords = geom_type[2].rstrip(')')

        def parse_coords(c):
            clist = c.split(',')
            return [np.fromstring(cpair.strip(), sep=' ') for cpair in clist]

        def correct_coords(clist):
            for id, cpair in enumerate(clist):
                if cpair[0] > 1e6 and cpair[1] < 1e6:
                    clist[id] = cpair[::-1]
            return clist

        def coords2str(clist):
            strcoords = ''
            for id, cpair in enumerate(clist):
                strcoords = ','.join((strcoords, '{0[0]} {0[1]}'.format(cpair)))
            return strcoords[1:]

        coords = parse_coords(coords)
        coords = correct_coords(coords)
        strcoords = coords2str(coords)

        if geom_type[0] == 'POINT':
            kwargs['points'] = GEOSGeometry('SRID=32622;MULTIPOINT({0})'.format(strcoords))
            # Assume SRID 32622 = UTM Zone 22N, WGS84
        elif geom_type[0] == 'LINESTRING':
            kwargs['lines'] = GEOSGeometry('SRID=32622;MULTILINESTRING(({0}))'.format(strcoords))
        else:
            print "*** Geometry type not recognized: {0} ***".format(geom_type[0])
            print "Feature ID (old database): {0} ".format(entry['ObjID'])
            sys.pause()
            continue

        print " "
        print "Processing entry {0}: {1}".format(rid, entry['ObjName'])
        print " - Type: {0}".format(entry['Type'])

        #if pub_models.Feature.objects.filter(name=kwargs['name']):
        #    print 'Feature "{0}" already in database, skipping...'.format(kwargs['name'])
        #    continue

        # Make sure kwargs only has entries that are not None
        kwargs = dict((k, v) for k, v in kwargs.items() if not v is None)

        # Create the feature

        f = pub_models.Feature(**kwargs)
        f.created_by = current_user
        f.modified_by = current_user
        f.save()

        # Find and add the correct reports to m2m-relationship
        sql = "SELECT reports.Number, reports.BaseDir FROM reports,repobjlink WHERE repobjlink.Obj_ID = {0} AND reports.RepID = repobjlink.Rep_ID".format(entry['ObjID'])

        cur.execute(sql)
        rep_nums = cur.fetchall()
        print "Number of related reports: {0}".format(len(rep_nums))

        for rn in rep_nums:
            reports = pub_models.Publication.objects.filter(number=rn[0])
            if reports:
                for r in reports:
                    f.publications.add(r)
                    print "Report {0} added.".format(r.number)

        f.save()

        if get_media and (entry['Links'] or entry['Pictures']):

            # load media from MySQL server and save to local server
            # If Links and Pictures are empty, no media is available.

            # Workflow:

            # 1) Get and split media from Links
            # 2) Get and split media from Pictures
            # 3) Compare the two lists, any entry in Pictures has identical name except _small, skip this entry
            # 4) Merge lists
            # 5) Loop through merged list
            #    - determine image or file based on extension
            #    - create image or file object and load file.
            #    - register in feature

            media = entry['Links'].split(';')
            media_captions = entry['LinksDescr'].split(';')
            pictures = entry['Pictures'].split(';')

            if rep_nums:
                MySQL_base_dir = rep_nums[0][1]  # Get the base path to the MySQL media
            else:
                raise ValueError('No path specified for MySQL media!')

            # Make list of filenames without extensions for pictures in media list
            picnames = []
            to_delete = []
            for id, m in enumerate(media):
                pn, ff = os.path.split(m)
                fn, fe = os.path.splitext(ff)

                if not fn:
                    to_delete.append(id)

                # This change is due to an error in the registration in the MySQL database,
                # Which we need to correct for this to work
                if fn.startswith('pic') and fe == '.htm':
                    fn = fn.replace('pic', 'Billede ', 1)
                    fe = '.jpg'
                elif fn.startswith('sample') and fe == '.htm':
                    fe = '.doc'
                elif fn.startswith('data') and fe == '.htm':
                    fe = '.png'
                    media.append(urljoin(pn, fn + '.doc'))
                    media_captions.append(media_captions[id])
                elif fe == '.htm':
                    pdb.set_trace()

                media[id] = urljoin(pn, fn + fe)

                if fe in img_ext:
                    picnames.append(fn)

            for i in reversed(to_delete):
                del media[i]
                del media_captions[i]

            # Cycle pictures list and remove for doubles:
            to_delete = []
            for id, p in enumerate(pictures):
                for pn in picnames:
                    if os.path.basename(p).startswith(pn):
                        to_delete.append(id)

            for i in reversed(to_delete):
                del pictures[i]

            # append the pictures list to the media list
            media.extend(pictures)
            for p in pictures:
                media_captions.append(os.path.basename(p))

            for mid, m in enumerate(media):
                m = m.rstrip()
                filename = os.path.basename(m)
                media_url = urljoin(mysql_ip_address, road_db_path, MySQL_base_dir, m)
                media_url = 'http://' + media_url
                media_url = iri_to_uri(media_url)
                register_feature_media(f, media_url, filename, media_captions[mid])


def urljoin(*pieces):
    # function to join a list of strings into an url
    # redundant '/' are stripped, but no validation occurs
    return '/'.join(s.strip('/') for s in pieces)


def get_file_from_url(url):
    # Loads the file located at URL and saves it to a temporaryfile.
    # The temporary file is wrapped by the django File() class
    # and returned for further use.
    #
    # e.g.:
    #
    # im.file.save(file_name, get_file_from_url('http://www.some.url'))

    from django.core.files import File
    from django.core.files.temp import NamedTemporaryFile
    import urllib2

    file_temp = NamedTemporaryFile()
    try:
        file_temp.write(urllib2.urlopen(url, None, timeout=5).read())
    except Exception as detail:
        print "HTTP error: ", detail
        file_temp.close()
        return None

    file_temp.flush()

    return File(file_temp)


def import_all(get_media=True):
    import_reports(get_reports=get_media)
    import_features(get_media=get_media)
