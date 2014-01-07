from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

from django.dispatch import receiver
from django_auth_ldap.backend import populate_user
from django.contrib.auth.models import Group
from ldap import SCOPE_SUBTREE
import sys
import pdb

import logging
logger = logging.getLogger(__name__)


"""This module is being imported in the publications __init__ module and from the urls module.
"""

super_user_list = []
#super_user_list = [u's103346',
#                   u's103355',
#                   u'thin']

CArtek1_groups_base_name = 'OU=Security group,OU=BYG,OU=Institutter,DC=win,DC=dtu,DC=dk'
ARTEK_superuser_groups = [u'CN=BYG-CArtek1_superusers,OU=Security group,OU=BYG,OU=Institutter,DC=win,DC=dtu,DC=dk']

ARTEK_staff_groups = [u'CN=BYG-CArtek1_staff,OU=Security group,OU=BYG,OU=Institutter,DC=win,DC=dtu,DC=dk',
                      u'CN=11427_Teachers,OU=11427,OU=Courses,DC=win,DC=dtu,DC=dk']

ARTEK_student_groups = [u'CN=11427_Students,OU=11427,OU=Courses,DC=win,DC=dtu,DC=dk',
                        u'CN=BYG-CArtek1_11427,OU=Security group,OU=BYG,OU=Institutter,DC=win,DC=dtu,DC=dk']

logger.debug('TEST: loaded the signals.py module')


@receiver(populate_user)
def post_ldap_authentication(sender, **kwargs):
    """Update django user model with permissions according to ldap group
    memberships.

    """

    user = kwargs['user']
    ldap_user = kwargs['ldap_user']

    all_groups_dn = set(ldap_user._user_attrs['memberOf'])

    searchstr = '(&(objectClass=group)(member:1.2.840.113556.1.4.1941:={0}))'.format(ldap_user._user_dn)
    try:
        result = ldap_user._connection.search_s(CArtek1_groups_base_name, SCOPE_SUBTREE, searchstr, None)
    except:
        result = []
        logger.warning('ldap search for nested groups failed!')

    if result:
        for r in result: all_groups_dn.add(r[0])

    # all_groups_dn = sorted(all_groups_dn)


    """  Handle ARTEK STAFF  """
    logger.debug('TEST: Authenticating for STAFF membership')

    try:
        g = Group.objects.get(name='ARTEK_staff')
    except:
        logger.debug('ARTEK_staff group not found in django database')
        g = None

    if g:
        # Remove the group if it is already there.
        if g in user.groups.all():
            user.groups.remove(g)

        for group in ARTEK_staff_groups:
            #if group in ldap_user._user_attrs['memberOf']:
            if group in all_groups_dn:
                user.groups.add(g)
                user.is_staff = True
                logger.debug('TEST: Group {0} added to user {1}'.format(g, user.username))


    """  Handle ARTEK STUDENTS  """
    try:
        g = Group.objects.get(name='ARTEK_student')
    except:
        logger.debug('ARTEK_student group not found in django database')
        g = None

    if g:
        # Remove the group if it is already there.
        if g in user.groups.all():
            user.groups.remove(g)

        for group in ARTEK_student_groups:
            #if group in ldap_user._user_attrs['memberOf']:
            if group in all_groups_dn:
                user.groups.add(g)
                logger.debug('TEST: Group {0} added to user {1}'.format(g, user.username))


    """  Handle ARTEK SUPERUSERS  """

    user.is_superuser = False
    for group in ARTEK_superuser_groups:
        #if group in ldap_user._user_attrs['memberOf'] or user.username in super_user_list:
        if group in all_groups_dn or user.username in super_user_list:
            user.is_superuser = True
            logger.debug('TEST: superuser permissions added to user {0}'.format(user.username))
