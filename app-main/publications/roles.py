"""Role groups, name and e-mail set at every CAS login (registration plan, Phase 1b, roadmap
FA-R54, tasks T1 and T12).

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
- ``first_name``, ``last_name`` and ``email`` are set from the user's AD entry (``givenName``,
  ``sn``, ``mail``; as the old django-auth-ldap ``AUTH_LDAP_USER_ATTR_MAP``). An empty or missing
  AD value, an entry that is not found, a failed lookup or ``USE_LDAP = False`` leave the stored
  value unchanged. Nothing else about the user is stored.

One LDAP connection per login: the user's entry and the group memberships are read on the same
bind (``ad_user_info``).

The groups and their permissions are created by migration 0003_registration_groups.
"""
import logging
from typing import NamedTuple

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
    """The AD lookup could not be done (disabled, bind or search failure)."""


class AdUserInfo(NamedTuple):
    """What the login lookup reads from AD. Empty string = no value in AD (or entry not found)."""
    first_name: str
    last_name: str
    email: str
    memberships: dict  # {group_dn: bool}


# auth_user field -> AD attribute of the user's entry.
USER_ATTRIBUTES = {
    'first_name': 'givenName',
    'last_name': 'sn',
    'email': 'mail',
}


def _first_value(attributes, name):
    """First value of attribute `name` (case-insensitive) as a stripped string, '' if none."""
    for key, values in attributes.items():
        if key.lower() != name.lower():
            continue
        if not isinstance(values, (list, tuple)):
            values = [values]
        for value in values:
            if isinstance(value, bytes):
                value = value.decode('utf-8', errors='replace')
            value = str(value).strip() if value is not None else ''
            if value:
                return value
    return ''


def ad_user_info(username, group_dns):
    """Read the AD entry of `username` (sAMAccountName) and its group memberships on one
    connection (one bind).

    Returns AdUserInfo: first_name/last_name/email from givenName/sn/mail ('' when missing or
    when the entry is not found) and memberships {group_dn: bool} for each DN in `group_dns`,
    nested membership included (one search per group).

    Raises LdapLookupError if LDAP is disabled or the lookup fails.
    """
    if not getattr(settings, 'USE_LDAP', False):
        raise LdapLookupError('LDAP is disabled (USE_LDAP is False)')
    user = escape_filter_chars(username)
    memberships = {}
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
            conn.search(settings.AUTH_LDAP_USER_SEARCH_BASE, f'(sAMAccountName={user})',
                        attributes=list(USER_ATTRIBUTES.values()), size_limit=1)
            attributes = conn.entries[0].entry_attributes_as_dict if conn.entries else {}
            values = {field: _first_value(attributes, attr)
                      for field, attr in USER_ATTRIBUTES.items()}

            for dn in group_dns:
                search_filter = '(&(sAMAccountName={0})(memberOf:{1}:={2}))'.format(
                    user, _IN_CHAIN, escape_filter_chars(dn))
                conn.search(settings.AUTH_LDAP_USER_SEARCH_BASE, search_filter,
                            attributes=['sAMAccountName'], size_limit=1)
                memberships[dn] = len(conn.entries) > 0
    except Exception as exc:
        # Only the exception type: messages may contain the bind DN or server details.
        raise LdapLookupError(f'LDAP lookup failed ({type(exc).__name__})') from exc
    return AdUserInfo(memberships=memberships, **values)


def _group(name):
    try:
        return Group.objects.get(name=name)
    except Group.DoesNotExist:
        logger.error('Group %s does not exist (migration publications 0003 not applied?)', name)
        return None


def update_user_details(user, info):
    """Set first_name, last_name and email of `user` from `info` (AdUserInfo). Empty AD values
    don't overwrite stored ones; names are cut to the field's max_length, an e-mail address
    longer than the field is not stored (a cut address would be wrong). Saves only the fields
    that changed."""
    changed = []
    for field in USER_ATTRIBUTES:
        value = getattr(info, field)
        if not value:
            continue
        max_length = user._meta.get_field(field).max_length
        if max_length and len(value) > max_length:
            if field == 'email':
                continue
            value = value[:max_length].rstrip()
        if getattr(user, field) != value:
            setattr(user, field, value)
            changed.append(field)
    if changed:
        user.save(update_fields=changed)


def update_user_from_ad(user):
    """Set the role groups, name and e-mail of `user` as described in the module docstring.
    One AD lookup (one connection) per call, also when no AD group is configured."""
    dtu_user = _group(DTU_USER)
    if dtu_user is not None:
        user.groups.add(dtu_user)

    configured = {}  # Django group name -> (group, AD group DN)
    for group_name, setting_name in AD_ROLE_SETTINGS.items():
        dn = getattr(settings, setting_name, '') or ''
        group = _group(group_name)
        if group is None:
            continue
        if dn:
            configured[group_name] = (group, dn)
        else:
            user.groups.remove(group)

    try:
        info = ad_user_info(user.get_username(), [dn for _, dn in configured.values()])
    except LdapLookupError as exc:
        # No names or e-mail addresses in the log; the username as in T1.
        logger.warning('AD data of user %s not updated (name, e-mail and AD roles kept): %s',
                       user.get_username(), exc)
        return

    for group_name, (group, dn) in configured.items():
        if info.memberships.get(dn, False):
            user.groups.add(group)
        else:
            user.groups.remove(group)

    update_user_details(user, info)


def cas_user_authenticated_handler(sender, user=None, **kwargs):
    """Receiver of django_cas_ng.signals.cas_user_authenticated (sent with user, created,
    username, attributes, pgtiou, ticket, service, request)."""
    if user is None:
        return
    update_user_from_ad(user)
