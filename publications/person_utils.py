# -*- coding: utf_8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"
import ldap
import pdb
import re
from unidecode import unidecode
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages

from pybtex.database import Person as pybtexPerson
from pybtex.bibtex import utils as pybtex_utils     # functions for splitting strings in a tex aware fashion etc.

from find_artek import settings
from publications import models
from publications.utils import dk_unidecode

from publications.utils import get_tag, remove_tags

logger = logging.getLogger(__name__)
logger.debug('TEST: loaded the person_utils.py module')

re_name_sep_words = re.compile(r'\s*[;&\n]+\s*|\s+and\s+|\s+AND\s+|\s+og\s+|\s+OG\s+')
re_space_sep = re.compile(r'(?<!,)\s(?!,)')  # used to find spaces that are not connected to commas


# ----------------------------------------------------------------------------
#  Name processing and conversion functions
# ----------------------------------------------------------------------------

def parse_name_list(names):
    # function to split a list of names, in individual persons,
    # taking into account many different types of separators:
    # last1, first1, last2, first2 & last3, first3
    # first1 last1, first2 last2 & first3 last3
    # and many more...

    def comma_parsing(names):
        # stupid way to strip off all whitespace and commas at ends of string
        names.strip().strip(',').strip()
        # Count number of commas
        comma_count = names.count(',')
        # Check to see if names has space separators not connected to commas
        space_count = len(re.findall(re_space_sep, names))

        if space_count and comma_count:
            # we have both comma and space
            # list types could be:
            # 1) first (middle) (von) last, first last etc.     => split at comma
            # 2) (von) last, first middle                       => no split, everything is one name
            # 3) (von) last, first middle, last, first etc.     => split at every second comma

            # how to determine which is which?
            # a) split at commas
            # b) first term has space and starts with lowercase word => 2) or 3) split at every second comma
            # c) first term has space and starts with uppercase word => 1) split at all commas

            # split at commas
            name_list = names.split(',')
            name_list = [n.strip() for n in name_list]  # clean up

            if name_list[0].find(' ') > -1:
                # first term has space
                if not name_list[0][0].isupper():
                    # Situation 2) or 3) with von, split at every second comma
                    # which means rejoin pairwise...
                    span = 2
                    name_list = [', '.join(name_list[i:i + span]) for i in range(0, len(name_list), span)]
                else:
                    # Situation 1), split this at all commas, thus do nothing more...
                    pass
            else:
                # first term has no spaces, thus must be situation 2) or 3) without von
                # split at every second comma which means rejoin pairwise...
                span = 2
                name_list = [', '.join(name_list[i:i + span]) for i in range(0, len(name_list), span)]

        elif comma_count:
            # We have no spaces not adjacent to commas.
            # all names and parts must be comma separated.
            # list type must be: last, first, last, first
            nl2 = names.split(',')
            name_list = [', '.join([a, b]) for a, b in zip(nl2[::2], nl2[1::2])]
        else:
            # we have no commas, this must be a single name
            name_list = [names]

        return name_list

    name_list = []
    [name_list.extend(comma_parsing(n)) for n in re_name_sep_words.split(names)]

    return name_list


def get_relaxed_name_kwargs(string='', person=None):
    if string:
        # parse name string
        person = pybtexPerson(string)

    kwargs = {}

    if person:
        # match first initial and last name lower case, no special characters
        if person.first():
            initial = pybtex_utils.bibtex_first_letter(person.first()[0])
            initial = dk_unidecode(initial.decode('latex')).lower()
        else:
            initial = ''

        if person.last():
            last = dk_unidecode(u' '.join(person.last()).decode('latex')).lower()
        else:
            last = ''

        kwargs = dict(first_relaxed=initial,
                      last_relaxed=last)

    return kwargs


