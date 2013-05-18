# -*- coding: utf_8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"


import xlrd
import os.path
import pdb
import datetime
import dateutil.parser
import chardet

from pybtex.database import Person as pybtexPerson

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.shortcuts import get_object_or_404
from django.contrib import messages

#from find_artek.publications.models import Publication, Person, Feature, PubType, Authorship
from find_artek.publications import models, person_utils


import logging
logger = logging.getLogger(__name__)



def xlsx_pubs(filepath, user=None):
    current_user = user  # User.objects.get(username='thin')

    wb = xlrd.open_workbook(os.path.join(settings.MEDIA_ROOT, filepath), formatting_info=False)

    for s in wb.sheets():
        # ignore empty sheets
        if s.ncols == 0 and s.nrows == 0:
            continue

        # Make list of column names
        col_names = []
        for col in range(s.ncols):
            if s.cell_type(0, col) == 1:
                col_names.append(s.cell_value(0, col).strip())
            else:
                col_names.append(s.cell_value(0, col))

        # ignore sheets that don't provide a title column
        if not (col_names.index('title') or col_names.index('booktitle')):
            continue

        number_col = col_names.index('number')

        # iterate over report entries
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

            # extract the m2m and foreignkey entries
            m2m_dict = dict()
            for k in kwargs.keys():
                if k in ['author', 'editor', 'supervisor', 'keywords',
                         'topic', 'URLs', 'type', 'journal']:
                    m2m_dict[k] = kwargs.pop(k)

            # temporary until authentication is implemented
            kwargs['created_by'] = current_user
            kwargs['modified_by'] = current_user

            # Handle the publication type
            kwargs['type'] = models.PubType.objects.get(type=m2m_dict.pop('type', 'STUDENTREPORT'))

            # Handle the publication type
            kwargs['topics'] = models.Topic.objects.get(topic=m2m_dict.pop('topic', None))
            if kwargs['topics'] is None:
                kwargs.pop('topics')

            # handle journal if present
            if 'journal' in m2m_dict and m2m_dict['journal']:
                kwargs['journal'] = models.Journal.objects.get(type=m2m_dict.pop('journal'))

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
            if created:
                print "Publication registered!"
                # Handle authors, editors, supervisors etc. here!
                for f in ['author', 'supervisor', 'editor']:
                    names = m2m_dict.pop(f, None)
                    add_persons_to_publication(names, instance, f, current_user)

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

                if not updated:
                    print "No attributes updated!"
                instance.save()

                if m2m_dict:
                    # handle authors, editors, supervisors etc. here!
                    for f in ['author', 'supervisor', 'editor']:
                        names = m2m_dict.pop(f, None)
                        if not getattr(instance, f):
                            # Add persons if no persons are registered already
                            add_persons_to_publication(names, instance, f, current_user)

                instance.save()


def add_persons_to_publication(names, pub, field, user):
    # return if no names passed
    if not names or not names.strip():
        return

    if pub.author.all():
        # Skip if authors are already registered.
        return

    #define pubplication-person through-table
    through_tbl = getattr(models, field[0].upper() + field[1:] + 'ship')

    kwargs = dict()

    # Parse author names to a list
    kwargs[field] = [pybtexPerson(s) for s in
                     person_utils.parse_name_list(names) if s]

    # Cycle through persons
    for id, pers in enumerate(kwargs[field]):
        if not (hasattr(pers, 'first') and hasattr(pers, 'last')):
            raise ValueError("Missing parts of name, cannot create database entry")

        print "   Processing person {0}: {1}".format(id, pers)

        exact_match = False
        multiple_match = False
        relaxed_match = False

        # Get existing persons using relaxed naming
        p, match = person_utils.get_person(person=pers)

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
        p = person_utils.create_person_from_pybtex(person=pers, user=user)

        if p:
            # add the author to the author-relationship

            tmp = through_tbl(person=p[0],
                              publication=pub,
                              author_id=id,
                              exact_match=exact_match,
                              multiple_match=multiple_match,
                              relaxed_match=relaxed_match)
            tmp.save()



