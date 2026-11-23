"""Add and edit features by drawing on the map (plan "features" T5).

- Add (``add_feature_by_map``, ADD_FEATURE) with a point, a line, a polygon and a mix; the
  geometry is read back from MariaDB with ST_AsText (as test_feature_geometry, FA-R101). The
  source fields describe the map drawing (EPSG:4326, "digitized on the map (WGS84)").
- Edit (``edit_feature_by_map``, EDIT_FEATURE): geometry replaced, a kind no longer drawn
  becomes NULL, an attribute-only edit keeps the source fields of a feature entered in
  EPSG:3182, a geometry edit replaces them; created_by only on add, modified_by always;
  the report to return to (``report``) counts only if it is a visible report of the feature.
- Access matrix for add and edit; Edit / Delete links on the report and feature pages.
- Bad input is a form error (status 200, nothing saved): non-numeric coordinates (was a
  TypeError, 500), empty collection, GeometryCollection, self-intersecting or overlapping
  polygons, nothing drawn.
- The feature page shows the original coordinates, or "origin unknown" for old features.
- Static files: the page loads Leaflet.draw, the map component and the edit script from local
  static files (no CDN, no OSM tiles); the dead feature-map-selector.js is gone.
"""
import datetime
import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib.messages import get_messages
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils.html import escape

from publications.geometry import (
    MAP_DIGITIZED, feature_geojson, from_geojson, from_vertices, same_geometry, source_origin,
)
from publications.models import Feature, Publication
from publications.test_factories import page_path
from publications.test_feature_source_fields import stored_wkt
from publications.test_write_access import WriteAccessTestBase

DAY = datetime.date(2003, 8, 1)
APP_MAIN = Path(settings.BASE_DIR)

POINT = {'type': 'Point', 'coordinates': [-50.5, 67.0]}
POINT_2 = {'type': 'Point', 'coordinates': [-51.25, 66.75]}
LINE = {'type': 'LineString', 'coordinates': [[-51.0, 67.0], [-52.0, 68.0], [-52.5, 68.2]]}
LINE_2 = {'type': 'LineString', 'coordinates': [[-49.0, 66.0], [-48.0, 66.5]]}
POLYGON = {'type': 'Polygon', 'coordinates': [[[-51.0, 67.0], [-50.0, 67.0], [-50.0, 68.0],
                                               [-51.0, 67.0]]]}
# Edges cross (a bow tie).
BOW_TIE = {'type': 'Polygon', 'coordinates': [[[-51.0, 67.0], [-50.0, 68.0], [-50.0, 67.0],
                                               [-51.0, 68.0], [-51.0, 67.0]]]}
POLYGON_OVERLAPPING = {'type': 'Polygon', 'coordinates': [[[-50.5, 67.5], [-49.5, 67.5],
                                                           [-49.5, 68.5], [-50.5, 67.5]]]}
OUTSIDE_GREENLAND = {'type': 'Point', 'coordinates': [12.5, 55.7]}


def collection(*geometries):
    """A FeatureCollection as Leaflet.draw writes it, one Feature per geometry."""
    return json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {}, 'geometry': geometry} for geometry in geometries]})


def attributes(name='Drawn', **extra):
    data = {'name': name, 'type': Feature.BOREHOLE, 'date': '2003-08-01',
            'pos_quality': 'Approximate', 'description': 'drawn in a test'}
    data.update(extra)
    return data


