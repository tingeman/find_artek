"""USE_LDAP from the environment (FA-R34) and the LDAP person lookup when it is off.

- find_artek.env.env_bool parses the variable: unset or empty = default, true/1/yes/on,
  false/0/no/off (case-insensitive, whitespace ignored), anything else ImproperlyConfigured.
- utils_person.find_ldap_person returns [] without touching ldap3 when USE_LDAP is False.

Login and role sync with USE_LDAP=False are covered in test_roles.py
(test_ldap_disabled_is_treated_as_failure, test_ldap_disabled_leaves_fields_unchanged,
test_disabled_raises_without_connecting).
"""

from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from find_artek.env import env_bool
from publications import utils_person


class EnvBoolTests(SimpleTestCase):

    def test_unset_gives_default(self):
        self.assertIs(env_bool('USE_LDAP', default=True, environ={}), True)
        self.assertIs(env_bool('USE_LDAP', default=False, environ={}), False)

    def test_empty_or_blank_gives_default(self):
        for raw in ('', '   ', '\t\n'):
            with self.subTest(raw=raw):
                self.assertIs(env_bool('USE_LDAP', default=True, environ={'USE_LDAP': raw}),
                              True)
                self.assertIs(env_bool('USE_LDAP', default=False, environ={'USE_LDAP': raw}),
                              False)

    def test_true_spellings(self):
        for raw in ('true', '1', 'yes', 'on', 'TRUE', 'True', 'Yes', 'ON', ' true ', '\ton\n'):
            with self.subTest(raw=raw):
                self.assertIs(env_bool('USE_LDAP', default=False, environ={'USE_LDAP': raw}),
                              True)

    def test_false_spellings(self):
        for raw in ('false', '0', 'no', 'off', 'FALSE', 'False', 'No', 'Off', ' false ', '0\n'):
            with self.subTest(raw=raw):
                self.assertIs(env_bool('USE_LDAP', default=True, environ={'USE_LDAP': raw}),
                              False)

    def test_invalid_value_raises(self):
        for raw in ('maybe', 'tru', '2', 'y', 'n', 'disabled', 'true false'):
            with self.subTest(raw=raw):
                with self.assertRaises(ImproperlyConfigured) as ctx:
                    env_bool('USE_LDAP', default=True, environ={'USE_LDAP': raw})
                self.assertIn('USE_LDAP', str(ctx.exception))
                self.assertIn(repr(raw), str(ctx.exception))

    def test_reads_os_environ_by_default(self):
        with mock.patch.dict('os.environ', {'FA_TEST_FLAG': 'off'}):
            self.assertIs(env_bool('FA_TEST_FLAG', default=True), False)
        with mock.patch.dict('os.environ', {}, clear=True):
            self.assertIs(env_bool('FA_TEST_FLAG', default=True), True)


def _fail(*args, **kwargs):
    raise AssertionError('ldap3 must not be used when USE_LDAP is False')


class FindLdapPersonTests(SimpleTestCase):

    @override_settings(USE_LDAP=False)
    def test_disabled_returns_empty_without_connecting(self):
        with mock.patch('publications.utils_person.ldap3.Server', side_effect=_fail) as server, \
                mock.patch('publications.utils_person.ldap3.Connection',
                           side_effect=_fail) as connection, \
                self.assertLogs('publications.utils_person', level='WARNING'):
            self.assertEqual(utils_person.find_ldap_person(name='s990123'), [])
            self.assertEqual(utils_person.find_ldap_person(initials='zqxw'), [])
        server.assert_not_called()
        connection.assert_not_called()

    @override_settings(USE_LDAP=True, AUTH_LDAP_SERVER_URI='ldaps://ldap.invalid',
                       AUTH_LDAP_BIND_DN='cn=bind', AUTH_LDAP_BIND_PASSWORD='secret',
                       AUTH_LDAP_USER_SEARCH_BASE='ou=Users,dc=example,dc=org')
    def test_enabled_searches_ldap(self):
        entry = object()
        with mock.patch('publications.utils_person.ldap3.Server') as server, \
                mock.patch('publications.utils_person.ldap3.Connection') as connection_cls:
            conn = connection_cls.return_value.__enter__.return_value
            conn.entries = [entry]
            result = utils_person.find_ldap_person(name='s990123')
        self.assertEqual(result, [entry])
        server.assert_called_once()
        conn.search.assert_called_once()
        self.assertEqual(conn.search.call_args.args[:2],
                         ('ou=Users,dc=example,dc=org', '(&(name=s990123))'))
