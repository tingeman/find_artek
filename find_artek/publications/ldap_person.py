from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

from django_auth_ldap.backend import populate_user
from ldap import SCOPE_SUBTREE
import sys
import pdb

import logging
logger = logging.getLogger(__name__)



logger.debug('TEST: loaded the ldap_person.py module')



AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=DTUBaseUsers,dc=win,dc=dtu,dc=dk",
                                   ldap.SCOPE_SUBTREE, "(name=%(user)s)")

AUTH_LDAP_GROUP_SEARCH = LDAPSearch("dc=win,dc=dtu,dc=dk", ldap.SCOPE_SUBTREE, "(objectClass=group)")
AUTH_LDAP_GROUP_TYPE = ActiveDirectoryGroupType(name_attr="cn")


AUTH_LDAP_USER_ATTR_MAP = {"first_name": "givenName", "last_name": "sn",
                           "email": "mail"}



def find_ldap_person(**kwargs):
    """Search LDAP for user with the attributes specified in kwargs.
    Returns a LDAP user instance.

    """

    
    # 1) Possibly make translation of attribute names?
    # 2) Generate search string
    searchstr = '(&(objectClass=group)(member:1.2.840.113556.1.4.1941:={0}))'.format(ldap_user._user_dn)
    
    # 3) Perform the search
    try:
        result = ldap_user._connection.search_s(CArtek1_groups_base_name, SCOPE_SUBTREE, searchstr, None)
    except:
        result = []
        logger.warning('ldap search for nested groups failed!')
        
    # 4) Return list of users matching the search criteria
    return result
  
  
def get_or_create_person_from_ldap_search(first_name=None, last_name=None, email=None, person_id=None, initials=None):
    """Search the ldap directory for persons matching the specified attributes.
    If the person_id (study number or employee number) or initials are specified and the search matches exactly one 
    person, get the full credentials, and search the persons table. If a match is found, return that id. If a match
    is not found, create the person and return the id.
    If only name attributes are passed, create a new person and possibly mark as multiple matches.
    """
    
    find_ldap_person(givenName=..., sn=..., email=..., ????)
    pass