"""The report list and the map always fetch fresh data (plan release-2026-7 T2b, FA-R89).

The two page classes used to keep API results in sessionStorage per filter combination
(``reportData*``, ``featureData*``) and read them back instead of fetching, so a deleted,
added, edited or verified report (or an added or deleted feature) stayed invisible until the
browser session ended. Option A: no browser cache. There's no JS test framework (FA-R40), so
these tests read the JS sources and check that the cache isn't reintroduced unnoticed.

The session flag ``invalidate_feature_cache`` (set after adding or deleting a feature, read by
report.html to drop one cached feature list) only served that cache and is gone too. The
auth-marker clearing in base.html stays for entries left by earlier releases (test_auth_marker).
"""
import datetime

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase
from django.urls import reverse

from publications.models import Feature
from publications.test_factories import page_path
from publications.test_write_access import WriteAccessTestBase

PAGE_CLASSES = (
    'publications/js/class/my-reports-class.js',
    # The shared map component (plan "features" T3) replaced my-map-class.js. Its layer file
    # find-artek-map-layers.js keeps only the chosen base layer in localStorage
    # (test_map_component), no API data.
    'publications/js/map/find-artek-map.js',
)
# The page scripts that call the classes; they must not add a cache of their own.
PAGE_SCRIPTS = (
    'publications/js/reports.js',
    'publications/js/map.js',
    'publications/js/report.js',
    'publications/js/feature.js',
)


def read_static(path):
    found = finders.find(path)
    if not found:
        raise AssertionError(f'static file {path} not found')
    with open(found, encoding='utf-8') as handle:
        return handle.read()


class NoBrowserCacheTests(SimpleTestCase):

    def test_classes_do_not_use_session_storage(self):
        for path in PAGE_CLASSES + PAGE_SCRIPTS:
            with self.subTest(path=path):
                source = read_static(path)
                for needle in ('sessionStorage', 'localStorage', 'indexedDB'):
                    self.assertNotIn(needle, source)

    def test_classes_still_fetch_from_the_api(self):
        reports = read_static(PAGE_CLASSES[0])
        self.assertIn("'/api/report/'", reports)
        self.assertIn('await fetch(fullUrl)', reports)
        for param in ("'topic'", "'author_id'", "'supervisor_id'", "'q'"):
            self.assertIn(f'queryParams.append({param}', reports)
        features = read_static(PAGE_CLASSES[1])
        self.assertIn("'/api/feature/'", features)
        self.assertIn('await fetch(url', features)
        self.assertIn('publication_id: filters.publicationId', features)
        for source in (reports, features):
            self.assertIn('if (!response.ok)', source)


class FeatureWritesWithoutCacheFlagTests(WriteAccessTestBase):
    """Adding or deleting a feature still redirects to the report page, which renders without
    the old session flag or a per-report cache-clearing script."""

    def assertReportPageClean(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('invalidate_feature_cache', response.context)
        self.assertNotIn('invalidate_feature_cache', self.client.session)
        self.assertNotContains(response, 'featureData_report_')

    def test_add_feature_then_report_page(self):
        self.login(self.dtu_own)
        response = self.client.post(
            page_path('add_feature_coordinates', report_pk=self.pub.pk),
            {'name': 'Fresh feature', 'type': Feature.PHOTO, 'date': '2000-01-01',
             'pos_quality': 'Unknown', 'x_coordinate': '-50.5', 'y_coordinate': '67.0',
             'spatial_reference_system': '4326'})
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        self.assertNotIn('invalidate_feature_cache', self.client.session)
        feature = Feature.objects.get(name='Fresh feature')
        page = self.client.get(page_path('report', pk=self.pub.pk))
        self.assertReportPageClean(page)
        self.assertIn(feature.pk, [f.pk for f in page.context['associated_features']])

    def test_delete_feature_then_report_page(self):
        feature = Feature.objects.create(name='Doomed feature', date=datetime.date(2000, 1, 1),
                                         created_by=self.editor)
        feature.publications.add(self.pub)
        self.login(self.editor)
        response = self.client.post(page_path('delete_feature', pk=feature.pk))
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        self.assertFalse(Feature.objects.filter(pk=feature.pk).exists())
        self.assertNotIn('invalidate_feature_cache', self.client.session)
        page = self.client.get(page_path('report', pk=self.pub.pk))
        self.assertReportPageClean(page)
        self.assertNotIn(feature.pk, [f.pk for f in page.context['associated_features']])
