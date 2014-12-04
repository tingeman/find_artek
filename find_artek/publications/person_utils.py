# -*- coding: utf_8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

import pdb
import re
from unidecode import unidecode

from pybtex.database import Person as pybtexPerson
from pybtex.bibtex import utils as pybtex_utils     # functions for splitting strings in a tex aware fashion etc.

from find_artek.publications import models
from find_artek.publications.utils import dk_unidecode

re_name_sep_words = re.compile(r'\s*[;&\n]+\s*|\s+and\s+|\s+AND\s+|\s+og\s+|\s+OG\s+')
re_space_sep = re.compile(r'(?<!,)\s(?!,)')  # used to find spaces that are not connected to commas


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


def get_person(string='', person=None, initials='', person_id='', id_number='', exact=False, relaxed=False):
    """Match exact name as passed (ignore empty parts of name)
    If exact argument is True, only exact matches are returned

    returns tuple of queryset and string flag indicating exact or relaxed fit.

    kwargs:
    exact=True    Force only exact RESTRUCTUREDTEXT_FILTER_SETTINGS
    relaxed=True  Force return of both exact and relaxed RESTRUCTUREDTEXT_FILTER_SETTINGS
    exact=False and relaxed=False    Return only exact, if existing, otherwise relaxed.

    """
    if not string and not person and not initials and not id_number:
        return ([], '')

    kwargs = get_full_name_kwargs(string, person, initials, id_number)
    match = 'exact'
    p = models.Person.objects.filter(**kwargs)

    if not p:
        print "   No Exact match found."

    if not exact:
        if not p or relaxed:
            # No exact match - we'll try relaxed match
            print '   Trying relaxed match...'
            kwargs = get_relaxed_name_kwargs(string, person)
            match = 'relaxed'
            p = models.Person.objects.filter(**kwargs)

        if not p and relaxed:
            # No relaxed match
            print '   No relaxed match found.'

    # return result of query (may contain more than one entry)
    return (p, match)


def create_person_from_pybtex(person=None, user=None):
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


    
    
    
def add_persons_to_publication(names, pub, field, user):
    """
    """
    personmessages = []  # Will hold tuples of e.g. (messages.INFO, "info text")
    
    # return if no names passed
    if not names or not names.strip():
        return personmessages
    
    #define pubplication-person through-table
    through_tbl = getattr(models, field[0].upper() + field[1:] + 'ship')
    
    person_entity_list = [s for s in person_utils.parse_name_list(names) if s]
    
    for id, s in enumerate(person_entity_list):
        print "Processing person: {0}".format(s.encode('ascii', 'replace'))
        exact_match = False
        multiple_match = False
        relaxed_match = False

        if re.search('[a-zA-Z]{1}[0-9]{6}', s):
            # This is a study number...
            p, match, msg = get_from_studynumber(s, user)
            
        elif len(re.split('[^A-Za-z]',s)) == 1:
            # this is an entry with only consecutive letters = initials
            p, match, msg = get_from_initials(s, user)
        
        elif re.search('\[.*\]', s):
            # this entry has a tag!
             p, match, msg = get_from_tag(s, user)
             
        else:
            # otherwise... this is just a name...
            p, match, msg = get_from_namestring(s, user)
        
        personmessages.extend(msg)
        
        if p:
            if len(p) > 1:
                # More than one exact return, flag multiple_match
                multiple_match = True
            if match == 'exact':
                # if exact match flag exact_match
                exact_match = True
            elif match == 'relaxed':
                # if relaxed match flag relaxed_match
                relaxed_match = True

            # add the person to the author/supervisor/editor-relationship
            tmp = through_tbl(person=p[0],
                              publication=pub,
                              exact_match=exact_match,
                              multiple_match=multiple_match,
                              relaxed_match=relaxed_match,
                              **{field+'_id': id})
            tmp.save()

    return personmessages    
    
    
def get_from_studynumber(s, user):
    """Get or create person from study number. Will use ldap lookup if possible."""

    msgs = []
    
    # See if it is in our own database
    p, match = person_utils.get_person(id_number=s, exact=True)
    if not p:
        # Now see if it is in LDAP directory
        result = ldap_person.find_ldap_person(name=s)
        if result:
            p = ldap_person.get_or_create_person_from_ldap(person=result[0],
                                                           user=user)
            exact_match = True
#            print "   LDAP match"
        else:
#            print "   WARNING: No match found. Not added!"
            msgstr = "{0} identified by '{1}' was not found in " \
                     "database. Please add {0} manually!"
            msgstr = msgstr.format(field.title(), s)
            msgs.append((messages.WARNING, msgstr))
            continue
    else:
#        print "   DB match"
        pass
    
    return p, match, msgs

    
def get_from_studynumber(s, user):
    """Get or create person from initials. Will use ldap lookup if possible."""

    msgs = []
    
    # See if it is in our own database
    p, match = person_utils.get_person(initials=s, exact=True)
    if not p:
        # Now see if it is in LDAP directory
        result = ldap_person.find_ldap_person(initials=s)
        if result:
            p = ldap_person.get_or_create_person_from_ldap(person=result[0],
                                                           user=user)
            exact_match = True
#            print "   LDAP match"
        else:
#            print "   WARNING: No match found. Not added!"
            msgstr = "{0} identified by '{1}' was not found in " \
                     "database. Please add {2} manually!"
            msgstr = msgstr.format(field.title(), s, field.lower())
            msgs.append((messages.WARNING, msgstr))
            continue
    else:
#        print "   DB match"    
        pass
    
    return p, match, msgs    
    

def get_from_tag(s, user):
    """Get or create person from tag value."""

    msgs = []
    s = s.strip()
    pid = get_tag(s, 'id')

    if pid == '0':
        # tag [id:0]
        # create new person
        # ...
        s = remove_tags(s)
        if s:
            p = Person(name=s)
            p.created_by = user
            p.modified_by = user
            p.save()

    elif pid:
        # tag [id:XX] where xx is supposed to be integer.
        # get specified person and add to authorship
        try:
            p = Person.objects.get(id=pid)
        except ObjectDoesNotExist:
            if s:
                # This is only an error, if n is not empty
                msgs.error(request, "Person with id:{0} does not exist in database".format(pid))
            p = None

    return p, 'exact', msgs    
    
    
def get_from_namestring(s):
    """Get or create person from initials. Will use ldap lookup if possible."""

    msgs = []

    person = pybtexPerson(s)

    if not (person.first() and person.last()):
        msgstr = "The {0} name '{1}' does not contain enough " \
                 "information to add it to the database (must " \
                 "contain at least given and sur names)."
        msgstr = msgstr.format(field.lower(), s)
        msgs.append((messages.ERROR, msgstr))
        continue

#    print "   Processing person {0}: {1}".format(id, utils.unidecode(unicode(person)))

    # Get existing persons using relaxed naming
    p, match = person_utils.get_person(person=person)

    # Create new person, also if matched
    p = person_utils.create_person_from_pybtex(person=person, user=user)    
    
    return p, match, msgs    
    
    

# def dk_unidecode(string):
#     """use unidecode, but first exchange æÆ, øØ and åÅ with ae, oe and aa
#
#     """
#
#     raise DeprecationWarning('Use instead: find_artek.utils.dk_unidecode')
#
#     kwargs = {'æ': 'ae', 'Æ': 'Ae',
#               'ø': 'oe', 'Ø': 'Oe',
#               'å': 'aa', 'Å': 'Aa'}
#
#     for old, new in kwargs.items():
#         string = string.replace(old, new)
#
#     # now call regular unidecode
#     return unidecode(string)