def get_full_name_kwargs(string='', person=None, initials='', id_number=''):
    """Creates a dictionary with the fields:
    'first', 'middle', 'last', 'prelast' and 'lineage'
    (and possibly 'initials' and 'person_id')

    Only non-empty fields will be included in the dictionary.
    The fields will be unicode strings.

    """
    if string:
        # parse name string
        person = pybtexPerson(string)

    # Define possible name parts to match
    names = ['first', 'middle', 'last', 'prelast', 'lineage']
    kwargs = {}

    if person:
        # loop through name parts
        for n in names:
            part = getattr(person, n)()
            if part:
                # If the name part is not empty
                # get the unicode representation ...
                part = u" ".join(part).decode('latex')
                # ... and include it in query
                kwargs[n] = part

    if initials:
        kwargs['initials'] = initials

    if id_number:
        kwargs['id_number'] = id_number


    return kwargs


def fullname(person):
    """return name as string from pybtex person instance
    First Middle von Last, Jr

    """
    if isinstance(person, pybtexPerson):
        full_name = ' '.join(person.first() + person.middle() +
                             person.prelast() + person.last())
        jr = ' '.join(person.lineage())
        return ', '.join(part for part in (full_name, jr) if part)
    elif isinstance(person, models.Person):
        return unicode(person)
    elif isinstance(person, dict):
        full_name = ' '.join([person[k] for k in ['first', 'middle', 'prelast', 'last'] if k in person])

        jr = ' '.join(person.get('lineage', ""))
        return ', '.join(part for part in (full_name, jr) if part)


def create_pybtex_person(*args, **kwargs):
    """Function is just a wrapper for the pybtexPerson class instantiation.

    """
    return pybtexPerson(*args, **kwargs)


# ----------------------------------------------------------------------------
#  Database interaction
# ----------------------------------------------------------------------------


def create_person_from_pybtex(person=None, user=None, save=True):
    """Create Person object from pybtex instance

    """
    if not person:
        raise ValueError('No person information passed!')

    if not user:
        raise ValueError('No user information passed!')

    # define name parts
    kwargs = get_full_name_kwargs(person=person)

    if not kwargs:
        raise ValueError('The pybtex person passed, contained no information')

    if kwargs.get('first', None):
        initial = pybtex_utils.bibtex_first_letter(person.first()[0])
        kwargs['first_relaxed'] = dk_unidecode(initial.decode('latex')).lower()
    if kwargs.get('last', None):
        kwargs['last_relaxed'] = dk_unidecode(u' '.join(person.last()).decode('latex')).lower()

    p = models.Person(**kwargs)

    p.created_by = user
    p.modified_by = user

    if save:
        p.save()

    return [p]


def choose_person(queryset, person, user):
    """Function to ask for user input to choose among multiple person matches

    Input arguments:
    queryset:   list of prows matching the search
    person:     Pybtex person instance, giving the correct full name.
    returns None or a single row/entry,

    """
    if isinstance(person, pybtexPerson) or isinstance(person, models.Person):
        name = fullname(person)
    else:
        name = person

    print ' '
    if len(queryset) > 1:
        print 'Multiple matches for person: {0}'.format(name)
        print 'Please choose correct entry:'
    else:
        print 'Relaxed match for person: {0}'.format(name)
        print 'Please choose:'

    for id, q in enumerate(queryset):
        print '   {0}:\t{1}'.format(id, fullname(q))

    print '   {0}:\tCreate new person'.format('N')  # len(queryset))

    pid = -1
    while pid < 0 or pid > len(queryset):
        pid = raw_input('Enter choice: ')
        try:
            pid = int(pid)
        except:
            if hasattr(pid, 'lower') and pid.lower() == 'n':
                pid = len(queryset)
            else:
                pid = -1

    print ' '

    if pid == len(queryset):  # If we chose to create new person
        if isinstance(person, pybtexPerson):
            return create_person_from_pybtex(person, user)
        else:
            raise ValueError('person argument is not a pybtexPerson instance!')
    else:    # Otherwise return the chosen query-result
        return [queryset[pid]]