class FeatureMapTestBase(WriteAccessTestBase):
    """cls.pub (unverified; author cls.dtu_own) and cls.public_pub (verified, public, nobody
    listed)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.public_pub = Publication.objects.create(
            type=cls.pubtype, title='Public report', number='99-02', year=1999, verified=True)

    def add_path(self, pub=None):
        return page_path('add_feature_by_map', report_pk=(pub or self.pub).pk)

    def edit_path(self, feature, report=None):
        path = page_path('edit_feature_by_map', pk=feature.pk)
        return path if report is None else f'{path}?report={report}'

    def assertColumns(self, feature, **expected_prefix):
        """Each geometry column as MariaDB has it: the WKT starts with the given type, or
        the column is NULL (prefix None)."""
        for column in ('points', 'lines', 'polys'):
            prefix = expected_prefix.get(column)
            wkt = stored_wkt(feature, column)
            with self.subTest(column=column):
                if prefix is None:
                    self.assertIsNone(wkt)
                else:
                    self.assertIsNotNone(wkt, f'{column} stored as NULL')
                    self.assertTrue(wkt.upper().startswith(prefix), wkt)

    def assertDrawnOnMap(self, feature):
        self.assertEqual(feature.source_srid, 4326)
        self.assertTrue(feature.transform_note.endswith(MAP_DIGITIZED), feature.transform_note)
        self.assertTrue(feature.transform_note.startswith('EPSG:4326 (no transformation)'))
        self.assertEqual(source_origin(feature), 'map')

    def messages_of(self, response):
        # Not follow=True: with FORCE_SCRIPT_NAME (release gate) the redirect has the prefix.
        return [str(message) for message in get_messages(response.wsgi_request)]


class AddFeatureByMapTests(FeatureMapTestBase):

    def test_add_each_kind_and_a_mix(self):
        cases = [
            ('point', (POINT, POINT_2), {'points': 'MULTIPOINT'}),
            ('line', (LINE,), {'lines': 'MULTILINESTRING'}),
            ('polygon', (POLYGON,), {'polys': 'MULTIPOLYGON'}),
            ('mix', (POINT, LINE, POLYGON),
             {'points': 'MULTIPOINT', 'lines': 'MULTILINESTRING', 'polys': 'MULTIPOLYGON'}),
        ]
        report_url = reverse('publications:report', kwargs={'pk': self.pub.pk})
        self.login(self.dtu_own)
        for name, geometries, columns in cases:
            with self.subTest(case=name):
                response = self.client.post(
                    self.add_path(), dict(attributes(name), geojson_data=collection(*geometries)))
                self.assertRedirects(response, report_url, fetch_redirect_response=False)
                feature = Feature.objects.get(name=name)
                self.assertColumns(feature, **columns)
                self.assertDrawnOnMap(feature)
                self.assertEqual(feature.created_by, self.dtu_own)
                self.assertEqual(feature.modified_by, self.dtu_own)
                self.assertEqual(list(feature.publications.all()), [self.pub])
                self.assertEqual(feature.type, Feature.BOREHOLE)
                if name == 'mix':
                    self.assertTrue(feature.source_geometry.startswith('GEOMETRYCOLLECTION'))
        points = Feature.objects.get(name='point').points
        self.assertEqual(points.coords, ((-50.5, 67.0), (-51.25, 66.75)))

    def test_observation_date_is_saved_and_optional(self):
        self.login(self.editor)
        self.client.post(self.add_path(), dict(attributes('With GNSS date'),
                                               observation_date='2003-08-03',
                                               geojson_data=collection(POINT)))
        self.client.post(self.add_path(), dict(attributes('Without GNSS date'),
                                               geojson_data=collection(POINT)))
        with_date = Feature.objects.get(name='With GNSS date')
        self.assertEqual(with_date.observation_date, datetime.date(2003, 8, 3))
        self.assertEqual(with_date.epoch_date, datetime.date(2003, 8, 3))
        without = Feature.objects.get(name='Without GNSS date')
        self.assertIsNone(without.observation_date)
        self.assertEqual(without.epoch_date, DAY)

    def test_warning_outside_greenland_is_a_message(self):
        self.login(self.dtu_own)
        response = self.client.post(self.add_path(), dict(
            attributes('Copenhagen'), geojson_data=collection(OUTSIDE_GREENLAND)))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Feature.objects.filter(name='Copenhagen').exists())
        self.assertTrue(any('outside Greenland' in text for text in self.messages_of(response)))

    def test_bad_geometry_is_a_form_error(self):
        cases = {
            'nothing drawn': '',
            'non-numeric coordinates': collection({'type': 'Point', 'coordinates': ['abc', 67]}),
            'non-numeric in a line': collection(
                {'type': 'LineString', 'coordinates': [[-51, 67], [None, {}]]}),
            'empty collection': collection(),
            'geometry collection': json.dumps({'type': 'GeometryCollection',
                                               'geometries': [POINT]}),
            'collection in a feature': collection({'type': 'GeometryCollection',
                                                   'geometries': [POINT]}),
            'self-intersecting polygon': collection(BOW_TIE),
            'overlapping polygons': collection(POLYGON, POLYGON_OVERLAPPING),
            'not JSON': '{"type": ',
        }
        self.login(self.dtu_own)
        for name, geojson in cases.items():
            with self.subTest(case=name):
                response = self.client.post(self.add_path(),
                                            dict(attributes(name), geojson_data=geojson))
                self.assertEqual(response.status_code, 200)
                self.assertIn('geojson_data', response.context['form'].errors)
                self.assertFalse(Feature.objects.filter(name=name).exists())
        self.assertFalse(Feature.objects.exists())

    def test_access(self):
        data = dict(attributes('Sneaked in'), geojson_data=collection(POINT))
        self.assertRedirectsToLogin(self.client.get(self.add_path()))
        self.assertRedirectsToLogin(self.client.post(self.add_path(), data))
        for user in (self.dtu_not_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(self.add_path()))
                self.assertDenied(self.client.post(self.add_path(), data))
        self.assertFalse(Feature.objects.exists())
        for user in (self.dtu_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                response = self.client.get(self.add_path())
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context['editing'])
                self.assertEqual(response.context['cancel_url'],
                                 reverse('publications:report', kwargs={'pk': self.pub.pk}))

    def test_add_page_cancel_goes_to_the_report(self):
        self.login(self.dtu_own)
        html = self.client.get(self.add_path()).content.decode()
        report_url = reverse('publications:report', kwargs={'pk': self.pub.pk})
        self.assertRegex(html, r'<a href="%s" class="btn btn-outline-secondary" id="feature-cancel">'
                         % re.escape(report_url))
        self.assertNotIn(reverse('publications:map') + '" class="btn btn-outline-secondary"', html)


class EditFeatureByMapTests(FeatureMapTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Entered in GR96 / UTM 22N (EPSG:3182), as coordinate entry (T6) will store it.
        cls.gnss = from_vertices('point', [(430000, 7450000)], 3182).apply_to(Feature(
            name='GNSS point', type=Feature.SAMPLE, date=DAY, pos_quality='GPS (phase)',
            observation_date=datetime.date(2003, 8, 2), created_by=cls.editor,
            modified_by=cls.editor))
        cls.gnss.save()
        cls.gnss.publications.add(cls.pub)
        cls.mixed = from_geojson(collection(LINE, POLYGON)).apply_to(
            Feature(name='Line and polygon', date=DAY, created_by=cls.editor))
        cls.mixed.save()
        cls.mixed.publications.add(cls.pub)
        cls.orphan = from_geojson(collection(POINT)).apply_to(Feature(name='Orphan', date=DAY))
        cls.orphan.save()

    def stored_geojson(self, feature):
        """The geometry field as the edit page fills it in."""
        self.login(self.editor)
        response = self.client.get(self.edit_path(feature))
        self.assertEqual(response.status_code, 200)
        return response.context['form'].initial['geojson_data']

    def post(self, feature, user, geojson, report=None, **data):
        self.login(user)
        post = dict(attributes(data.pop('name', feature.name)), geojson_data=geojson, **data)
        if report is not None:
            post['report'] = report
        return self.client.post(self.edit_path(feature), post)

    def test_edit_page_prefills_the_feature(self):
        self.login(self.dtu_own)
        response = self.client.get(self.edit_path(self.gnss, report=self.pub.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['editing'])
        form = response.context['form']
        self.assertEqual(form.initial['name'], 'GNSS point')
        self.assertEqual(json.loads(form.initial['geojson_data']), feature_geojson(self.gnss))
        html = response.content.decode()
        self.assertIn('value="GNSS point"', html)
        self.assertIn('value="2003-08-02"', html)   # observation date
        self.assertIn(f'data-feature-id="{self.gnss.pk}"', html)
        self.assertIn(f'<input type="hidden" name="report" value="{self.pub.pk}">', html)

    def test_attribute_only_edit_keeps_geometry_and_source_fields(self):
        before = Feature.objects.get(pk=self.gnss.pk)
        response = self.post(self.gnss, self.dtu_own, self.stored_geojson(self.gnss),
                             name='GNSS point, renamed', observation_date='2003-08-02')
        self.assertEqual(response.status_code, 302)
        after = Feature.objects.get(pk=self.gnss.pk)
        self.assertEqual(after.name, 'GNSS point, renamed')
        self.assertEqual(after.source_srid, 3182)
        self.assertEqual(after.source_geometry, before.source_geometry)
        self.assertEqual(after.transform_note, before.transform_note)
        self.assertEqual(source_origin(after), 'entered')
        self.assertEqual(after.points.coords, before.points.coords)
        self.assertEqual(after.modified_by, self.dtu_own)
        self.assertEqual(after.created_by, self.editor)   # not changed by an edit

    def test_same_geometry_written_again_by_the_editor_counts_as_unchanged(self):
        # The editor splits the MultiPoint into single Points and writes it again
        # (e.g. edit mode opened and closed without moving anything).
        lon, lat = self.gnss.points[0].coords
        geojson = collection({'type': 'Point', 'coordinates': [lon, lat]})
        self.post(self.gnss, self.editor, geojson)
        after = Feature.objects.get(pk=self.gnss.pk)
        self.assertEqual(after.source_srid, 3182)
        self.assertIn('EPSG:3182', after.transform_note)

    def test_geometry_edit_replaces_geometry_and_source_fields(self):
        response = self.post(self.gnss, self.dtu_own, collection(POINT, LINE))
        self.assertEqual(response.status_code, 302)
        after = Feature.objects.get(pk=self.gnss.pk)
        self.assertColumns(after, points='MULTIPOINT', lines='MULTILINESTRING')
        self.assertEqual(after.points.coords, ((-50.5, 67.0),))
        self.assertDrawnOnMap(after)
        self.assertTrue(after.source_geometry.startswith('GEOMETRYCOLLECTION'))
        self.assertEqual(after.modified_by, self.dtu_own)
        self.assertEqual(after.created_by, self.editor)

    def test_removed_kind_becomes_null(self):
        self.assertColumns(self.mixed, lines='MULTILINESTRING', polys='MULTIPOLYGON')
        self.post(self.mixed, self.editor, collection(POLYGON))
        after = Feature.objects.get(pk=self.mixed.pk)
        self.assertColumns(after, polys='MULTIPOLYGON')
        self.assertIsNone(after.lines)
        self.assertEqual(after.modified_by, self.editor)

    # --- T17: the editor splits the stored multi-geometries into single layers and the form
    # sends what is left as single geometries; the server joins them again.

    def two_lines_and_polygon(self):
        """A feature with a MultiLineString of 2 lines and a polygon, entered (not drawn on
        the map), so a geometry change is visible in the source fields."""
        feature = from_geojson(collection(LINE, LINE_2, POLYGON)).apply_to(
            Feature(name='Two lines and a polygon', date=DAY, created_by=self.editor))
        feature.save()
        feature.publications.add(self.pub)
        self.assertEqual(source_origin(feature), 'entered')
        return Feature.objects.get(pk=feature.pk)

    def test_one_line_removed_keeps_the_other_line_and_the_polygon(self):
        feature = self.two_lines_and_polygon()
        # As the editor writes it: polygons first, then lines (T17 drawing order).
        response = self.post(feature, self.editor, collection(POLYGON, LINE_2))
        self.assertEqual(response.status_code, 302)
        after = Feature.objects.get(pk=feature.pk)
        self.assertColumns(after, lines='MULTILINESTRING', polys='MULTIPOLYGON')
        self.assertEqual(after.lines.coords, (tuple(map(tuple, LINE_2['coordinates'])),))
        self.assertTrue(after.polys.equals_exact(feature.polys, 1e-9))
        self.assertDrawnOnMap(after)   # geometry_changed: the source fields describe the map
        self.assertNotEqual(after.source_geometry, feature.source_geometry)

    def test_polygon_removed_keeps_both_lines(self):
        feature = self.two_lines_and_polygon()
        self.post(feature, self.editor, collection(LINE, LINE_2))
        after = Feature.objects.get(pk=feature.pk)
        self.assertColumns(after, lines='MULTILINESTRING')
        self.assertIsNone(after.polys)
        self.assertTrue(after.lines.equals_exact(feature.lines, 1e-9))
        self.assertDrawnOnMap(after)

    def test_split_geometries_joined_again_equal_the_original(self):
        feature = self.two_lines_and_polygon()
        cases = {
            # Opened in the editor, a mode entered and left without changes: single
            # geometries in the drawing order (polygons first), or in the stored order.
            'drawing order': collection(POLYGON, LINE, LINE_2),
            'stored order': collection(LINE, LINE_2, POLYGON),
            # Float noise below the 1e-9 degree tolerance (T5 rule).
            'within tolerance': collection(
                {'type': 'LineString', 'coordinates': [[x + 1e-12, y] for x, y in
                                                       LINE['coordinates']]},
                LINE_2, POLYGON),
        }
        for name, geojson in cases.items():
            with self.subTest(case=name):
                form_response = self.post(feature, self.editor, geojson, name=name)
                self.assertEqual(form_response.status_code, 302)
                after = Feature.objects.get(pk=feature.pk)
                self.assertEqual(after.name, name)
                self.assertEqual(after.source_geometry, feature.source_geometry)
                self.assertEqual(after.transform_note, feature.transform_note)
                self.assertEqual(after.source_srid, feature.source_srid)
                self.assertEqual(source_origin(after), 'entered')
                self.assertEqual(after.lines.coords, feature.lines.coords)
                self.assertEqual(after.polys.coords, feature.polys.coords)

    def test_lines_in_another_order_count_as_changed(self):
        # The order of the parts is part of the stored geometry; the editor keeps it.
        feature = self.two_lines_and_polygon()
        self.post(feature, self.editor, collection(LINE_2, LINE, POLYGON))
        self.assertDrawnOnMap(Feature.objects.get(pk=feature.pk))

    def test_everything_deleted_is_the_nothing_drawn_error(self):
        # The editor empties the field when the last shape is deleted ("Clear all" too).
        feature = self.two_lines_and_polygon()
        response = self.post(feature, self.editor, '', name='Renamed')
        self.assertEqual(response.status_code, 200)
        errors = response.context['form'].errors['geojson_data']
        self.assertTrue(any('Nothing drawn on the map' in error for error in errors), errors)
        after = Feature.objects.get(pk=feature.pk)
        self.assertEqual(after.name, feature.name)
        self.assertEqual(after.source_geometry, feature.source_geometry)
        self.assertTrue(after.lines.equals_exact(feature.lines, 0))
        self.assertTrue(after.polys.equals_exact(feature.polys, 0))

    def test_bad_geometry_changes_nothing(self):
        before = Feature.objects.get(pk=self.gnss.pk)
        for geojson in (collection({'type': 'Point', 'coordinates': ['x', 'y']}), collection(),
                        '', collection(BOW_TIE)):
            with self.subTest(geojson=geojson):
                response = self.post(self.gnss, self.dtu_own, geojson, name='Changed')
                self.assertEqual(response.status_code, 200)
                self.assertIn('geojson_data', response.context['form'].errors)
        after = Feature.objects.get(pk=self.gnss.pk)
        self.assertEqual(after.name, before.name)
        self.assertEqual(after.source_srid, 3182)
        self.assertEqual(after.modified_by, self.editor)

    def test_return_to_the_given_report(self):
        self.gnss.publications.add(self.public_pub)
        for report in (self.pub, self.public_pub):
            with self.subTest(report=report.number):
                response = self.post(self.gnss, self.editor, self.stored_geojson(self.gnss),
                                     report=report.pk)
                self.assertRedirects(
                    response, reverse('publications:report', kwargs={'pk': report.pk}),
                    fetch_redirect_response=False)

    def test_foreign_or_bad_report_is_ignored(self):
        # public_pub is not a report of the feature: back to its first visible report.
        expected = reverse('publications:report', kwargs={'pk': self.pub.pk})
        for report in (self.public_pub.pk, self.pub.pk + 1000, 'x', ''):
            with self.subTest(report=report):
                response = self.post(self.gnss, self.editor, self.stored_geojson(self.gnss),
                                     report=report)
                self.assertRedirects(response, expected, fetch_redirect_response=False)
        self.login(self.editor)
        response = self.client.get(self.edit_path(self.gnss, report=self.public_pub.pk))
        self.assertEqual(response.context['return_report'], self.pub)
        self.assertEqual(response.context['cancel_url'], expected)

    def test_hidden_report_is_ignored(self):
        # The feature is on cls.pub (unverified, dtu_own listed) and on a confidential report
        # dtu_own may not see: that one doesn't count as the report to return to.
        hidden = Publication.objects.create(type=self.pubtype, title='Hidden', number='99-03',
                                            year=1999, verified=True, confidential=True)
        self.gnss.publications.add(hidden)
        response = self.post(self.gnss, self.dtu_own, self.stored_geojson(self.gnss),
                             report=hidden.pk)
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)

    def test_feature_without_report_returns_to_the_feature_page(self):
        response = self.post(self.orphan, self.editor, self.stored_geojson(self.orphan))
        self.assertRedirects(response, reverse('publications:feature',
                                               kwargs={'pk': self.orphan.pk}),
                             fetch_redirect_response=False)

    def test_access(self):
        geojson = collection(POINT_2)
        path = self.edit_path(self.gnss)
        self.assertRedirectsToLogin(self.client.get(path))
        self.assertRedirectsToLogin(self.client.post(path, dict(attributes('x'),
                                                                geojson_data=geojson)))
        for user in (self.dtu_not_own, self.staff, self.no_role):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(path))
                self.assertDenied(self.post(self.gnss, user, geojson, name='Sneaked in'))
        after = Feature.objects.get(pk=self.gnss.pk)
        self.assertEqual(after.name, 'GNSS point')
        self.assertEqual(after.source_srid, 3182)
        for user in (self.dtu_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertEqual(self.client.get(path).status_code, 200)
        # Orphan feature: only who has change_feature (artek_editor).
        self.login(self.dtu_own)
        self.assertDenied(self.client.get(self.edit_path(self.orphan)))
        self.login(self.editor)
        self.assertEqual(self.client.get(self.edit_path(self.orphan)).status_code, 200)
        self.assertEqual(self.client.get(
            page_path('edit_feature_by_map', pk=self.orphan.pk + 1000)).status_code, 404)


class FeatureLinksTests(FeatureMapTestBase):
    """Edit and Delete links on the report and feature pages follow EDIT_FEATURE and
    DELETE_FEATURE."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.feature = Feature.objects.create(name='Public feature', date=DAY)
        cls.feature.publications.add(cls.public_pub)
        cls.own_feature = Feature.objects.create(name='Own feature', date=DAY)
        cls.own_feature.publications.add(cls.pub)

    def edit_url(self, feature, report):
        return reverse('publications:edit_feature_by_map',
                       kwargs={'pk': feature.pk}) + f'?report={report.pk}'

    def test_report_page_edit_link(self):
        cases = [(None, self.public_pub, self.feature, False),
                 (self.dtu_not_own, self.public_pub, self.feature, False),
                 (self.dtu_own, self.public_pub, self.feature, False),
                 (self.editor, self.public_pub, self.feature, True),
                 (self.dtu_own, self.pub, self.own_feature, True)]
        for user, report, feature, allowed in cases:
            with self.subTest(user=getattr(user, 'username', 'anonymous'), report=report.number):
                if user is None:
                    self.client.logout()
                else:
                    self.login(user)
                response = self.client.get(page_path('report', pk=report.pk))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(feature.pk in response.context['editable_feature_ids'], allowed)
                if allowed:
                    self.assertContains(response, self.edit_url(feature, report))
                else:
                    self.assertNotContains(response, '/edit/?report=')

    def test_report_page_add_buttons(self):
        draw = reverse('publications:add_feature_by_map', kwargs={'report_pk': self.pub.pk})
        enter = reverse('publications:add_feature_coordinates', kwargs={'report_pk': self.pub.pk})
        self.login(self.dtu_own)
        response = self.client.get(page_path('report', pk=self.pub.pk))
        self.assertContains(response, 'Draw on map')
        self.assertContains(response, 'Enter coordinates')
        self.assertContains(response, draw)
        self.assertContains(response, enter)
        self.assertNotContains(response, 'Add By Map')
        self.login(self.dtu_not_own)
        response = self.client.get(page_path('report', pk=self.public_pub.pk))
        self.assertNotContains(response, 'Draw on map')
        self.assertNotContains(response, 'Enter coordinates')

    def test_feature_page_links(self):
        edit = reverse('publications:edit_feature_by_map', kwargs={'pk': self.feature.pk})
        delete = reverse('publications:delete_feature', kwargs={'pk': self.feature.pk})
        for user, allowed in ((None, False), (self.dtu_not_own, False), (self.dtu_own, False),
                              (self.editor, True)):
            with self.subTest(user=getattr(user, 'username', 'anonymous')):
                if user is None:
                    self.client.logout()
                else:
                    self.login(user)
                response = self.client.get(page_path('feature', pk=self.feature.pk))
                self.assertEqual(response.status_code, 200)
                self.assertIs(response.context['can_edit_feature'], allowed)
                self.assertIs(response.context['can_delete_feature'], allowed)
                if allowed:
                    # From the feature page, the edit returns there (T15).
                    self.assertContains(response, f'href="{edit}?next=feature"')
                    self.assertContains(response, f'href="{delete}"')
                    self.assertContains(response, 'Edit on map')
                else:
                    self.assertNotContains(response, edit)
                    self.assertNotContains(response, delete)

    def test_feature_page_links_for_a_listed_user(self):
        self.login(self.dtu_own)
        response = self.client.get(page_path('feature', pk=self.own_feature.pk))
        self.assertTrue(response.context['can_edit_feature'])
        self.assertContains(response, reverse('publications:edit_feature_by_map',
                                              kwargs={'pk': self.own_feature.pk}))


