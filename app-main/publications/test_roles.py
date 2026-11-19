"""Role groups (registration plan, Phase 1b, roadmap FA-R54).

- Migration 0003_registration_groups creates the groups dtu_user, artek_staff and
  artek_editor with exactly the planned permissions, and its reverse removes them.
- At every CAS login (signal cas_user_authenticated, publications/roles.py) the user is put
  into dtu_user; artek_staff / artek_editor follow AD group membership only.
- T12: at the same login, first_name / last_name / email are set from the AD entry (givenName,
  sn, mail), read on the same LDAP connection as the group memberships.

No network: the AD lookup (roles.ad_user_info) or ldap3 itself is mocked.
"""
from unittest import mock

from django.contrib.auth.models import Group, User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, override_settings
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


def _info(memberships=None, first_name='', last_name='', email=''):
    """What roles.ad_user_info returns for a successful lookup."""
    return roles.AdUserInfo(first_name=first_name, last_name=last_name, email=email,
                            memberships=memberships or {})


@override_settings(USE_LDAP=True, LDAP_GROUP_ARTEK_STAFF='', LDAP_GROUP_ARTEK_EDITOR='')
class CasLoginRolesTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('s990001', password='x')
        self.staff = Group.objects.get(name='artek_staff')
        self.editor = Group.objects.get(name='artek_editor')

    def test_login_adds_dtu_user(self):
        with mock.patch.object(roles, 'ad_user_info', return_value=_info()) as lookup:
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user'})
        # T12: no AD group configured: still one lookup (for name and e-mail), no group DN.
        lookup.assert_called_once_with('s990001', [])

    def test_empty_settings_remove_hand_set_roles(self):
        self.user.groups.add(self.staff, self.editor)
        with mock.patch.object(roles, 'ad_user_info', return_value=_info()):
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user'})

    def test_empty_settings_remove_hand_set_roles_also_when_lookup_fails(self):
        self.user.groups.add(self.staff, self.editor)
        with mock.patch.object(roles, 'ad_user_info',
                               side_effect=roles.LdapLookupError('bind failed')), \
                self.assertLogs('publications.roles', level='WARNING'):
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_members_get_roles(self):
        with mock.patch.object(roles, 'ad_user_info',
                               return_value=_info({STAFF_DN: True, EDITOR_DN: True})) as lookup:
            _login(self.user)
        lookup.assert_called_once()
        self.assertEqual(lookup.call_args.args[0], 's990001')
        self.assertCountEqual(lookup.call_args.args[1], [STAFF_DN, EDITOR_DN])
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_staff', 'artek_editor'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_non_members_lose_roles(self):
        self.user.groups.add(self.staff, self.editor)
        with mock.patch.object(roles, 'ad_user_info',
                               return_value=_info({STAFF_DN: False, EDITOR_DN: False})):
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_roles_are_independent(self):
        self.user.groups.add(self.editor)
        with mock.patch.object(roles, 'ad_user_info',
                               return_value=_info({STAFF_DN: True, EDITOR_DN: False})):
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_staff'})

        with mock.patch.object(roles, 'ad_user_info',
                               return_value=_info({STAFF_DN: False, EDITOR_DN: True})):
            _login(self.user)
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_editor'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR='')
    def test_only_configured_group_is_looked_up(self):
        self.user.groups.add(self.editor)
        with mock.patch.object(roles, 'ad_user_info',
                               return_value=_info({STAFF_DN: True})) as lookup:
            _login(self.user)
        self.assertEqual(lookup.call_args.args[1], [STAFF_DN])
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_staff'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_lookup_failure_keeps_membership_and_grants_nothing(self):
        self.user.groups.add(self.editor)
        with mock.patch.object(roles, 'ad_user_info',
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
            with mock.patch.object(roles, 'ad_user_info', return_value=_info(answer)):
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
        with mock.patch.object(roles, 'ad_user_info', return_value=_info()), \
                self.assertLogs('publications.roles', level='ERROR'):
            _login(self.user)
        self.assertEqual(_names(self.user), set())


@override_settings(USE_LDAP=True, LDAP_GROUP_ARTEK_STAFF='', LDAP_GROUP_ARTEK_EDITOR='')
class CasLoginUserDetailsTests(TestCase):
    """T12: first_name / last_name / email from AD at login."""

    def setUp(self):
        self.user = User.objects.create_user('s990001', password='x')

    def _set(self, **fields):
        User.objects.filter(pk=self.user.pk).update(**fields)
        self.user.refresh_from_db()

    def _stored(self):
        self.user.refresh_from_db()
        return (self.user.first_name, self.user.last_name, self.user.email)

    def test_fields_set_at_login_also_without_group_settings(self):
        info = _info(first_name='Ada Maria', last_name='Lovelace', email='ada@example.org')
        with mock.patch.object(roles, 'ad_user_info', return_value=info) as lookup:
            _login(self.user)
        lookup.assert_called_once_with('s990001', [])
        self.assertEqual(self._stored(), ('Ada Maria', 'Lovelace', 'ada@example.org'))
        self.assertEqual(_names(self.user), {'dtu_user'})

    @override_settings(LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
    def test_fields_and_roles_from_the_same_lookup(self):
        info = _info({STAFF_DN: True, EDITOR_DN: False}, 'Ada', 'Lovelace', 'ada@example.org')
        with mock.patch.object(roles, 'ad_user_info', return_value=info) as lookup:
            _login(self.user)
        lookup.assert_called_once()
        self.assertEqual(self._stored(), ('Ada', 'Lovelace', 'ada@example.org'))
        self.assertEqual(_names(self.user), {'dtu_user', 'artek_staff'})

    def test_changed_values_are_updated(self):
        self._set(first_name='Old', last_name='Name', email='old@example.org')
        info = _info(first_name='New', last_name='Name', email='new@example.org')
        with mock.patch.object(roles, 'ad_user_info', return_value=info):
            _login(self.user)
        self.assertEqual(self._stored(), ('New', 'Name', 'new@example.org'))

    def test_only_changed_fields_are_saved(self):
        self._set(first_name='Ada', last_name='Lovelace')
        info = _info(first_name='Ada', last_name='Lovelace', email='ada@example.org')
        with mock.patch.object(roles, 'ad_user_info', return_value=info), \
                mock.patch.object(User, 'save', autospec=True) as save:
            _login(self.user)
        save.assert_called_once()
        self.assertEqual(save.call_args.kwargs['update_fields'], ['email'])

    def test_unchanged_values_are_not_saved(self):
        self._set(first_name='Ada', last_name='Lovelace', email='ada@example.org')
        info = _info(first_name='Ada', last_name='Lovelace', email='ada@example.org')
        with mock.patch.object(roles, 'ad_user_info', return_value=info), \
                mock.patch.object(User, 'save', autospec=True) as save:
            _login(self.user)
        save.assert_not_called()

    def test_empty_ad_values_do_not_overwrite(self):
        self._set(first_name='Ada', last_name='Lovelace', email='ada@example.org')
        info = _info(first_name='', last_name='Byron', email='')
        with mock.patch.object(roles, 'ad_user_info', return_value=info):
            _login(self.user)
        self.assertEqual(self._stored(), ('Ada', 'Byron', 'ada@example.org'))

    def test_entry_not_found_leaves_fields_unchanged(self):
        """ad_user_info gives empty values when the entry is not found (see AdUserInfoTests)."""
        self._set(first_name='Ada', email='ada@example.org')
        with mock.patch.object(roles, 'ad_user_info', return_value=_info()):
            _login(self.user)
        self.assertEqual(self._stored(), ('Ada', '', 'ada@example.org'))
        self.assertEqual(_names(self.user), {'dtu_user'})

    def test_lookup_failure_leaves_fields_unchanged_and_logs_no_personal_data(self):
        self._set(first_name='Ada', last_name='Lovelace', email='ada@example.org')
        with mock.patch.object(roles, 'ad_user_info',
                               side_effect=roles.LdapLookupError('LDAP lookup failed (X)')), \
                self.assertLogs('publications.roles', level='WARNING') as logs:
            _login(self.user)
        self.assertEqual(self._stored(), ('Ada', 'Lovelace', 'ada@example.org'))
        self.assertEqual(_names(self.user), {'dtu_user'})
        text = '\n'.join(logs.output)
        for personal in ('Ada', 'Lovelace', 'ada@example.org'):
            self.assertNotIn(personal, text)

    @override_settings(USE_LDAP=False)
    def test_ldap_disabled_leaves_fields_unchanged(self):
        self._set(first_name='Ada', last_name='Lovelace')
        with mock.patch('publications.roles.ldap3.Connection') as connection_cls, \
                self.assertLogs('publications.roles', level='WARNING'):
            _login(self.user)
        connection_cls.assert_not_called()
        self.assertEqual(self._stored(), ('Ada', 'Lovelace', ''))
        self.assertEqual(_names(self.user), {'dtu_user'})

    def test_values_longer_than_the_field(self):
        first_max = User._meta.get_field('first_name').max_length
        last_max = User._meta.get_field('last_name').max_length
        email_max = User._meta.get_field('email').max_length
        self._set(email='ada@example.org')
        info = _info(first_name='A' * (first_max + 10), last_name='B' * (last_max + 1),
                     email='c' * email_max + '@example.org')
        with mock.patch.object(roles, 'ad_user_info', return_value=info):
            _login(self.user)
        # Names are cut to the field length; a too long e-mail is not stored (a cut address
        # would be wrong), the stored one stays.
        self.assertEqual(self._stored(), ('A' * first_max, 'B' * last_max, 'ada@example.org'))

    def test_nothing_else_is_stored(self):
        before = User.objects.filter(pk=self.user.pk).values().get()
        info = _info(first_name='Ada', last_name='Lovelace', email='ada@example.org')
        with mock.patch.object(roles, 'ad_user_info', return_value=info):
            _login(self.user)
        after = User.objects.filter(pk=self.user.pk).values().get()
        changed = {k for k in before if before[k] != after[k]}
        self.assertEqual(changed, {'first_name', 'last_name', 'email'})


class _Entry:
    """Stand-in for an ldap3 Entry."""

    def __init__(self, attributes):
        self.entry_attributes_as_dict = attributes


@override_settings(USE_LDAP=True, AUTH_LDAP_SERVER_URI='ldaps://ldap.invalid',
                   AUTH_LDAP_BIND_DN='cn=bind', AUTH_LDAP_BIND_PASSWORD='secret',
                   AUTH_LDAP_USER_SEARCH_BASE='ou=Users,dc=example,dc=org')
class AdUserInfoTests(TestCase):
    """The lookup function itself, with ldap3 mocked."""

    def _lookup(self, username, group_dns, results):
        """Run roles.ad_user_info with ldap3 mocked; `results` = conn.entries per search."""
        with mock.patch('publications.roles.ldap3.Server'), \
                mock.patch('publications.roles.ldap3.Connection') as connection_cls:
            conn = connection_cls.return_value.__enter__.return_value
            results = iter(results)

            def search(base, search_filter, **kwargs):
                conn.entries = next(results)
            conn.search.side_effect = search

            answer = roles.ad_user_info(username, group_dns)
        return answer, connection_cls, conn

    def test_one_connection_user_search_then_one_search_per_group_with_escaped_filter(self):
        entry = _Entry({'givenName': ['Ada'], 'sn': ['Lovelace'], 'mail': ['ada@example.org']})
        answer, connection_cls, conn = self._lookup(
            'a*b(c)', [STAFF_DN, 'CN=x(y),DC=org'], [[entry], [object()], []])

        self.assertEqual(answer, roles.AdUserInfo(
            first_name='Ada', last_name='Lovelace', email='ada@example.org',
            memberships={STAFF_DN: True, 'CN=x(y),DC=org': False}))
        connection_cls.assert_called_once()
        self.assertEqual(connection_cls.call_args.kwargs['receive_timeout'], roles.LDAP_TIMEOUT)
        filters = [c.args[1] for c in conn.search.call_args_list]
        self.assertEqual(filters, [
            '(sAMAccountName=a\\2ab\\28c\\29)',
            '(&(sAMAccountName=a\\2ab\\28c\\29)'
            '(memberOf:1.2.840.113556.1.4.1941:=CN=ARTEK staff,OU=Groups,DC=example,DC=org))',
            '(&(sAMAccountName=a\\2ab\\28c\\29)'
            '(memberOf:1.2.840.113556.1.4.1941:=CN=x\\28y\\29,DC=org))',
        ])
        for call in conn.search.call_args_list:
            self.assertEqual(call.args[0], 'ou=Users,dc=example,dc=org')
        self.assertCountEqual(conn.search.call_args_list[0].kwargs['attributes'],
                              ['givenName', 'sn', 'mail'])

    def test_no_groups_still_reads_the_user_entry(self):
        entry = _Entry({'givenName': ['Ada'], 'sn': ['Lovelace'], 'mail': ['ada@example.org']})
        answer, connection_cls, conn = self._lookup('s990001', [], [[entry]])
        self.assertEqual(answer, roles.AdUserInfo('Ada', 'Lovelace', 'ada@example.org', {}))
        connection_cls.assert_called_once()
        self.assertEqual(conn.search.call_count, 1)

    def test_entry_not_found_gives_empty_values_not_an_error(self):
        answer, _, _ = self._lookup('s990001', [STAFF_DN], [[], []])
        self.assertEqual(answer, roles.AdUserInfo('', '', '', {STAFF_DN: False}))

    def test_missing_and_empty_attributes_give_empty_values(self):
        answer, _, _ = self._lookup(
            's990001', [], [[_Entry({'givenname': [' Ada '], 'sn': [], 'mail': ['']})]])
        self.assertEqual(answer, roles.AdUserInfo('Ada', '', '', {}))
        answer, _, _ = self._lookup('s990001', [], [[_Entry({})]])
        self.assertEqual(answer, roles.AdUserInfo('', '', '', {}))

    def test_bind_failure_raises_lookup_error_without_secrets(self):
        with mock.patch('publications.roles.ldap3.Server'), \
                mock.patch('publications.roles.ldap3.Connection',
                           side_effect=RuntimeError('bind as cn=bind with secret failed')):
            with self.assertRaises(roles.LdapLookupError) as ctx:
                roles.ad_user_info('s990001', [STAFF_DN])
        self.assertNotIn('secret', str(ctx.exception))
        self.assertNotIn('cn=bind', str(ctx.exception))

    def test_search_failure_raises_lookup_error(self):
        with mock.patch('publications.roles.ldap3.Server'), \
                mock.patch('publications.roles.ldap3.Connection') as connection_cls:
            conn = connection_cls.return_value.__enter__.return_value
            conn.search.side_effect = RuntimeError('search failed for Ada Lovelace')
            with self.assertRaises(roles.LdapLookupError) as ctx:
                roles.ad_user_info('s990001', [])
        self.assertNotIn('Lovelace', str(ctx.exception))

    @override_settings(USE_LDAP=False)
    def test_disabled_raises_without_connecting(self):
        with mock.patch('publications.roles.ldap3.Connection') as connection_cls:
            with self.assertRaises(roles.LdapLookupError):
                roles.ad_user_info('s990001', [STAFF_DN])
        connection_cls.assert_not_called()


class LdapBindIdentityTests(SimpleTestCase):
    """The LDAP bind uses the account's UPN, not a DN tied to its OU (the account was moved)."""

    def test_bind_identity_is_upn_without_ou(self):
        from django.conf import settings
        self.assertEqual(settings.AUTH_LDAP_BIND_DN, f'{settings.LDAP_BIND_USER}@win.dtu.dk')
        self.assertNotIn('ou=', settings.AUTH_LDAP_BIND_DN.lower())
