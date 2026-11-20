"""The report API follows the visibility rule (roadmap FA-R75, FA-R76; plan PLAN_confidential T2).

- ``/api/report/`` lists the reports the user may see (publications.visibility).
- ``/api/report/<pk>/`` works (it was always 500 before FA-R76: ``get_queryset`` had the wrong
  signature) and is 404 for a report the user may not see.
- An invalid ``q`` is a 400 (it returned a Response from inside ``get_queryset`` before).
- Every report carries the read-only flag ``confidential``.
"""
from django.test import TestCase
from django.urls import reverse

from publications.models import Authorship, Person
from publications.roles import ARTEK_EDITOR
from publications.test_factories import app_path, make_report, make_user, report_type

P, U, C, CU, CO = '99-01', '99-02', '99-03', '99-04', '99-05'
ALL = {P, U, C, CU, CO}


class ReportApiVisibilityTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()

        def report(number, verified, confidential):
            return make_report(pubtype, number, verified=verified, confidential=confidential,
                               title=f'Title of {number}')

        cls.pubs = {
            P: report(P, True, False),
            U: report(U, False, False),
            C: report(C, True, True),
            CU: report(CU, False, True),
            CO: report(CO, True, True),     # confidential, the author below not listed
        }
        author = Person.objects.create(first='Stu', last='Dent', id_number='s990001')
        for number in (P, U, C, CU):
            Authorship.objects.create(publication=cls.pubs[number], person=author, author_id=0)
        # A second person on P, so that a join on authors could duplicate rows.
        other = Person.objects.create(first='Ot', last='Her', id_number='s990002')
        Authorship.objects.create(publication=cls.pubs[P], person=other, author_id=1)
        cls.author = author

        cls.users = {
            'dtu': make_user('s990999'),
            'author': make_user('S990001'),
            'artek_editor': make_user('edit', ARTEK_EDITOR),
        }
        cls.list_path = app_path(reverse('api:report-list'))

    EXPECTED = {
        'anonymous': {P},
        'dtu': {P, U},
        'author': {P, U, C, CU},
        'artek_editor': ALL,
    }

    def login(self, key):
        self.client.logout()
        if key != 'anonymous':
            self.client.force_login(self.users[key])

    def detail_path(self, pub):
        return app_path(reverse('api:report-detail', kwargs={'pk': pub.pk}))

    def list_numbers(self, **params):
        response = self.client.get(self.list_path, params)
        self.assertEqual(response.status_code, 200)
        numbers = [r['number'] for r in response.json()]
        self.assertEqual(len(numbers), len(set(numbers)), 'duplicate rows')
        return set(numbers)

    def test_list(self):
        for key, expected in self.EXPECTED.items():
            with self.subTest(user=key):
                self.login(key)
                self.assertEqual(self.list_numbers(), expected)

    def test_list_filtered_by_author(self):
        for key, expected in self.EXPECTED.items():
            with self.subTest(user=key):
                self.login(key)
                self.assertEqual(self.list_numbers(author_id=self.author.pk),
                                 expected & {P, U, C, CU})

    def test_detail(self):
        for key, expected in self.EXPECTED.items():
            self.login(key)
            for number, pub in self.pubs.items():
                with self.subTest(user=key, report=number):
                    response = self.client.get(self.detail_path(pub))
                    if number in expected:
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json()['number'], number)
                    else:
                        self.assertEqual(response.status_code, 404)
                        self.assertNotIn(f'Title of {number}', response.content.decode())

    def test_detail_of_unknown_report_is_404(self):
        response = self.client.get(app_path(reverse('api:report-detail', kwargs={'pk': 999999})))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_list_contains_no_hidden_titles(self):
        content = self.client.get(self.list_path).content.decode()
        self.assertIn(f'Title of {P}', content)
        for number in (U, C, CU, CO):
            self.assertNotIn(f'Title of {number}', content)

    def test_confidential_flag(self):
        self.login('artek_editor')
        flags = {r['number']: r['confidential'] for r in self.client.get(self.list_path).json()}
        self.assertEqual(flags, {P: False, U: False, C: True, CU: True, CO: True})
        detail = self.client.get(self.detail_path(self.pubs[C])).json()
        self.assertIs(detail['confidential'], True)

    def test_anonymous_flag_present_and_false(self):
        detail = self.client.get(self.detail_path(self.pubs[P])).json()
        self.assertIs(detail['confidential'], False)

    def test_search(self):
        self.login('author')
        self.assertEqual(self.list_numbers(q='Title'), {P, U, C, CU})
        self.assertEqual(self.list_numbers(q=C), {C})

    def test_invalid_search_is_400(self):
        # A q of only white space has no search terms; filtering with it fails.
        response = self.client.get(self.list_path, {'q': ' '})
        self.assertEqual(response.status_code, 400)
        self.assertIn('q', response.json())

    def test_unknown_topic_is_404(self):
        response = self.client.get(self.list_path, {'topic': 'no such topic'})
        self.assertEqual(response.status_code, 404)