class FeaturePageSourceTests(FeatureMapTestBase):

    def page(self, feature):
        response = self.client.get(page_path('feature', pk=feature.pk))
        self.assertEqual(response.status_code, 200)
        return response

    def public_feature(self, feature):
        feature.save()
        feature.publications.add(self.public_pub)
        return feature

    def test_old_feature_origin_unknown(self):
        feature = self.public_feature(Feature(
            name='Old', date=DAY, points=from_vertices('point', [(-50.5, 67)], 4326).points))
        response = self.page(feature)
        self.assertEqual(response.context['source_origin'], 'unknown')
        self.assertContains(response, 'origin unknown')
        self.assertContains(response, 'Original coordinates')
        self.assertContains(response, 'Epoch date')
        self.assertContains(response, '2003-08-01 (the feature date)')
        self.assertNotContains(response, 'digitized on the map')

    def test_entered_feature_shows_the_source_block(self):
        result = from_vertices('point', [(430000, 7450000)], 3182)
        feature = self.public_feature(result.apply_to(Feature(
            name='GNSS', date=DAY, observation_date=datetime.date(2003, 8, 5))))
        response = self.page(feature)
        self.assertEqual(response.context['source_origin'], 'entered')
        html = response.content.decode()
        self.assertIn('EPSG:3182', html)
        self.assertIn(f'<pre class="feature-wkt">{result.source_geometry}</pre>', html)
        self.assertIn(escape(result.transform_note), html)
        self.assertIn('GNSS observation date', html)
        self.assertIn('2003-08-05', html)
        self.assertNotIn('origin unknown', html)
        self.assertNotIn('digitized on the map', html)

    def test_map_feature_says_digitized_on_the_map(self):
        self.login(self.editor)
        self.client.post(self.add_path(self.public_pub),
                         dict(attributes('On the map'), geojson_data=collection(POINT, LINE)))
        feature = Feature.objects.get(name='On the map')
        self.client.logout()
        response = self.page(feature)
        self.assertEqual(response.context['source_origin'], 'map')
        self.assertContains(response, 'digitized on the map (WGS84)')
        self.assertContains(response, 'EPSG:4326')
        self.assertContains(response, 'not given')   # no GNSS observation date

    def test_details_do_not_use_bootstrap_rows(self):
        # Bootstrap's .row has negative side margins: the first letters were cut off.
        feature = self.public_feature(Feature(name='Layout', date=DAY, description='Treatment'))
        html = self.page(feature).content.decode()
        details = html[html.index('class="details-box-left"'):html.index('class="map-box-right"')]
        self.assertNotIn('class="row"', details)
        self.assertIn('class="feature-row"', details)
        css = Path(finders.find('publications/css/feature.css')).read_text(encoding='utf-8')
        self.assertIn('.details-box-left .feature-row', css)


