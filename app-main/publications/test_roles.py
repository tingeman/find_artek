"""Role groups (registration plan, Phase 1b, roadmap FA-R54).

- Migration 0003_registration_groups creates the groups dtu_user, artek_staff and
  artek_editor with exactly the planned permissions, and its reverse removes them.
- At every CAS login (signal cas_user_authenticated, publications/roles.py) the user is put
  into dtu_user; artek_staff / artek_editor follow AD group membership only.

No network: the AD lookup (roles.ad_group_memberships) or ldap3 itself is mocked.
"""
from unittest import mock

from django.contrib.auth.models import Group, User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, override_settings
from django_cas_ng.backends import CASBackend
from django_cas_ng.signals import cas_user_authenticated

from publications import roles

STAFF_DN = 'CN=ARTEK staff,OU=Groups,DC=example,DC=org'
EDITOR_DN = 'CN=ARTEK editors,OU=Groups,DC=example,DC=org'

EXPECTED_PERMISSIONS = {
    'dtu_user': {
        'edit_own_publication', 'add_person', 'edit_own_person',
        'add_feature', 'edit_own_feature', 'delete_own_feature',
    },
    'artek_staff': {'add_publication', 'delete_own_publication'},
    'artek_editor': {
        'add_publication', 'change_publication', 'delete_publication', 'verify_publication',
        'change_person', 'change_feature', 'delete_feature',
    },
}

MIGRATION_BEFORE = ('publications', '0002_alter_feature_created_date_and_more')
MIGRATION = ('publications', '0003_registration_groups')


def _permissions(group):
    return {(p.content_type.app_label, p.codename) for p in group.permissions.all()}


def _expected(name):
    return {('publications', codename) for codename in EXPECTED_PERMISSIONS[name]}


class RegistrationGroupsMigrationTests(TestCase):

    def test_groups_have_exactly_the_planned_permissions(self):
        for name in EXPECTED_PERMISSIONS:
            with self.subTest(group=name):
                self.assertEqual(_permissions(Group.objects.get(name=name)), _expected(name))

    def test_migration_is_reversible(self):
        executor = MigrationExecutor(connection)
        executor.migrate([MIGRATION_BEFORE])
        self.assertFalse(Group.objects.filter(name__in=EXPECTED_PERMISSIONS).exists())

        executor = MigrationExecutor(connection)
        executor.migrate([MIGRATION])
        for name in EXPECTED_PERMISSIONS:
            with self.subTest(group=name):
                self.assertEqual(_permissions(Group.objects.get(name=name)), _expected(name))

    def test_reverse_keeps_other_groups(self):
        other = Group.objects.create(name='some_other_group')
        executor = MigrationExecutor(connection)
        executor.migrate([MIGRATION_BEFORE])
        self.assertTrue(Group.objects.filter(pk=other.pk).exists())
        MigrationExecutor(connection).migrate([MIGRATION])


def _login(user):
    """Send the signal the way django_cas_ng.backends.CASBackend.authenticate sends it."""
    cas_user_authenticated.send(
        sender=CASBackend, user=user, created=False, username=user.username,
        attributes={}, pgtiou=None, ticket='ST-test', service='http://testserver/login',
        request=None)


def _names(user):
    return set(user.groups.values_list('name', flat=True))


