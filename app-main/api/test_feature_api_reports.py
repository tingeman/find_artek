"""Features and their publications in the feature API follow the report API's rule.

Rule since FA-R75 (plan PLAN_confidential T2; publications.visibility): anonymous users see
verified, not confidential reports; logged-in users see reports that are not confidential,
and confidential ones only if they are listed on them (author, supervisor, editor), are in
``artek_editor`` or are superusers. Before FA-R75 the keyword "confidential" in ``comment``
hid a report from everyone; now the field ``Publication.confidential`` decides, and listed
persons and artek_editor see confidential reports (tests changed deliberately).

A feature is listed only if at least one of its publications is visible; features without
any publication stay listed to everyone. Before the 2026.2.1 fix /api/feature/ listed every
feature with number and title of all its reports to anyone.
"""
import datetime
import json

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from api.serializers import FeatureSerializer
from publications.models import Authorship, Feature, Person, Publication
from publications.roles import ARTEK_EDITOR
from publications.test_factories import app_path, report_type


class FeatureApiReportVisibilityTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()

        def report(number, title, verified, confidential=False):
            return Publication.objects.create(
                type=pubtype, number=number, title=title, year=1999,
                verified=verified, confidential=confidential)

        def feature(name, *publications):
            f = Feature.objects.create(name=name, date=datetime.date(1999, 7, 1))
            f.publications.set(publications)
            return f

        cls.public = report('99-01', 'Public report', verified=True)
        cls.unverified = report('99-02', 'Unverified report', verified=False)
        cls.confidential = report('99-03', 'Confidential report', verified=True,
                                  confidential=True)

        cls.f_public = feature('F-public', cls.public)
        cls.f_unverified = feature('F-unverified', cls.unverified)
        cls.f_confidential = feature('F-confidential', cls.confidential)
        cls.f_none = feature('F-none')
        # Linked to all three reports: listed whenever the public one is, showing only
        # the visible reports.
        cls.f_mixed = feature('F-mixed', cls.public, cls.unverified, cls.confidential)

        cls.user = User.objects.create_user('s990001')
        # Listed as author of the confidential report (by id_number).
        cls.listed_user = User.objects.create_user('s990002')
        Authorship.objects.create(
            publication=cls.confidential, author_id=0,
            person=Person.objects.create(first='Li', last='Sted', id_number='s990002'))
        cls.editor = User.objects.create_user('edit')
        cls.editor.groups.add(Group.objects.get(name=ARTEK_EDITOR))
        cls.list_path = app_path(reverse('api:feature-list'))

    def _list(self, **params):
        response = self.client.get(self.list_path, params)
        self.assertEqual(response.status_code, 200)
        return {f['name']: sorted(p['number'] for p in f['related_publications'])
                for f in response.json()}

    def _detail_status(self, feature):
        return self.client.get(app_path(reverse('api:feature-detail', kwargs={'pk': feature.pk}))).status_code

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

    # ---- listed on the confidential report (FA-R75) ------------------------------------

    def test_listed_user_list(self):
        self.client.force_login(self.listed_user)
        self.assertEqual(self._list(), {
            'F-public': ['99-01'],
            'F-unverified': ['99-02'],
            'F-confidential': ['99-03'],
            'F-none': [],
            'F-mixed': ['99-01', '99-02', '99-03'],
        })

    def test_listed_user_publication_id_and_detail(self):
        self.client.force_login(self.listed_user)
        self.assertEqual(self._list(publication_id=self.confidential.pk), {
            'F-confidential': ['99-03'],
            'F-mixed': ['99-01', '99-02', '99-03'],
        })
        self.assertEqual(self._detail_status(self.f_confidential), 200)

    # ---- artek_editor (FA-R75) ----------------------------------------------------------

    def test_artek_editor_sees_everything(self):
        self.client.force_login(self.editor)
        self.assertEqual(self._list(), {
            'F-public': ['99-01'],
            'F-unverified': ['99-02'],
            'F-confidential': ['99-03'],
            'F-none': [],
            'F-mixed': ['99-01', '99-02', '99-03'],
        })
        self.assertEqual(self._detail_status(self.f_confidential), 200)

    # ---- serializer without a request -----------------------------------------------

    def test_serializer_without_request_treats_user_as_anonymous(self):
        data = FeatureSerializer(self.f_mixed).data
        self.assertEqual([p['number'] for p in data['related_publications']], ['99-01'])


class FeatureApiOverviewRecordTests(TestCase):
    """What the overview map's "reports in view" list is built from (plan "features" T18):
    every feature record carries its geometry as GeoJSON (a point-only feature as a
    MultiPoint) and ``related_publications`` lists every report of the feature the user may
    see, not only some, with id, number and title; hidden reports are absent."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.gis.geos import MultiPoint, Point

        pubtype = report_type()

        def report(number, verified=True, confidential=False):
            return Publication.objects.create(
                type=pubtype, number=number, title=f'Title {number}', year=1999,
                verified=verified, confidential=confidential)

        cls.reports = [report(f'98-0{i}') for i in range(1, 4)]
        cls.hidden = [report('98-08', verified=False), report('98-09', confidential=True)]
        cls.point_feature = Feature.objects.create(
            name='F-points', date=datetime.date(1999, 7, 1),
            points=MultiPoint(Point(-50.5, 67.0), Point(-51.0, 67.5), srid=4326))
        cls.point_feature.publications.set(cls.reports + cls.hidden)
        cls.list_path = app_path(reverse('api:feature-list'))

    def _record(self):
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)
        records = [r for r in response.json() if r['name'] == 'F-points']
        self.assertEqual(len(records), 1)
        return records[0]

    def test_point_only_feature_has_its_multipoint_geometry(self):
        record = self._record()
        geometry = json.loads(record['points'])
        self.assertEqual(geometry['type'], 'MultiPoint')
        self.assertEqual(len(geometry['coordinates']), 2)
        self.assertIsNone(record['lines'])
        self.assertIsNone(record['polys'])

    def test_anonymous_gets_every_visible_report_of_the_feature(self):
        related = self._record()['related_publications']
        self.assertEqual(sorted(related, key=lambda p: p['number']), [
            {'id': p.pk, 'number': p.number, 'title': p.title} for p in self.reports])

    def test_hidden_reports_are_absent(self):
        related = self._record()['related_publications']
        ids = {p['id'] for p in related}
        for publication in self.hidden:
            with self.subTest(number=publication.number):
                self.assertNotIn(publication.pk, ids)