class GeometryHelperTests(SimpleTestCase):

    def test_feature_geojson_round_trip(self):
        feature = from_geojson(collection(POINT, POINT_2, LINE, POLYGON)).apply_to(
            Feature(name='x', date=DAY))
        data = feature_geojson(feature)
        self.assertEqual([f['geometry']['type'] for f in data['features']],
                         ['MultiPoint', 'MultiLineString', 'MultiPolygon'])
        self.assertTrue(same_geometry(from_geojson(data), feature))

    def test_same_geometry(self):
        feature = from_geojson(collection(POINT, LINE)).apply_to(Feature(name='x', date=DAY))
        self.assertTrue(same_geometry(from_geojson(collection(POINT, LINE)), feature))
        self.assertFalse(same_geometry(from_geojson(collection(POINT)), feature))
        self.assertFalse(same_geometry(from_geojson(collection(POINT_2, LINE)), feature))
        self.assertFalse(same_geometry(from_geojson(collection(POINT, LINE, POLYGON)), feature))
        moved = {'type': 'Point', 'coordinates': [-50.5, 67.00001]}   # about 1 m
        self.assertFalse(same_geometry(from_geojson(collection(moved, LINE)), feature))

    def test_source_origin(self):
        self.assertEqual(source_origin(Feature()), 'unknown')
        self.assertEqual(source_origin(from_geojson(collection(POINT)).apply_to(Feature())),
                         'entered')
        feature = Feature(source_srid=4326, source_geometry='MULTIPOINT (1 2)',
                          transform_note=f'EPSG:4326 (no transformation); {MAP_DIGITIZED}')
        self.assertEqual(source_origin(feature), 'map')


