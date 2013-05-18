# -*- coding: utf_8 -*-

# This code can be run with an empty database (with all tables and fields
# defined of course) to populate the database with initial data.
#
# To launch, change directory to the find_artek root directory (where
# manage.py is located) and issue the following commands:
#
# $ sudo python manage.py shell
#
# >>> import find_artek.publications.prepopulate as prepopulate
# >>> prepopulate.populate_db()
#
# To list all entries in the db's:
#
# >>> prepopulate.list_db_entries()

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

from django.contrib.gis.geos import GEOSGeometry

from django.contrib.auth.models import User
current_user = User.objects.get(username='thin')

from find_artek.publications.models import Person, PubType, Feature, Topic


def populate_db():
    """ Function to populate database with the data defined in this module """
    prepopulate_pubtype(pubtype_dict)
    prepopulate_person(persons_data)
    prepopulate_feature(features_data)
    prepopulate_topic(topics_data)


def list_db_entries():
    """ List entries in tables """
    print "------------------------------------"
    print " Content of Person Table "
    print "------------------------------------"
    for p in Person.objects.all():
        print p

    print " "

    print "------------------------------------"
    print " Content of PubType Table "
    print "------------------------------------"
    for p in PubType.objects.all():
        print p

    print " "

    print "------------------------------------"
    print " Content of feature Table "
    print "------------------------------------"
    for f in Feature.objects.all():
        print f


def prepopulate_pubtype(data_dict):
    """ Function to create entries and populate bibtex Publication Types """
    for pt, pt_dict in data_dict.items():
        ptype = PubType(type=pt.upper(), **pt_dict)
        ptype.save()


def prepopulate_person(data):
    """ Function to create entries and populate Person table """
    for pdict in data:
        p = Person(**pdict)
        p.created_by = current_user
        p.modified_by = current_user
        p.save()


def prepopulate_feature(data):
    """ Function to create entries and populate Person table """
    for fdict in data:
        f = Feature(**fdict)
        f.created_by = current_user
        f.modified_by = current_user
        f.save()


def prepopulate_topic(data):
    """ Function to create entries and populate Topic table """
    for fdict in data:
        f = Topic(**fdict)
        f.save()

# ----------------------------------------------------------------------------
# DATA SECTION - definiton of data to prepopulate tables
# ----------------------------------------------------------------------------

# -------------------------------------------
# DATA for PubType table
# -------------------------------------------

pubtype_dict = {
    'ARTICLE': dict(
        description = 'An article from a journal or magazine.',
        req_fields  = 'author, title, journal, year',
        opt_fields  = 'volume, number, pages, month, note, key',
        ),
    'BOOK': dict(
        description = 'A book with an explicit publisher.',
        req_fields  = 'author/editor, title, publisher, year',
        opt_fields  = 'volume/number, series, address, edition, month, note, key',
        ),
    'BOOKLET': dict(
        description = 'A work that is printed and bound, but without a named publisher or sponsoring institution.',
        req_fields  = 'title',
        opt_fields  = 'author, howpublished, address, month, year, note, key',
        ),
    'CONFERENCE': dict(
        description = 'The same as inproceedings, included for Scribe compatibility.',
        req_fields  = '',
        opt_fields  = '',
        ),
    'INBOOK': dict(
        description = 'A part of a book, usually untitled. May be a chapter (or section or whatever) and/or a range of pages.',
        req_fields  = 'author/editor, title, chapter/pages, publisher, year',
        opt_fields  = 'volume/number, series, type, address, edition, month, note, key',
        ),
    'INCOLLECTION': dict(
        description = 'A part of a book having its own title.',
        req_fields  = 'author, title, booktitle, publisher, year',
        opt_fields  = 'editor, volume/number, series, type, chapter, pages, address, edition, month, note, key',
        ),
    'INPROCEEDINGS': dict(
        description = 'An article in a conference proceedings.',
        req_fields  = 'author, title, booktitle, year',
        opt_fields  = 'editor, volume/number, series, pages, address, month, organization, publisher, note, key',
        ),
    'MANUAL': dict(
        description = 'Technical documentation.',
        req_fields  = 'title',
        opt_fields  = 'author, organization, address, edition, month, year, note, key',
        ),
    'MASTERSTHESIS': dict(
        description = 'A Master''s thesis.',
        req_fields  = 'author, title, school, year',
        opt_fields  = 'type, address, month, note, key',
        ),
    'MISC': dict(
        description = 'For use when nothing else fits.',
        req_fields  = 'none',
        opt_fields  = 'author, title, howpublished, month, year, note, key',
        ),
    'PHDTHESIS': dict(
        description = 'A Ph.D. thesis.',
        req_fields  = 'author, title, school, year',
        opt_fields  = 'type, address, month, note, key',
        ),
    'PROCEEDINGS': dict(
        description = 'The proceedings of a conference.',
        req_fields  = 'title, year',
        opt_fields  = 'editor, volume/number, series, address, month, publisher, organization, note, key',
        ),
    'TECHREPORT': dict(
        description = 'A report published by a school or other institution, usually numbered within a series.',
        req_fields  = 'author, title, institution, year',
        opt_fields  = 'type, number, address, month, note, key',
        ),
    'UNPUBLISHED': dict(
        description = 'A document having an author and title, but not formally published.',
        req_fields  = 'author, title, note',
        opt_fields  = 'month, year, key',
        ),
    'STUDENTREPORT': dict(
        description = 'A student report, e.g. handed in as part of the evaluation of participation in a course. [Not standard BIBTEX!]',
        req_fields  = 'author, title, school, year',
        opt_fields  = 'type, address, month, note, key',
        ),
}