def xlsx_features(filepath, user=None):

    xlsxmessages = []  # Will hold tuples of e.g. (messages.INFO, "info text")

    current_user = user  # User.objects.get(username='thin')

    wb = xlrd.open_workbook(os.path.join(settings.MEDIA_ROOT, filepath))

    s = wb.sheet_by_name('Features')

    if not s:
        logger.error("Excel file does not hold a sheet by the name 'Features'. Import aborted.")
        xlsxmessages.append((messages.ERROR, "Excel file does not hold a sheet by the name 'Features'. Import aborted."))
        return (False, xlsxmessages)

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

    for cn in col_names:
        if cn not in sheet_col_names:
            msg = "Excel feature col_name problem: " + cn + " missing in file. Import aborted."
            logger.error(msg)
            xlsxmessages.append((messages.ERROR, msg))
            return (False, xlsxmessages)

    feature_list = []  # will hold list of unique feature numbers from Feature# column

    # iterate over report entries
    for row in range(1, s.nrows):

        # Get the feature number
        fnum = s.cell_value(row, col_names.index('Feature#'))
        if not fnum:
            # if no feature number is given, skip the line
            continue

        try:
            # Try to format the feature number as a normal number format
            fnum = "{0:g}".format(fnum)
        except:
            pass

        # If this is a new feature number, get all properties
        if fnum and fnum not in feature_list:
            #print " "
            #print "Processing feature {0}".format(fnum)

            # Add the feature number to the list
            feature_list.append(fnum)

            # create dictionary of field:value pairs
            kwargs = dict()

            kwargs['comment'] = s.cell_value(row, col_names.index('Comment'))
            kwargs['name'] = s.cell_value(row, col_names.index('Name'))
            kwargs['type'] = s.cell_value(row, col_names.index('Feature_type'))
            kwargs['date'] = s.cell_value(row, col_names.index('Date'))
            orig_date = kwargs['date']
            date_ctype = s.cell_type(row, col_names.index('Date'))   # get the cell type e.g. XL_CELL_TEXT, XL_CELL_NUMBER, XL_CELL_DATE
            if kwargs['date']:
                if date_ctype == 3:
                    # This is a date type cell, use xlrd's date conversion
                    kwargs['date'] = xlrd.xldate_as_tuple(kwargs['date'], wb.datemode)
                    kwargs['date'] = datetime.datetime(*kwargs['date']).date()
                else:
                    # This is a number or text type
                    try:
                        # Try parsing the expected date format
                        kwargs['date'] = datetime.datetime.strptime(kwargs['date'], '%Y-%m-%d').date()
                    except:
                        # if error, try using dateutils parser
                        kwargs['date'] = dateutil.parser.parse(kwargs['date'],
                                                               dayfirst=True,
                                                               yearfirst=True,
                                                               default=datetime.date(1900, 1, 1),
                                                               fuzzy=True)
                        # Add warning to messages
                        msg = "Feature ({1}) '{0}': Unexpected date format, parsed date may be wrong ('{2}' == '{3}' ??)".format(kwargs['name'], fnum, orig_date, kwargs['date'])
                        xlsxmessages.append((messages.WARNING, msg))

                        # Add warning to feature comment.
                        if not kwargs['comment']:
                            kwargs['comment'] += '\r\n'
                        kwargs['comment'] += '[Date of feature may be wrong!]'

            kwargs['direction'] = s.cell_value(row, col_names.index('Direction'))
            kwargs['description'] = s.cell_value(row, col_names.index('Description'))
            kwargs['pos_quality'] = s.cell_value(row, col_names.index('Pos_quality'))
            kwargs['created_by'] = current_user
            kwargs['modified_by'] = current_user

            # Create feature
            f = models.Feature(**kwargs)
            fmsg = [messages.INFO, "Feature ({1}) '{0}' created".format(f.name, fnum)]

            if s.cell_value(row, col_names.index('Geometry_type')) == 'point':
                # This is a point we can finish the handling here
                x, y = (s.cell_value(row, col_names.index('UTMX/LON')),
                        s.cell_value(row, col_names.index('UTMY/LAT')))
                fWKT = "MULTIPOINT({0} {1})".format(x, y)
                srid = int(s.cell_value(row, col_names.index('SRID')))
                geom = GEOSGeometry(fWKT, srid=srid)
                f.points = geom

            elif s.cell_value(row, col_names.index('Geometry_type')) == 'line':
                # This is a line, we must expect more segments to be added
                msg = "Line geometry not implemented. No coordinates added for feature ({1}) '{0}'".format(f.name, fnum)
                xlsxmessages.append((messages.WARNING, msg))

            elif s.cell_value(row, col_names.index('Geometry_type')) == 'polygon':
                # This is a polygon, we must expect more segments to be added
                msg = "Line geometry not implemented. No coordinates added for feature ({1}) '{0}'".format(f.name, fnum)
                xlsxmessages.append((messages.WARNING, msg))

            """Here we should handle multiple rows with the same feature#.
            if point, a new point should be added to multipoint geometry
            if line, a new point should be added to the line geometry
            if polygon, a new point should be added to the polygon geometry
            """

            f.save()

            # Find related publication:
            pub_id = s.cell_value(row, col_names.index('Publication_ID'))
            if pub_id:
                pub_id = int(pub_id)
                try:
                    p = models.Publication.objects.get(pk=pub_id)
                except:
                    p = None
                    fmsg[0] = messages.WARNING
                    fmsg[1] += ", could not add to publication {0} - it does not exist!".format(pub_id)

                #get_object_or_404(models.Publication, pk=pub_id)
            else:
                p = None

            # add it to m2m relationship
            if p and not p in f.publications.all():
                f.publications.add(p)
                fmsg[1] += " and added to publication {0}".format(p.number)

            f.save()
            xlsxmessages.append(fmsg)

    return (len(feature_list), xlsxmessages)