class FeatureMapStaticTests(FeatureMapTestBase):

    PAGE_FILES = (
        'publications/vendor/leaflet-1.9.4/leaflet.css',
        'publications/vendor/leaflet-1.9.4/leaflet.js',
        'publications/vendor/leaflet-draw-1.0.4/leaflet.draw.css',
        'publications/vendor/leaflet-draw-1.0.4/leaflet.draw.js',
        'publications/vendor/proj4-2.22.0/proj4.js',
        'publications/vendor/proj4leaflet-1.0.2/proj4leaflet.js',
        'publications/js/map/find-artek-map-layers.js',
        'publications/js/map/find-artek-map.js',
        'publications/js/map/find-artek-map-edit.js',
        'publications/js/feature-map-form.js',
    )

    def test_add_and_edit_pages_load_local_files(self):
        feature = Feature.objects.create(name='Static', date=DAY)
        feature.publications.add(self.pub)
        self.login(self.editor)
        for path in (self.add_path(), self.edit_path(feature)):
            with self.subTest(path=path):
                html = self.client.get(path).content.decode()
                for file in self.PAGE_FILES:
                    self.assertIsNotNone(finders.find(file), file)
                    self.assertIn(static(file), html)
                # Scripts in load order: Leaflet, Leaflet.draw, ..., component, edit, page.
                positions = [html.index(static(file)) for file in self.PAGE_FILES
                             if file.endswith('.js')]
                self.assertEqual(positions, sorted(positions))
                for needle in ('unpkg.com', 'cdnjs', 'jsdelivr.net/npm/leaflet', 'openstreetmap',
                               'arcgisonline', 'publications/images/marker'):
                    self.assertNotIn(needle, html)
                images = static('publications/vendor/leaflet-1.9.4/images/')
                self.assertIn(f'data-leaflet-images="{images}"', html)
                self.assertIn('data-geojson-input="id_geojson_data"', html)
                self.assertEqual(html.count('{% block'), 0)
        for image in ('marker-icon.png', 'marker-icon-2x.png', 'marker-shadow.png'):
            self.assertIsNotNone(finders.find(f'publications/vendor/leaflet-1.9.4/images/{image}'))

    def test_edit_script(self):
        source = Path(finders.find('publications/js/map/find-artek-map-edit.js')).read_text(
            encoding='utf-8')
        self.assertIn('FindArtekMap.prototype.enableEditing = function', source)
        for needle in ('circle: false', 'circlemarker: false', 'rectangle: false',
                       'remove: true', 'toGeoJSON(false)', 'L.Icon.Default.imagePath'):
            self.assertIn(needle, source)
        for needle in ('marker:', 'polyline:', 'polygon:'):
            self.assertIn(needle, source)
        # T17: one layer per single geometry, polygons below lines below points, and the
        # drawing raised above the report's other features once they are loaded.
        for needle in ('FindArtekMap.singleGeometries = singleGeometries',
                       "case 'MultiLineString':", "case 'GeometryCollection':",
                       'DRAW_RANK = {Polygon: 0, LineString: 1, Point: 2}',
                       'FindArtekMap.prototype.raiseEditLayer = function'):
            self.assertIn(needle, source)
        form_script = Path(finders.find('publications/js/feature-map-form.js')).read_text(
            encoding='utf-8')
        self.assertIn('findArtekMap.raiseEditLayer()', form_script)

    def test_feature_map_selector_is_gone(self):
        self.assertIsNone(finders.find('publications/js/feature-map-selector.js'))
        for path in (APP_MAIN / 'publications' / 'templates').rglob('*.html'):
            with self.subTest(template=path.name):
                self.assertNotIn('feature-map-selector', path.read_text(encoding='utf-8'))
