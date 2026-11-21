"""Access to the person autocomplete (FA-R82, decided 2026-11-21).

The view feeds the select2 author/supervisor widgets of the report form. Anonymous users get
a JSON 403 without person data (no login redirect: select2 calls it with XHR), with or
without a term. Any logged-in user (a plain ``dtu_user`` too) gets the results as before,
including the study-number lookup. Study-number privacy itself: test_person_privacy.
"""
from django.test import TestCase

from publications.models import Person
from publications.roles import ARTEK_EDITOR
from publications.test_factories import make_user, page_path


class PersonAutocompleteAccessTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alpha = Person.objects.create(first='Acfirst', last='Autocompleton',
                                          id_number='s765432')
        cls.beta = Person.objects.create(first='Bcfirst', last='Betacomplete')
        cls.dtu_user = make_user('acdtuuser')
        cls.editor = make_user('aceditor', ARTEK_EDITOR)

    def get(self, term=None):
        params = {} if term is None else {'term': term}
        return self.client.get(page_path('person-autocomplete'), params,
                               HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def ids(self, response):
        self.assertEqual(response.status_code, 200)
        return [item['id'] for item in response.json()['results']]

    def test_anonymous_gets_json_403_without_person_data(self):
        for term in (None, '', 'Autocompleton', 's765432'):
            with self.subTest(term=term):
                response = self.get(term)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response['Content-Type'], 'application/json')
                data = response.json()
                self.assertEqual(data['results'], [])
                self.assertIn('error', data)
                raw = response.content.decode()
                for person in (self.alpha, self.beta):
                    self.assertNotIn(person.last, raw)
                    self.assertNotIn(person.first, raw)
                self.assertNotIn('s765432', raw)

    def test_logged_in_users_get_results(self):
        for user in (self.dtu_user, self.editor):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.ids(self.get('Autocompleton')), [self.alpha.pk])
                self.assertEqual(self.ids(self.get('Betacomplete')), [self.beta.pk])
                all_ids = self.ids(self.get())
                self.assertIn(self.alpha.pk, all_ids)
                self.assertIn(self.beta.pk, all_ids)
                self.client.logout()

    def test_logged_in_study_number_lookup_still_works(self):
        for user in (self.dtu_user, self.editor):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.get('s765432')
                self.assertEqual(self.ids(response), [self.alpha.pk])
                self.assertEqual(response.json()['results'][0]['text'], str(self.alpha))
                self.client.logout()