def add_persons_to_publication(names, pub, field, user):
    """
    """
    personmessages = []  # Will hold tuples of e.g. (messages.INFO, "info text")

    # return if no names passed
    if not names or not names.strip():
        return personmessages

    #define pubplication-person through-table
    through_tbl = getattr(models, field[0].upper() + field[1:] + 'ship')

    person_entity_list = [s for s in parse_name_list(names) if s]

    for id, s in enumerate(person_entity_list):
        multiple_match = False
        exact_match = False
        relaxed_match = False

        print "Processing person: {0}".format(s.encode('ascii', 'replace'))
        p, match = get_person_from_string(s, user, save=False)

        if p:
            print p
            if len(p) > 1:
                # More than one exact return, flag multiple_match
                multiple_match = True
            if match in ['db_exact']:
                # if exact match flag exact_match
                exact_match = True
            elif match == 'db_relaxed':
                # if relaxed match flag relaxed_match
                relaxed_match = True
            elif match == 'ldap':
                p[0].save()
                msgstr = "Person '{0}' [id:{1}] imported from DTU directory.".format(p[0], p[0].id)
                personmessages.append((messages.INFO, msgstr))

            if match in ['db_exact', 'db_relaxed']:
                # Create new database person entity
                p = get_person(string=s)
                p = models.Person(name=s)
                p.created_by = user
                p.modified_by = user
                p.save()
                p = [p]
                msgstr = "Person '{0}' [id:{1}] created".format(p[0], p[0].id)
                personmessages.append((messages.INFO, msgstr))

            # add the person to the author/supervisor/editor-relationship
            p[0].save()
            tmp = through_tbl(person=p[0],
                              publication=pub,
                              exact_match=exact_match,
                              multiple_match=multiple_match,
                              relaxed_match=relaxed_match,
                              **{field+'_id': id})
            tmp.save()
        else:
            msgstr = "Person '{0}' could not be added automatically as {1}. You may add manually later.".format(s, field)
            personmessages.append((messages.WARNING, msgstr))

    return personmessages


def get_person_from_string(s, user, save=False):
    """Parses a string and tries to find the person either in database or
    through ldap, depending on the information in the string.

    If string has tag:
        if tag is 'ldap', get person from ldap import (studynumber or initials)
        if tag is number (not 0), get person from database
        if tag is 0, create new person from name
            set appropriate match flags
    else:
        if studynumber: get person from database or ldap
        if initials: get person from database or ldap
        else: check for exact or relaxed matches in database
            create a new person, and set appropriate match flags.

    match flags:
    ldap:       matched in ldap directory
    db_exact:   matches are exact and found in database
    db_relaxed: relaxed matches found in database
    new:        no matches found in database, person created from name (but not committed)
    pid:        match based on unique person id

    It is safe to make relations to 'pid' mathces. 'ldap' and 'new' matches must be committed
    before relations can be made to these (and that should be safe too).
    db_relaxes and db_exact matches should not be used for making relations, only to set
    appropriate match flags on the relation.
    """

    msg = []

    pid = get_tag(s, 'id')  # get the value of "[id:147]" tags, get_tag will return 147.
    s = remove_tags(s)

    if pid == 'ldap':
        if re.search('[a-zA-Z]{1}[0-9]{6}', s):
            # This is a study number...
            p, match = get_from_studynumber(s, user, force_ldap=True)

        elif len(re.split('[^A-Za-z]',s)) == 1:
            # this is an entry with only consecutive letters = initials
            p, match = get_from_initials(s, user, force_ldap=True)


    elif pid:
        # check that person with id exists in database
        # should not be included in choice-list
        # or should be included with an nice OK icon
        try:
            p = models.Person.objects.get(id=pid)
            match = 'pid'
            p = [p]
        except ObjectDoesNotExist:
            p = None
            match = None
    else:
        # No id-tag, thus make choice
        # First get possible matches from database

        if re.search('[a-zA-Z]{1}[0-9]{6}', s):
            # This is a study number...
            print "looking for study number"
            p, match = get_from_studynumber(s, user)

        elif len(re.split('[^A-Za-z]',s)) == 1:
            # this is an entry with only consecutive letters = initials
            p, match = get_from_initials(s, user)

        else:
            # otherwise... this is just a name...
            p, match = get_from_namestring(s, user)

        if save and p:
            for pers in p:
                pers.save()

    return p, match


