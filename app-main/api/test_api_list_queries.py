"""The list endpoints ``/api/report/`` and ``/api/feature/`` use a fixed number of queries
(plan release-2026-7 T2a, roadmap FA-R97).

Before the fix every report cost queries for its authors, file, type and feature count, and
every feature one for its publications: ~1900 queries for ~500 reports. Now the number of
queries doesn't depend on the number of rows: the same with 1 and with 10 reports (each with
authors, a supervisor, a file, a topic, a keyword and features, one feature linked to all
reports), for anonymous users and for an artek_editor, unfiltered and filtered.
"""
import datetime

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from publications.models import Feature, FileObject
from publications.roles import ARTEK_EDITOR
from publications.test_factories import api_path, make_person, make_report, make_user, report_type


class ApiListQueryCountTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pubtype = report_type()
        cls.sue = make_person('Sue', 'Pervisor')
        cls.shared = Feature.objects.create(name='F-shared', date=datetime.date(1999, 7, 1))
        cls.editor = make_user('edit990', ARTEK_EDITOR)
        cls.count = 0

    def add_reports(self, n):
        """``n`` more reports, alternating public, unverified and confidential, each with two
        authors, a supervisor, a file, a topic, a keyword, two own features and the shared
        feature."""
        for _ in range(n):
            i = self.count = self.count + 1
            number = f'05-{i:02d}'
            pub = make_report(
                self.pubtype, number, verified=(i % 3 != 2), confidential=(i % 3 == 0),
                title=f'Permafrost report {i}',
                authors=[make_person(f'A{i}', 'First'), make_person(f'B{i}', 'Second')],
                supervisors=[self.sue], topics=['Geotechnics'], keywords=['permafrost'],
                file=FileObject.objects.create(file=f'reports/{number}.pdf'))
            for name in ('a', 'b'):
                feature = Feature.objects.create(name=f'F-{i}{name}',
                                                 date=datetime.date(1999, 7, 1))
                feature.publications.add(pub)
            self.shared.publications.add(pub)

    def queries(self, user, path, params=None):
        """Number of queries of one GET (login done before, not counted)."""
        if user is None:
            self.client.logout()
        else:
            self.client.force_login(user)
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(path, params or {})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json(), 'empty result: nothing to count')
        return len(captured)

    def requests(self):
        report = api_path('report-list')
        feature = api_path('feature-list')
        return {
            'report list': (report, None),
            'report list, topic': (report, {'topic': 'Geotechnics'}),
            'report list, supervisor_id': (report, {'supervisor_id': self.sue.pk}),
            'report list, q': (report, {'q': 'permafrost'}),
            'feature list': (feature, None),
        }

    def assert_same_count_for_1_and_10_reports(self, user):
        self.add_reports(1)
        with_one = {name: self.queries(user, *args) for name, args in self.requests().items()}
        self.add_reports(9)
        for name, args in self.requests().items():
            with self.subTest(request=name):
                self.assertEqual(self.queries(user, *args), with_one[name])

    def test_anonymous(self):
        self.assert_same_count_for_1_and_10_reports(None)

    def test_artek_editor(self):
        self.assert_same_count_for_1_and_10_reports(self.editor)

    def test_dtu_user(self):
        self.assert_same_count_for_1_and_10_reports(make_user('s990010'))

    def test_feature_with_several_publications(self):
        """The shared feature lists 1, then 10 reports: still the same count."""
        self.add_reports(1)
        path = api_path('feature-list')
        one = {label: self.queries(user, path) for label, user in
               (('anonymous', None), ('editor', self.editor))}
        self.add_reports(9)
        self.assertEqual(self.shared.publications.count(), 10)
        for label, user in (('anonymous', None), ('editor', self.editor)):
            with self.subTest(user=label):
                self.assertEqual(self.queries(user, path), one[label])
