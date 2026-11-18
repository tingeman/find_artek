"""Role groups set at every CAS login (registration plan, Phase 1b, roadmap FA-R54).

- Every user who logs in through CAS is put into the group ``dtu_user``.
- ``artek_staff`` and ``artek_editor`` come only from AD group membership: the settings
  ``LDAP_GROUP_ARTEK_STAFF`` / ``LDAP_GROUP_ARTEK_EDITOR`` hold the DN of the AD group whose
  members (also through nested groups) get the role.
  - setting empty: nobody has the role, the user is removed from the Django group (a hand-made
    assignment in the admin does not survive a login);
  - lookup succeeded: the user is added if a member and removed if not;
  - lookup failed or ``USE_LDAP`` is False: the current membership of both groups is kept and
    nothing new is granted.
- ``is_superuser`` and ``is_staff`` are never touched.

The groups and their permissions are created by migration 0003_registration_groups.
"""
import logging

import ldap3
from django.conf import settings
from django.contrib.auth.models import Group
from ldap3.utils.conv import escape_filter_chars

logger = logging.getLogger(__name__)

DTU_USER = 'dtu_user'
ARTEK_STAFF = 'artek_staff'
ARTEK_EDITOR = 'artek_editor'

# Django group -> name of the setting holding the DN of the AD group that grants it.
AD_ROLE_SETTINGS = {
    ARTEK_STAFF: 'LDAP_GROUP_ARTEK_STAFF',
    ARTEK_EDITOR: 'LDAP_GROUP_ARTEK_EDITOR',
}

# Seconds; a slow or unreachable LDAP server must not hang a login.
LDAP_TIMEOUT = 5

# LDAP_MATCHING_RULE_IN_CHAIN: memberOf also matches through nested groups (AD only).
_IN_CHAIN = '1.2.840.113556.1.4.1941'


class LdapLookupError(Exception):
    """The AD group lookup could not be done (disabled, bind or search failure)."""


def ad_group_memberships(username, group_dns):
    """Return {group_dn: bool}: whether `username` (sAMAccountName) is a member of each AD
    group, nested membership included. One connection, one search per group.

    Raises LdapLookupError if LDAP is disabled or the lookup fails.
    """
    if not getattr(settings, 'USE_LDAP', False):
        raise LdapLookupError('LDAP is disabled (USE_LDAP is False)')
    user = escape_filter_chars(username)
    result = {}
    try:
        server = ldap3.Server(settings.AUTH_LDAP_SERVER_URI, connect_timeout=LDAP_TIMEOUT)
        with ldap3.Connection(
            server,
            user=settings.AUTH_LDAP_BIND_DN,
            password=settings.AUTH_LDAP_BIND_PASSWORD,
            auto_bind=True,
            receive_timeout=LDAP_TIMEOUT,
            raise_exceptions=True,
        ) as conn:
            for dn in group_dns:
                search_filter = '(&(sAMAccountName={0})(memberOf:{1}:={2}))'.format(
                    user, _IN_CHAIN, escape_filter_chars(dn))
                conn.search(settings.AUTH_LDAP_USER_SEARCH_BASE, search_filter,
                            attributes=['sAMAccountName'], size_limit=1)
                result[dn] = len(conn.entries) > 0
    except Exception as exc:
        # Only the exception type: messages may contain the bind DN or server details.
        raise LdapLookupError(f'LDAP group lookup failed ({type(exc).__name__})') from exc
    return result


def _group(name):
    try:
        return Group.objects.get(name=name)
    except Group.DoesNotExist:
        logger.error('Group %s does not exist (migration publications 0003 not applied?)', name)
        return None


def update_user_roles(user):
    """Set the role groups of `user` as described in the module docstring."""
    dtu_user = _group(DTU_USER)
    if dtu_user is not None:
        user.groups.add(dtu_user)

    configured = {}  # Django group name -> AD group DN
    for group_name, setting_name in AD_ROLE_SETTINGS.items():
        dn = getattr(settings, setting_name, '') or ''
        group = _group(group_name)
        if group is None:
            continue
        if dn:
            configured[group_name] = (group, dn)
        else:
            user.groups.remove(group)

    if not configured:
        return

    try:
        memberships = ad_group_memberships(
            user.get_username(), [dn for _, dn in configured.values()])
    except LdapLookupError as exc:
        logger.warning('Roles of user %s not updated, membership kept: %s',
                       user.get_username(), exc)
        return

    for group_name, (group, dn) in configured.items():
        if memberships.get(dn, False):
            user.groups.add(group)
        else:
            user.groups.remove(group)


def cas_user_authenticated_handler(sender, user=None, **kwargs):
    """Receiver of django_cas_ng.signals.cas_user_authenticated (sent with user, created,
    username, attributes, pgtiou, ticket, service, request)."""
    if user is None:
        return
    update_user_roles(user)
