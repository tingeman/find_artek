"""Features and their publications in the feature API follow the report API's rule.

Confidential reports ("confidential" in ``comment``) are never listed; unverified reports
only to logged-in users (publications.visibility.visible_publications). A feature is listed
only if at least one of its publications is visible; features without any publication stay
listed. Before this fix /api/feature/ listed every feature with number and title of all
its reports to anyone.
"""
import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from api.serializers import FeatureSerializer
from publications.models import Feature, Publication, PubType
from publications.test_upload_appendix_access import _app_path


class FeatureApiReportVisibilityTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')

        def report(number, title, verified, comment=''):
            return Publication.objects.create(
                type=pubtype, number=number, title=title, year=1999,
                verified=verified, comment=comment)

        def feature(name, *publications):
            f = Feature.objects.create(name=name, date=datetime.date(1999, 7, 1))
            f.publications.set(publications)
            return f

        cls.public = report('99-01', 'Public report', verified=True)
        cls.unverified = report('99-02', 'Unverified report', verified=False)
        cls.confidential = report('99-03', 'Confidential report', verified=True,
                                  comment='Report is CONFIDENTIAL until 2030')

        cls.f_public = feature('F-public', cls.public)
        cls.f_unverified = feature('F-unverified', cls.unverified)
        cls.f_confidential = feature('F-confidential', cls.confidential)
        cls.f_none = feature('F-none')
        # Linked to all three reports: listed whenever the public one is, showing only
        # the visible reports.
        cls.f_mixed = feature('F-mixed', cls.public, cls.unverified, cls.confidential)

        cls.user = User.objects.create_user('s990001', password='x')
        cls.list_path = _app_path(reverse('api:feature-list'))

    def _list(self, **params):
        response = self.client.get(self.list_path, params)
        self.assertEqual(response.status_code, 200)
        return {f['name']: sorted(p['number'] for p in f['related_publications'])
                for f in response.json()}

    def _detail_status(self, feature):
        return self.client.get(_app_path(reverse('api:feature-detail', kwargs={'pk': feature.pk}))).status_code

    # ---- anonymous ------------------------------------------------------------------

    def test_anonymous_list(self):
        self.assertEqual(self._list(), {
            'F-public': ['99-01'],
            'F-none': [],
            'F-mixed': ['99-01'],
        })

    def test_anonymous_list_contains_no_hidden_titles(self):
        content = self.client.get(self.list_path).content.decode()
        self.assertIn('Public report', content)
        self.assertNotIn('Unverified report', content)
        self.assertNotIn('Confidential report', content)

    def test_anonymous_publication_id_of_hidden_report_gives_nothing(self):
        self.assertEqual(self._list(publication_id=self.unverified.pk), {})
        self.assertEqual(self._list(publication_id=self.confidential.pk), {})

    def test_anonymous_publication_id_of_public_report(self):
        self.assertEqual(self._list(publication_id=self.public.pk), {
            'F-public': ['99-01'],
            'F-mixed': ['99-01'],
        })

    def test_anonymous_detail(self):
        self.assertEqual(self._detail_status(self.f_public), 200)
        self.assertEqual(self._detail_status(self.f_none), 200)
        self.assertEqual(self._detail_status(self.f_unverified), 404)
        self.assertEqual(self._detail_status(self.f_confidential), 404)

    # ---- logged in ------------------------------------------------------------------

    def test_logged_in_list(self):
        self.client.force_login(self.user)
        self.assertEqual(self._list(), {
            'F-public': ['99-01'],
            'F-unverified': ['99-02'],
            'F-none': [],
            'F-mixed': ['99-01', '99-02'],
        })

    def test_logged_in_publication_id(self):
        self.client.force_login(self.user)
        self.assertEqual(self._list(publication_id=self.unverified.pk), {
            'F-unverified': ['99-02'],
            'F-mixed': ['99-01', '99-02'],
        })
        self.assertEqual(self._list(publication_id=self.confidential.pk), {})

    def test_logged_in_detail(self):
        self.client.force_login(self.user)
        self.assertEqual(self._detail_status(self.f_unverified), 200)
        self.assertEqual(self._detail_status(self.f_confidential), 404)

    # ---- serializer without a request -----------------------------------------------

    def test_serializer_without_request_treats_user_as_anonymous(self):
        data = FeatureSerializer(self.f_mixed).data
        self.assertEqual([p['number'] for p in data['related_publications']], ['99-01'])
