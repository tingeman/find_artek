from django.dispatch import receiver
from django_auth_ldap.backend import populate_user
from django.contrib.auth.models import Group

import pdb

import logging
logger = logging.getLogger(__name__)


super_user_list = [u's103346',
                   u's103355',
                   u'thin']

ARTEK_superuser_groups = []

ARTEK_staff_groups = [u'CN=BYG-ArktiskCenter,OU=Grupper_migreret_fra_BYG,OU=Security group,OU=BYG,OU=Institutter,DC=win,DC=dtu,DC=dk',
                      u'CN=11427_Teachers,OU=11427,OU=Courses,DC=win,DC=dtu,DC=dk']

ARTEK_student_groups = [u'CN=11427_Students,OU=11427,OU=Courses,DC=win,DC=dtu,DC=dk']


@receiver(populate_user)
def post_ldap_authentication(sender, **kwargs):
    """Update django user model with permissions according to ldap group
    memberships.

    """

    user = kwargs['user']
    ldap_user = kwargs['ldap_user']

    #pdb.set_trace()

    """  Handle ARTEK STAFF  """
    try:
        g = Group.objects.get(name='ARTEK_staff')
    except:
        logging.debug('ARTEK_staff group not found in django database')
        g = None

    if g:
        # Remove the group if it is already there.
        if g in user.groups.all():
            user.groups.remove(g)

        for group in ARTEK_staff_groups:
            if group in ldap_user._user_attrs['memberOf']:
                user.groups.add(g)


    """  Handle ARTEK STUDENTS  """
    try:
        g = Group.objects.get(name='ARTEK_student')
    except:
        logging.debug('ARTEK_student group not found in django database')
        g = None

    if g:
        # Remove the group if it is already there.
        if g in user.groups.all():
            user.groups.remove(g)

        for group in ARTEK_student_groups:
            if group in ldap_user._user_attrs['memberOf']:
                user.groups.add(g)


    """  Handle ARTEK SUPERUSERS  """

    user.is_superuser = False
    for group in ARTEK_student_groups:
        if group in ldap_user._user_attrs['memberOf'] or user.username in super_user_list:
            user.is_superuser = True
