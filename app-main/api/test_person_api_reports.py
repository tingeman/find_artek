"""Publications listed through the person API follow the report API's rule.

Confidential reports ("confidential" in ``comment``) are never listed; unverified reports
only to logged-in users (publications.visibility.visible_publications). Before this fix
/api/person/ listed number and title of every report of a person to anyone.
"""
from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from django.urls import reverse

from api.serializers import PersonSerializer
from publications.models import Authorship, Person, Publication, PubType, Supervisorship
from publications.test_upload_appendix_access import _app_path
from publications.visibility import visible_publications


class PersonApiReportVisibilityTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')

        def report(number, title, verified, comment=''):
            return Publication.objects.create(
                type=pubtype, number=number, title=title, year=1999,
                verified=verified, comment=comment)

        cls.public = report('99-01', 'Public report', verified=True)
        cls.unverified = report('99-02', 'Unverified report', verified=False)
        cls.confidential = report('99-03', 'Confidential report', verified=True,
                                  comment='Report is CONFIDENTIAL until 2030')
        cls.confidential_unverified = report('99-04', 'Confidential unverified report',
                                             verified=False, comment='confidential')

        cls.author = Person.objects.create(first='Anna', last='Author')
        cls.supervisor = Person.objects.create(first='Sven', last='Supervisor')
        for author_id, pub in enumerate(
                [cls.public, cls.unverified, cls.confidential, cls.confidential_unverified]):
            Authorship.objects.create(publication=pub, person=cls.author, author_id=author_id)
            Supervisorship.objects.create(publication=pub, person=cls.supervisor, supervisor_id=0)

        cls.user = User.objects.create_user('s990001', password='x')
        cls.list_path = _app_path(reverse('api:person-list'))

    def _detail_path(self, person):
        return _app_path(reverse('api:person-detail', kwargs={'pk': person.pk}))

    def _numbers(self, entries):
        return sorted(entry['number'] for entry in entries)

    def _person_from_list(self, person):
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)
        return next(p for p in response.json() if p['id'] == person.pk)

    def _person_from_detail(self, person):
        response = self.client.get(self._detail_path(person))
        self.assertEqual(response.status_code, 200)
        return response.json()

    # ---- anonymous ------------------------------------------------------------------

    def test_anonymous_list_shows_only_verified_public_reports(self):
        self.assertEqual(self._numbers(self._person_from_list(self.author)['authorships']), ['99-01'])
        self.assertEqual(self._numbers(self._person_from_list(self.supervisor)['supervisorships']), ['99-01'])

    def test_anonymous_detail_shows_only_verified_public_reports(self):
        self.assertEqual(self._numbers(self._person_from_detail(self.author)['authorships']), ['99-01'])
        self.assertEqual(self._numbers(self._person_from_detail(self.supervisor)['supervisorships']), ['99-01'])

    def test_anonymous_response_contains_no_hidden_titles(self):
        for path in (self.list_path, self._detail_path(self.author), self._detail_path(self.supervisor)):
            content = self.client.get(path).content.decode()
            self.assertIn('Public report', content)
            for title in ('Unverified report', 'Confidential report', 'Confidential unverified report'):
                self.assertNotIn(title, content, path)

    # ---- logged in ------------------------------------------------------------------

    def test_logged_in_list_shows_unverified_but_not_confidential(self):
        self.client.force_login(self.user)
        self.assertEqual(self._numbers(self._person_from_list(self.author)['authorships']), ['99-01', '99-02'])
        self.assertEqual(self._numbers(self._person_from_list(self.supervisor)['supervisorships']), ['99-01', '99-02'])

    def test_logged_in_detail_shows_unverified_but_not_confidential(self):
        self.client.force_login(self.user)
        self.assertEqual(self._numbers(self._person_from_detail(self.author)['authorships']), ['99-01', '99-02'])
        self.assertEqual(self._numbers(self._person_from_detail(self.supervisor)['supervisorships']), ['99-01', '99-02'])

    # ---- serializer without a request -----------------------------------------------

    def test_serializer_without_request_treats_user_as_anonymous(self):
        data = PersonSerializer(self.author).data
        self.assertEqual(self._numbers(data['authorships']), ['99-01'])

    # ---- shared rule and the report API ---------------------------------------------

    def test_visible_publications_rule(self):
        everything = Publication.objects.all()
        self.assertEqual(sorted(visible_publications(everything, None).values_list('number', flat=True)),
                         ['99-01'])
        self.assertEqual(sorted(visible_publications(everything, AnonymousUser()).values_list('number', flat=True)),
                         ['99-01'])
        self.assertEqual(sorted(visible_publications(everything, self.user).values_list('number', flat=True)),
                         ['99-01', '99-02'])

    def test_report_api_behaviour_unchanged(self):
        path = _app_path(reverse('api:report-list'))
        anonymous = self.client.get(path, {'author_id': self.author.pk})
        self.assertEqual(anonymous.status_code, 200)
        self.assertEqual(self._numbers(anonymous.json()), ['99-01'])

        self.client.force_login(self.user)
        logged_in = self.client.get(path, {'supervisor_id': self.supervisor.pk})
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(self._numbers(logged_in.json()), ['99-01', '99-02'])