def get_from_studynumber(s, user, force_ldap=False):
    """Get or create person from study number. Will use ldap lookup if possible."""

    p = None

    if not force_ldap:
        # See if it is in our own database
        p, match = get_person(id_number=s, exact=True)
    if not p:
        # Now see if it is in LDAP directory
        result = find_ldap_person(name=s)
        if result:
            p = get_or_create_person_from_ldap(person=result[0],
                                                           user=user, save=False)
            match = "ldap"
        else:
            p = None
            match = None

    return p, match


def get_from_initials(s, user, force_ldap=False):
    """Get or create person from initials. Will use ldap lookup if possible."""

    p = None

    if not force_ldap:
        # See if it is in our own database
        p, match = get_person(initials=s, exact=True)
    if not p:
        # Now see if it is in LDAP directory
        result = find_ldap_person(initials=s)
        if result:
            p = get_or_create_person_from_ldap(person=result[0],
                                               user=user, save=False)
            match = "ldap"
        else:
            p = None
            match = None

    return p, match


def get_from_tag(s, user):
    """Get or create person from tag value."""
    p = None
    match = None
    s = s.strip()
    pid = get_tag(s, 'id')

    if pid == '0':
        # tag [id:0]
        # create new person
        # ...
        s = remove_tags(s)
        if s:
            p = models.Person(name=s)
            p.created_by = user
            p.modified_by = user
            p = [p]
            match = "new"

    elif pid:
        # tag [id:XX] where xx is supposed to be integer.
        # get specified person and add to authorship
        try:
            p = models.Person.objects.get(id=pid)
            match = "pid"
        except ObjectDoesNotExist:
            match = None

    return p, match


def get_from_namestring(s, user):
    """Get or create person from namestring."""

    person = pybtexPerson(s)

    if not (person.first() and person.last()):
        p = None
        match = None
    else:
        # Get existing persons using relaxed naming
        p, match = get_person(person=person)

    return p, match


def get_person(string='', person=None, initials='', person_id='', id_number='', exact=False, relaxed=False):
    """Searches Django database (not ldap) for matches against the arguments passed,
    ignores empty parts of name.
    If exact argument is True, only exact matches are returned

    returns tuple of queryset and string flag indicating exact or relaxed fit.

    kwargs:
    exact=True    Force only exact match
    relaxed=True  Force return of both exact and relaxed match
    exact=False and relaxed=False    Return only exact, if existing, otherwise relaxed.

    """
    if not string and not person and not initials and not id_number:
        return ([], '')

    kwargs = get_full_name_kwargs(string, person, initials, id_number)
    print kwargs
    match = 'db_exact'
    p = models.Person.objects.filter(**kwargs)

    if not p:
        print "   No Exact match found."
        match = None

    if not exact:
        if not p or relaxed:
            # No exact match - we'll try relaxed match
            print '   Trying relaxed match...'
            kwargs = get_relaxed_name_kwargs(string, person)
            match = 'db_relaxed'
            p = models.Person.objects.filter(**kwargs)

        if not p and relaxed:
            # No relaxed match
            print '   No relaxed match found.'

    # return result of query (may contain more than one entry)
    return (p, match)



# ----------------------------------------------------------------------------
#  LDAP RELATED
# ----------------------------------------------------------------------------



# AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=DTUBaseUsers,dc=win,dc=dtu,dc=dk",
#                                    ldap.SCOPE_SUBTREE, "(name=%(user)s)")

# AUTH_LDAP_GROUP_SEARCH = LDAPSearch("dc=win,dc=dtu,dc=dk", ldap.SCOPE_SUBTREE, "(objectClass=group)")
# AUTH_LDAP_GROUP_TYPE = ActiveDirectoryGroupType(name_attr="cn")


# AUTH_LDAP_USER_ATTR_MAP = {"first_name": "givenName", "last_name": "sn",
#                            "email": "mail"}



