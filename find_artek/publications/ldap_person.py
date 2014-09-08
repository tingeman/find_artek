from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

from django_auth_ldap.backend import populate_user
import ldap
import sys
import pdb

import logging

from find_artek import settings
from find_artek.publications import person_utils
from find_artek.publications import models


logger = logging.getLogger(__name__)
logger.debug('TEST: loaded the ldap_person.py module')



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


def get_or_create_person_from_ldap_search(first_name=None, last_name=None, email=None, person_id=None, initials=None):
    """Search the ldap directory for persons matching the specified attributes.
    If the person_id (study number or employee number) or initials are specified and the search matches exactly one
    person, get the full credentials, and search the persons table. If a match is found, return that id. If a match
    is not found, create the person and return the id.
    If only name attributes are passed, create a new person and possibly mark as multiple matches.
    """

    #find_ldap_person(givenName=..., sn=..., email=..., ????)
    pass



def get_or_create_person_from_ldap(person=None, user=None):
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
    kwargs = person_utils.get_full_name_kwargs(string=name)
    kwargs.update(person_utils.get_relaxed_name_kwargs(string=name))

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
    kwargs = person_utils.get_full_name_kwargs(string=name)
    kwargs.update(person_utils.get_relaxed_name_kwargs(string=name))

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
