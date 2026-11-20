"""Fields of the person API ``/api/person/`` (plan "test coverage" T6).

Who sees ``id_number`` and ``email`` and that the contact fields never appear is tested in
publications/test_person_privacy.py; which reports are listed per person in
test_person_api_reports.py. Here: the exact set of fields (nothing else of the Person model
leaks), their values, and the order of the list.
"""
from django.test import TestCase

from publications.test_factories import api_path, make_person, make_report, make_user, report_type

FIELDS = {'id', 'id_number', 'fullname', 'first', 'middle', 'prelast', 'last', 'lineage',
          'position', 'email', 'authorships', 'supervisorships'}

# Person model fields that are never part of the API (besides person_privacy.CONTACT_FIELDS).
INTERNAL = {
    'initials': 'ini-mark', 'note': 'note-mark', 'institution': 'institution-mark',
    'department': 'department-mark', 'pre_titulation': 'pretit-mark',
    'post_titulation': 'posttit-mark', 'first_relaxed': 'frx-mark',
    'last_relaxed': 'lastrelaxed-mark',
}


class PersonApiFieldTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        cls.full = make_person('Anna', 'Berg', middle='Maria', prelast='van der', lineage='Jr',
                               position='Professor', id_number='E-11111-TEST',
                               email='anna.berg@example.org', **INTERNAL)
        cls.bare = make_person('', 'Zed')
        cls.early = make_person('Bob', 'Berg')
        cls.pub = make_report(pubtype, '99-01', verified=True, confidential=False,
                              title='A report', authors=[cls.full])
        cls.supervised = make_report(pubtype, '99-02', verified=True, confidential=False,
                                     title='Another report', supervisors=[cls.full])
        cls.user = make_user('s990001')

    def get(self, name, **kwargs):
        response = self.client.get(api_path(name, **kwargs))
        self.assertEqual(response.status_code, 200)
        return response.json(), response.content.decode()

    def responses(self):
        """(view, data of cls.full, raw JSON) from list and detail."""
        listed, raw = self.get('person-list')
        yield 'list', next(p for p in listed if p['id'] == self.full.pk), raw
        data, raw = self.get('person-detail', pk=self.full.pk)
        yield 'detail', data, raw

    def test_exact_fields(self):
        for login in (False, True):
            if login:
                self.client.force_login(self.user)
            for view, data, raw in self.responses():
                with self.subTest(view=view, logged_in=login):
                    self.assertEqual(set(data), FIELDS)
                    for field, value in INTERNAL.items():
                        self.assertNotIn(value, raw, field)

    def test_values(self):
        self.client.force_login(self.user)
        for view, data, _ in self.responses():
            with self.subTest(view=view):
                self.assertEqual(data['id'], self.full.pk)
                self.assertEqual(data['fullname'], f'Anna Maria van der Berg, Jr [pk:{self.full.pk}]')
                self.assertEqual(
                    {k: data[k] for k in ('first', 'middle', 'prelast', 'last', 'lineage',
                                          'position', 'id_number', 'email')},
                    {'first': 'Anna', 'middle': 'Maria', 'prelast': 'van der', 'last': 'Berg',
                     'lineage': 'Jr', 'position': 'Professor', 'id_number': 'E-11111-TEST',
                     'email': 'anna.berg@example.org'})
                self.assertEqual(data['authorships'],
                                 [{'id': self.pub.pk, 'number': '99-01', 'title': 'A report'}])
                self.assertEqual(data['supervisorships'], [
                    {'id': self.supervised.pk, 'number': '99-02', 'title': 'Another report'}])

    def test_empty_values_are_null(self):
        self.client.force_login(self.user)
        data, _ = self.get('person-detail', pk=self.bare.pk)
        self.assertEqual(set(data), FIELDS)
        for field in ('first', 'middle', 'prelast', 'lineage', 'position', 'id_number', 'email'):
            with self.subTest(field=field):
                self.assertIsNone(data[field])
        self.assertEqual(data['last'], 'Zed')
        self.assertEqual(data['authorships'], [])
        self.assertEqual(data['supervisorships'], [])

    def test_list_ordered_by_last_then_first_name(self):
        listed, _ = self.get('person-list')
        self.assertEqual([p['id'] for p in listed], [self.full.pk, self.early.pk, self.bare.pk])
        self.assertEqual([(p['last'], p['first']) for p in listed],
                         [('Berg', 'Anna'), ('Berg', 'Bob'), ('Zed', None)])

    def test_unknown_person_is_404(self):
        response = self.client.get(api_path('person-detail', pk=999999))
        self.assertEqual(response.status_code, 404)