def find_ldap_person(**kwargs):
    """Search LDAP for user with the attributes specified in kwargs.
    Returns a LDAP user instance.

    """
    if not 'django_auth_ldap.backend.LDAPBackend' in settings.AUTHENTICATION_BACKENDS:
        return []

    # 1) Possibly make translation of attribute names?
    # 2) Generate search string
    searchstr = ''
    for k,v in kwargs.items():
        searchstr += '({0}={1})'.format(k,v)
    if len(kwargs.keys()) >= 1:
        searchstr = '(&{0})'.format(searchstr)

    # 3) Open connection and bind
    con = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
    con.simple_bind_s(settings.AUTH_LDAP_BIND_DN,
                      settings.AUTH_LDAP_BIND_PASSWORD)

    # 4) Perform the search
    try:
        result = con.search_s("ou=DTUBaseUsers,dc=win,dc=dtu,dc=dk",
                              ldap.SCOPE_SUBTREE, searchstr)
    except:
        result = []
        logger.warning('ldap search for nested groups failed!')

    # 5) unbind
    con.unbind()

    # 6) Return list of users matching the search criteria
    return result


def get_or_create_person_from_ldap(person=None, user=None, save=True):
    """Create Person object from pybtex instance

       person is a tuple returned from an ldap search where the first item
       is the distinguished name string, and the second item is a dictionary
       of attributes.

    """
    if not person:
        raise ValueError('No person information passed!')

    if not user:
        raise ValueError('No user information passed!')

    pdict = result2unicode(person[1])


    # define name parts
    name = u'{0}, {1}'.format(pdict['sn'][0],pdict['givenName'][0])

    # Get the different name parts
    kwargs = get_full_name_kwargs(string=name)
    kwargs.update(get_relaxed_name_kwargs(string=name))

    if pdict['company'][0] == 'Studerende':
        kwargs['position'] = 'student'
        kwargs['id_number'] = pdict['name'][0]
    elif 'title' in pdict.keys():
        kwargs['position'] = pdict['title'][0]
        kwargs['id_number'] = pdict['employeeID'][0]
        kwargs['department'] = pdict['department'][0]

    if 'initials' in pdict.keys():
        kwargs['initials'] = pdict['initials'][0]


    if not kwargs:
        raise ValueError('The person record passed, contained no information')

    # Test if it is already there, based on id_number or initials
    kwgs = kwargs.get('id_number', '')
    p = models.Person.objects.filter(**kwargs)
    if not p:
        kwgs = kwargs.get('initials', '')
        p = models.Person.objects.filter(**kwargs)

    if not p:
        p = models.Person(**kwargs)

        p.created_by = user
        p.modified_by = user

        if save:
            p.save()
    else:
        p = p[0]  # pick the first if multiple mathces... there shouldn't be multiple!

    return [p]



def create_person_from_ldap(person=None, user=None):
    """Create Person object from pybtex instance

       person is a tuple returned from an ldap search where the first item
       is the distinguished name string, and the second item is a dictionary
       of attributes.

    """
    if not person:
        raise ValueError('No person information passed!')

    if not user:
        raise ValueError('No user information passed!')

    pdict = person[1]

    # define name parts
    name = '{0}, {1}'.format(pdict['sn'][0],pdict['givenName'][0])

    # Get the different name parts
    kwargs = get_full_name_kwargs(string=name)
    kwargs.update(get_relaxed_name_kwargs(string=name))

    if pdict['company'][0] == 'Studerende':
        kwargs['position'] = 'student'
        kwargs['id_number'] = pdict['name'][0]
    elif 'title' in pdict.keys():
        kwargs['position'] = pdict['title'][0]
        kwargs['id_number'] = pdict['employeeID'][0]
        kwargs['department'] = pdict['department'][0]

    if 'initials' in pdict.keys():
        kwargs['initials'] = pdict['initials'][0]


    if not kwargs:
        raise ValueError('The person record passed, contained no information')

    p = models.Person(**kwargs)

    p.created_by = user
    p.modified_by = user

    p.save()

    return [p]


# ----------------------------------------------------------------------------
#  Utility functions
# ----------------------------------------------------------------------------


def result2unicode(pdict):
    result = dict()
    for k,v in pdict.items():
        try:
            result[k] = [unicode(s, 'UTF-8') for s in v]
        except:
            result[k] = v

    return result