# -------------------------------------------
# DATA for Person table
# -------------------------------------------

persons_data = (
    {
        "first_relaxed":   "t",
        "last_relaxed":    "ingeman-nielsen",
        "first":           "Thomas",
        "middle":          "",
        "prelast":         "",
        "last":            "Ingeman-Nielsen",
        "lineage":         "",
        "pre_titulation":  "",
        "post_titulation": "",
        "position":        "Associate Professor",
        "initials":        "TIN",
        "institution":     "Technical University of Denmark",
        "department":      "Department of Civil Engineering",
        "address_1":       "Arctic Technology Centre",
        "address_2":       "Kemitorvet, B. 204",
        "zip_code":        "DK-2800",
        "town":            "Kgs. Lyngby",
        "state":           "",
        "country":         "Denmark",
        "phone":           "+45 45252251",
        "cell_phone":      "+45 61858075",
        "email":           "tin@byg.dtu.dk",
        "id_number":       "v11189",
        "note":            "",
        "quality":         0
    },
    {
        "first_relaxed":   "a",
        "last_relaxed":    "villumsen",
        "first":           "Arne",
        "middle":          "",
        "prelast":         "",
        "last":            "Villumsen",
        "lineage":         "",
        "pre_titulation":  "",
        "post_titulation": "",
        "position":        "Professor",
        "initials":        "AV",
        "institution":     "Technical University of Denmark",
        "department":      "Department of Civil Engineering",
        "address_1":       "Arctic Technology Centre",
        "address_2":       "Kemitorvet, B. 204",
        "zip_code":        "DK-2800",
        "town":            "Kgs. Lyngby",
        "state":           "",
        "country":         "Denmark",
        "phone":           "",
        "cell_phone":      "",
        "email":           "av@byg.dtu.dk",
        "homepage":        "",
        "id_number":       "",
        "quality":         0
    },
        {
        "first_relaxed":   "n",
        "last_relaxed":    "foged",
        "first":           "Niels",
        "middle":          "",
        "prelast":         "",
        "last":            "Foged",
        "lineage":         "",
        "pre_titulation":  "",
        "post_titulation": "",
        "position":        "Professor Emeritus",
        "initials":        "NF",
        "institution":     "Technical University of Denmark",
        "department":      "Department of Civil Engineering",
        "address_1":       "Nordvej, B. 119",
        "address_2":       "",
        "zip_code":        "DK-2800",
        "town":            "Kgs. Lyngby",
        "state":           "",
        "country":         "Denmark",
        "phone":           "",
        "cell_phone":      "",
        "email":           "nf@byg.dtu.dk",
        "homepage":        "",
        "id_number":       "",
        "quality":         0
    },
        {
        "first_relaxed":   "a",
        "last_relaxed":    "joergensen",
        "first":           "Anders",
        "middle":          "Stuhr",
        "prelast":         "",
        "last":            "Jørgensen",
        "lineage":         "",
        "pre_titulation":  "",
        "post_titulation": "",
        "position":        "Assistant Professor",
        "initials":        "ASJ",
        "institution":     "Technical University of Denmark",
        "department":      "Department of Civil Engineering",
        "address_1":       "Kemitorvet, B. 204",
        "address_2":       "",
        "zip_code":        "DK-2800",
        "town":            "Kgs. Lyngby",
        "state":           "",
        "country":         "Denmark",
        "phone":           "",
        "cell_phone":      "",
        "email":           "asj@byg.dtu.dk",
        "homepage":        "",
        "id_number":       "",
        "quality":         0
    },
    {
        "first_relaxed":   "t",
        "last_relaxed":    "ingeman-nielsen",
        "first":           "Tobias",
        "middle":          "",
        "prelast":         "",
        "last":            "Ingeman-Nielsen",
        "lineage":         "",
        "pre_titulation":  "",
        "post_titulation": "",
        "position":        "",
        "initials":        "THIN",
        "institution":     "",
        "department":      "",
        "address_1":       "",
        "address_2":       "",
        "zip_code":        "",
        "town":            "",
        "state":           "",
        "country":         "",
        "phone":           "",
        "cell_phone":      "",
        "email":           "",
        "id_number":       "",
        "note":            "For testing purposes",
        "quality":         0
    },
)


# -------------------------------------------
# DATA for Feature table
# -------------------------------------------

features_data = (
    {
        "name":          "Sisimiut",
        "type":          "OTHER",
        "area":          "Sisimiut",
        "description":   "Test point",
        "points":      GEOSGeometry('SRID=4326;MULTIPOINT( -53.672225 66.938887 )'),
    },
)


# -------------------------------------------
# DATA for Topics table
# -------------------------------------------

topics_data = (
    {"topic":  u"Infrastruktur", },
    {"topic":  u"Miljø", },
    {"topic":  u"Energi", },
    {"topic":  u"Byggeri", },
)
