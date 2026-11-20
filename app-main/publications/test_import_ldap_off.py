"""Excel import, person resolution (register_from_file.add_persons_to_publication) with
USE_LDAP off and on (FA-R34).

Off: a study number or initials that are not in the database give the warning
"... was not found in database. Please add ... manually!" and no ldap3 call is made; a person
already in the database is matched. On: the directory is asked (find_ldap_person mocked).
All names and numbers are made up.
"""

from unittest import mock

from django.contrib import messages
from django.test import TestCase, override_settings

from publications import register_from_file
from publications.models import Authorship, Person, Supervisorship
from publications.test_factories import make_report, make_user, report_type


def _fail(*args, **kwargs):
    raise AssertionError('ldap3 must not be used here')


class _ImportCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('s990900')
        cls.pub = make_report(report_type(), '1999-90', verified=False, confidential=False)
        cls.student = Person.objects.create(first='Stu', last='Dent', id_number='s990001')
        cls.supervisor = Person.objects.create(first='Su', last='Pervisor', initials='zqsp')

    def _add(self, names, field='authors'):
        """Resolve ``names`` for ``field``; any real ldap3 use fails the test."""
        with mock.patch('publications.utils_person.ldap3.Server', side_effect=_fail) as server, \
                mock.patch('publications.utils_person.ldap3.Connection',
                           side_effect=_fail) as connection:
            result = register_from_file.add_persons_to_publication(
                names, self.pub, field, self.user)
        server.assert_not_called()
        connection.assert_not_called()
        return result

    def _people(self, model=Authorship):
        return list(model.objects.filter(publication=self.pub)
                    .values_list('person_id', flat=True))


@override_settings(USE_LDAP=False)
class ImportLdapOffTests(_ImportCase):

    def test_unknown_study_number_warns_without_ldap(self):
        result = self._add('s990123')
        self.assertEqual(result, [(
            messages.WARNING,
            "Author identified by 's990123' was not found in database. "
            "Please add author manually!")])
        self.assertEqual(self._people(), [])

    def test_unknown_initials_warn_without_ldap(self):
        result = self._add('zqxw')
        self.assertEqual(result, [(
            messages.WARNING,
            "Author identified by 'zqxw' was not found in database. "
            "Please add author manually!")])
        self.assertEqual(self._people(), [])

    def test_known_study_number_is_matched(self):
        self.assertEqual(self._add('s990001'), [])
        self.assertEqual(self._people(), [self.student.pk])

    def test_known_initials_are_matched(self):
        self.assertEqual(self._add('zqsp', field='supervisors'), [])
        self.assertEqual(self._people(Supervisorship), [self.supervisor.pk])

    def test_directory_lookup_not_called(self):
        with mock.patch('publications.utils_person.find_ldap_person') as find:
            self._add('s990123')
            self._add('zqxw')
        find.assert_not_called()


@override_settings(USE_LDAP=True)
class ImportLdapOnTests(_ImportCase):

    def test_unknown_study_number_asks_the_directory(self):
        with mock.patch('publications.utils_person.find_ldap_person',
                        return_value=[]) as find:
            result = self._add('s990123')
        find.assert_called_once_with(name='s990123')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], messages.WARNING)
        self.assertIn("'s990123' was not found in database", result[0][1])

    def test_unknown_initials_ask_the_directory(self):
        with mock.patch('publications.utils_person.find_ldap_person',
                        return_value=[]) as find:
            result = self._add('zqxw')
        find.assert_called_once_with(initials='zqxw')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], messages.WARNING)
        self.assertIn("'zqxw' was not found in database", result[0][1])

    def test_known_person_does_not_ask_the_directory(self):
        with mock.patch('publications.utils_person.find_ldap_person') as find:
            self.assertEqual(self._add('s990001'), [])
        find.assert_not_called()
        self.assertEqual(self._people(), [self.student.pk])