@override_settings(USE_LDAP=True, LDAP_GROUP_ARTEK_STAFF='', LDAP_GROUP_ARTEK_EDITOR='')
class CasLoginRolesTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('s990001', password='x')
        self.staff = Group.objects.get(name='artek_staff')
        self.editor = Group.objects.get(name='artek_editor')

    def test_login_adds_dtu_user(self):
        with mock.patch.object(roles, 'ad_group_memberships') as lookup:
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user'})
        lookup.assert_not_called()  # no AD group configured: no lookup

    def test_empty_settings_remove_hand_set_roles(self):
        self.user.groups.add(self.staff, self.editor)
        _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_members_get_roles(self):
        with mock.patch.object(roles, 'ad_group_memberships',
                               return_value={STAFF_DN: True, EDITOR_DN: True}) as lookup:
            _login(self.user)
        lookup.assert_called_once()
        self.assertEqual(lookup.call_args.args[0], 's990001')
        self.assertCountEqual(lookup.call_args.args[1], [STAFF_DN, EDITOR_DN])
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_staff', 'artek_editor'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_non_members_lose_roles(self):
        self.user.groups.add(self.staff, self.editor)
        with mock.patch.object(roles, 'ad_group_memberships',
                               return_value={STAFF_DN: False, EDITOR_DN: False}):
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_roles_are_independent(self):
        self.user.groups.add(self.editor)
        with mock.patch.object(roles, 'ad_group_memberships',
                               return_value={STAFF_DN: True, EDITOR_DN: False}):
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_staff'})

        with mock.patch.object(roles, 'ad_group_memberships',
                               return_value={STAFF_DN: False, EDITOR_DN: True}):
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_editor'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR='')
    def test_only_configured_group_is_looked_up(self):
        self.user.groups.add(self.editor)
        with mock.patch.object(roles, 'ad_group_memberships',
                               return_value={STAFF_DN: True}) as lookup:
            _login(self.user)
        self.assertEqual(lookup.call_args.args[1], [STAFF_DN])
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_staff'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_lookup_failure_keeps_membership_and_grants_nothing(self):
        self.user.groups.add(self.editor)
        with mock.patch.object(roles, 'ad_group_memberships',
                               side_effect=roles.LdapLookupError('bind failed')), \
                self.assertLogs('publications.roles', level='WARNING'):
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_editor'})

    @override_settings(USE_LDAP=False, LDAP_GROUP_ARTEK_STAFF=STAFF_DN,
                       LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_ldap_disabled_is_treated_as_failure(self):
        self.user.groups.add(self.staff)
        with mock.patch('publications.roles.ldap3.Connection') as connection_cls, \
                self.assertLogs('publications.roles', level='WARNING'):
            _login(self.user)
        connection_cls.assert_not_called()
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_staff'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_superuser_and_is_staff_untouched(self):
        admin = User.objects.create_superuser('admin1', password='x')  # is_staff too
        plain = User.objects.create_user('s990002', password='x', is_staff=False)
        for answer in ({STAFF_DN: True, EDITOR_DN: True}, {STAFF_DN: False, EDITOR_DN: False}):
            with mock.patch.object(roles, 'ad_group_memberships', return_value=answer):
                _login(admin)
                _login(plain)
            admin.refresh_from_db()
            plain.refresh_from_db()
            self.assertTrue(admin.is_superuser)
            self.assertTrue(admin.is_staff)
            self.assertFalse(plain.is_superuser)
            self.assertFalse(plain.is_staff)

    def test_missing_dtu_user_group_is_logged_and_login_continues(self):
        Group.objects.filter(name='dtu_user').delete()
        with self.assertLogs('publications.roles', level='ERROR'):
            _login(self.user)
        self.assertEqual(_names(self.user), set())


@override_settings(USE_LDAP=True, AUTH_LDAP_SERVER_URI='ldaps://ldap.invalid',
                   AUTH_LDAP_BIND_DN='cn=bind', AUTH_LDAP_BIND_PASSWORD='secret',
                   AUTH_LDAP_USER_SEARCH_BASE='ou=Users,dc=example,dc=org')
class AdGroupMembershipsTests(TestCase):
    """The lookup function itself, with ldap3 mocked."""

    def test_one_connection_one_search_per_group_with_escaped_filter(self):
        with mock.patch('publications.roles.ldap3.Server'), \
                mock.patch('publications.roles.ldap3.Connection') as connection_cls:
            conn = connection_cls.return_value.__enter__.return_value
            results = iter([[object()], []])

            def search(base, search_filter, **kwargs):
                conn.entries = next(results)
            conn.search.side_effect = search

            answer = roles.ad_group_memberships('a*b(c)', [STAFF_DN, 'CN=x(y),DC=org'])

        self.assertEqual(answer, {STAFF_DN: True, 'CN=x(y),DC=org': False})
        connection_cls.assert_called_once()
        self.assertEqual(connection_cls.call_args.kwargs['receive_timeout'], roles.LDAP_TIMEOUT)
        filters = [c.args[1] for c in conn.search.call_args_list]
        self.assertEqual(filters, [
            '(&(sAMAccountName=a\\2ab\\28c\\29)'
            '(memberOf:1.2.840.113556.1.4.1941:=CN=ARTEK staff,OU=Groups,DC=example,DC=org))',
            '(&(sAMAccountName=a\\2ab\\28c\\29)'
            '(memberOf:1.2.840.113556.1.4.1941:=CN=x\\28y\\29,DC=org))',
        ])
        self.assertEqual(conn.search.call_args_list[0].args[0], 'ou=Users,dc=example,dc=org')

    def test_bind_failure_raises_lookup_error_without_secrets(self):
        with mock.patch('publications.roles.ldap3.Server'), \
                mock.patch('publications.roles.ldap3.Connection',
                           side_effect=RuntimeError('bind as cn=bind with secret failed')):
            with self.assertRaises(roles.LdapLookupError) as ctx:
                roles.ad_group_memberships('s990001', [STAFF_DN])
        self.assertNotIn('secret', str(ctx.exception))
        self.assertNotIn('cn=bind', str(ctx.exception))

    @override_settings(USE_LDAP=False)
    def test_disabled_raises_without_connecting(self):
        with mock.patch('publications.roles.ldap3.Connection') as connection_cls:
            with self.assertRaises(roles.LdapLookupError):
                roles.ad_group_memberships('s990001', [STAFF_DN])
        connection_cls.assert_not_called()
