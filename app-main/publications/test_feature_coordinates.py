"""Coordinate entry: add and edit a one-point feature by its coordinates (plan "features" T6).

- Help list: the EPSG codes (4326, 4747, GR96 / UTM 18N-29N = 3178-3189, WGS84 / UTM 18N-29N
  = 32618-32629, 3857) and their names as PROJ has them. Each code transforms a fixed point
  to the expected WGS84 point. The expected values are computed here, independently of PROJ:
  UTM with the Transverse Mercator series of Snyder (USGS PP 1395, eq. 8-9 to 8-11) on GRS80
  (GR96) or WGS84, Web Mercator with its closed formula; GR96 -> WGS84 is the null
  transformation (~1 m, documented).
- Hard errors block (status 200, nothing saved): unknown EPSG code, non-numeric values,
  latitude beyond 90 after the transform.
- Warnings (outside Greenland, swapped values, UTM easting outside the zone) lead to a confirm
  page; nothing is saved before the confirmation, "Back to the form" saves nothing, "Save
  anyway" saves.
- Stored: WGS84 point, source_srid, source_geometry (WKT as entered), transform_note,
  observation_date (NULL when not given), created_by on add, modified_by always.
- Edit by coordinates: prefill from the source fields (else 4326 from points); new coordinates
  replace geometry and source fields, unchanged coordinates keep them; features with several
  points or with lines/polygons are redirected to the map edit; return to the report.
- Access matrix for add and edit (anonymous, dtu_user own/other report, artek_editor); the
  feature page offers "Edit coordinates" only for one-point features.
"""
import datetime
import math

from django.contrib.gis.gdal import SpatialReference
from django.contrib.gis.geos import GEOSGeometry, LineString, MultiLineString, MultiPoint, Point
from django.urls import reverse

from publications import geometry
from publications.forms.feature import GREENLAND_SRIDS, AddFeatureByCoordinatesForm
from publications.geometry import from_vertices, plausibility_warnings
from publications.models import Feature
from publications.test_factories import page_path
from publications.test_feature_map_edit import FeatureMapTestBase
from publications.test_feature_source_fields import stored_wkt

DAY = datetime.date(2003, 8, 1)

WGS84_ELLIPSOID = (6378137.0, 1 / 298.257223563)
GRS80_ELLIPSOID = (6378137.0, 1 / 298.257222101)


def utm_forward(lon, lat, zone, ellipsoid):
    """(easting, northing) of lon/lat (degrees) in UTM ``zone`` north (Snyder 1987, 8-9 to
    8-11); accurate to well below a millimetre this close to the central meridian."""
    a, f = ellipsoid
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    phi = math.radians(lat)
    lam = math.radians(lon)
    lam0 = math.radians(-183 + 6 * zone)
    n = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = ep2 * math.cos(phi) ** 2
    big_a = (lam - lam0) * math.cos(phi)
    m = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
             - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
             + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
             - (35 * e2 ** 3 / 3072) * math.sin(6 * phi))
    easting = k0 * n * (big_a + (1 - t + c) * big_a ** 3 / 6
                        + (5 - 18 * t + t ** 2 + 72 * c - 58 * ep2) * big_a ** 5 / 120) + 500000
    northing = k0 * (m + n * math.tan(phi) * (
        big_a ** 2 / 2 + (5 - t + 9 * c + 4 * c ** 2) * big_a ** 4 / 24
        + (61 - 58 * t + t ** 2 + 600 * c - 330 * ep2) * big_a ** 6 / 720))
    return easting, northing


def web_mercator_forward(lon, lat):
    r = 6378137.0
    return (r * math.radians(lon),
            r * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def reference_cases():
    """(srid, x, y, expected_lon, expected_lat) for every code of the help list."""
    cases = [(4326, -51.7, 64.2, -51.7, 64.2),
             (4747, -51.7, 64.2, -51.7, 64.2),   # GR96 -> WGS84: null transformation
             (3857, *web_mercator_forward(-51.7, 64.2), -51.7, 64.2)]
    for zone in range(18, 30):
        lon, lat = -183 + 6 * zone + 1.25, 72.0   # 1.25 deg east of the central meridian
        cases.append((3178 + zone - 18, *utm_forward(lon, lat, zone, GRS80_ELLIPSOID), lon, lat))
        cases.append((32618 + zone - 18, *utm_forward(lon, lat, zone, WGS84_ELLIPSOID), lon, lat))
    return cases


def form_data(x, y, srid, name='Entered', **extra):
    data = {'name': name, 'type': Feature.SAMPLE, 'date': '2003-08-01',
            'pos_quality': 'GPS (phase)', 'x_coordinate': str(x), 'y_coordinate': str(y),
            'spatial_reference_system': str(srid)}
    data.update(extra)
    return data


class SridHelpListTests(FeatureMapTestBase):

    def test_help_list_codes(self):
        codes = [code for code, _name in GREENLAND_SRIDS]
        self.assertEqual(codes, [4326, 4747, *range(3178, 3190), *range(32618, 32630), 3857])

    def test_help_list_codes_are_what_proj_calls_them(self):
        # The EPSG numbers are checked against PROJ, not guessed.
        expected = {4326: 'WGS 84', 4747: 'GR96', 3857: 'WGS 84 / Pseudo-Mercator'}
        for zone in range(18, 30):
            expected[3178 + zone - 18] = f'GR96 / UTM zone {zone}N'
            expected[32618 + zone - 18] = f'WGS 84 / UTM zone {zone}N'
        for code, _name in GREENLAND_SRIDS:
            with self.subTest(code=code):
                self.assertEqual(SpatialReference(code).name, expected[code])

    def test_the_reference_formulas(self):
        # The central meridian at the equator: easting 500 000 m, northing 0.
        easting, northing = utm_forward(-51.0, 0.0, 22, WGS84_ELLIPSOID)
        self.assertAlmostEqual(easting, 500000.0, places=6)
        self.assertAlmostEqual(northing, 0.0, places=6)

    def test_each_help_list_code_transforms_to_the_expected_wgs84_point(self):
        cases = reference_cases()
        self.assertEqual(sorted(case[0] for case in cases),
                         sorted(code for code, _name in GREENLAND_SRIDS))
        for srid, x, y, lon, lat in cases:
            with self.subTest(srid=srid):
                form = AddFeatureByCoordinatesForm(data=form_data(repr(x), repr(y), srid))
                self.assertTrue(form.is_valid(), form.errors)
                point = form.wgs84_point
                self.assertAlmostEqual(point.x, lon, delta=1e-7)   # ~1 cm or better
                self.assertAlmostEqual(point.y, lat, delta=1e-7)
                self.assertEqual(form.geometry_result.source_srid, srid)

    def test_any_other_epsg_code_is_accepted(self):
        # ETRS89 / UTM 32N (Denmark): not in the list, but PROJ knows it.
        form = AddFeatureByCoordinatesForm(data=form_data(725000, 6175000, 'EPSG:25832'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.geometry_result.source_srid, 25832)
        self.assertTrue(form.coordinate_warnings)   # outside Greenland

    def test_page_has_the_help_list_and_labels(self):
        self.login(self.dtu_own)
        response = self.client.get(page_path('add_feature_coordinates', report_pk=self.pub.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<datalist id="srid-help-list">')
        self.assertContains(response, 'list="srid-help-list"')
        for code in (4326, 4747, 3178, 3189, 32618, 32629, 3857):
            self.assertContains(response, f'<option value="{code}">')
        self.assertContains(response, 'Easting / Longitude (x)')
        self.assertContains(response, 'Northing / Latitude (y)')
        self.assertContains(response, 'GR96 or WGS84?')
        self.assertContains(response, '22: 54-48 W')   # UTM zone by longitude
        self.assertNotContains(response, 'jquery-3.7.1')   # the old label script is gone


class CoordinateErrorTests(FeatureMapTestBase):

    def add_path(self, pub=None):
        return page_path('add_feature_coordinates', report_pk=(pub or self.pub).pk)

    def test_unknown_epsg_code_is_an_error(self):
        for srid in ('999999', 'abc', '0', 'EPSG:', ''):
            with self.subTest(srid=srid):
                form = AddFeatureByCoordinatesForm(data=form_data(-51.7, 64.2, srid))
                self.assertFalse(form.is_valid())
                self.assertIn('spatial_reference_system', form.errors)

    def test_hard_errors_block_and_save_nothing(self):
        self.login(self.dtu_own)
        cases = {
            'unknown EPSG': (form_data(-51.7, 64.2, 999999), 'spatial_reference_system'),
            'non-numeric x': (form_data('abc', 64.2, 4326), 'x_coordinate'),
            'missing y': (form_data(-51.7, '', 4326), 'y_coordinate'),
            'infinite': (form_data('inf', 64.2, 4326), 'x_coordinate'),
            'latitude beyond 90': (form_data(-51.7, 95.0, 4326), '__all__'),
            'longitude beyond 180': (form_data(-200.0, 64.2, 4326), '__all__'),
            'GR96 latitude beyond 90': (form_data(-51.7, 91.0, 4747), '__all__'),
        }
        for label, (data, field) in cases.items():
            with self.subTest(case=label):
                # Even with the confirmation flag: errors are not warnings.
                for extra in ({}, {'confirm_warnings': '1'}):
                    response = self.client.post(self.add_path(), dict(data, **extra))
                    self.assertEqual(response.status_code, 200)
                    self.assertTemplateUsed(response, 'publications/add_feature_coordinates.html')
                    self.assertIn(field, response.context['form'].errors)
        self.assertFalse(Feature.objects.exists())


class CoordinateWarningTests(FeatureMapTestBase):

    def add_path(self):
        return page_path('add_feature_coordinates', report_pk=self.pub.pk)

    def test_plausibility_warnings(self):
        self.assertEqual(plausibility_warnings(4326, -51.7, 64.2), [])
        self.assertIn('swapped', plausibility_warnings(4326, 64.2, -51.7)[0])
        self.assertIn('swapped', plausibility_warnings(4747, 64.2, -51.7)[0])
        self.assertEqual(plausibility_warnings(32622, 430000, 7450000), [])
        self.assertIn('swapped', plausibility_warnings(32622, 7450000, 430000)[0])
        self.assertIn('outside the usual range', plausibility_warnings(3182, 50000, 7450000)[0])
        self.assertEqual(plausibility_warnings(3857, -5755000, 9000000), [])

    def test_warning_needs_confirmation_and_saves_nothing_before(self):
        self.login(self.dtu_own)
        data = form_data(12.5, 55.7, 4326, name='Copenhagen')   # outside Greenland
        response = self.client.post(self.add_path(), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'publications/feature_coordinates_confirm.html')
        self.assertFalse(Feature.objects.exists())
        self.assertContains(response, 'outside Greenland')
        self.assertContains(response, 'The feature is not saved yet')
        # All values are carried in hidden fields; the confirmation flag is the button.
        html = response.content.decode()
        for name, value in data.items():
            self.assertIn(f'name="{name}" value="{value}"', html)
        self.assertIn('name="confirm_warnings" value="1"', html)
        self.assertNotIn('type="hidden" name="confirm_warnings"', html)

        # Back to the form: the values are there, nothing saved.
        response = self.client.post(self.add_path(), dict(data, back='1'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'publications/add_feature_coordinates.html')
        self.assertContains(response, 'value="Copenhagen"')
        self.assertFalse(Feature.objects.exists())

        # Save anyway.
        response = self.client.post(self.add_path(), dict(data, confirm_warnings='1'))
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        feature = Feature.objects.get(name='Copenhagen')
        self.assertTrue(stored_wkt(feature, 'points').upper().startswith('MULTIPOINT'))
        self.assertEqual(feature.points.coords, ((12.5, 55.7),))
        self.assertTrue(any('outside Greenland' in message
                            for message in self.messages_of(response)))

    def test_swapped_utm_values_are_a_warning(self):
        # Easting and northing swapped in GR96 / UTM 22N: PROJ still transforms them, the
        # page asks before saving.
        self.login(self.dtu_own)
        response = self.client.post(self.add_path(), form_data(7450000, 430000, 3182))
        self.assertTemplateUsed(response, 'publications/feature_coordinates_confirm.html')
        self.assertContains(response, 'Easting and northing look swapped')
        self.assertContains(response, 'outside Greenland')
        self.assertFalse(Feature.objects.exists())

    def test_without_warnings_it_saves_at_once(self):
        self.login(self.dtu_own)
        response = self.client.post(self.add_path(), form_data(-51.7, 64.2, 4326))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Feature.objects.filter(name='Entered').exists())


class AddFeatureCoordinatesTests(FeatureMapTestBase):

    def add_path(self, pub=None):
        return page_path('add_feature_coordinates', report_pk=(pub or self.pub).pk)

    def test_source_fields_and_observation_date_are_stored(self):
        self.login(self.dtu_own)
        response = self.client.post(self.add_path(), form_data(
            430000.25, 7450000.5, 3182, name='GNSS', observation_date='2003-08-02'))
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        feature = Feature.objects.get(name='GNSS')
        self.assertEqual(feature.source_srid, 3182)
        source = GEOSGeometry(feature.source_geometry)
        self.assertEqual(source.geom_type, 'MultiPoint')
        self.assertEqual(source.coords, ((430000.25, 7450000.5),))
        self.assertTrue(feature.transform_note.startswith('EPSG:3182 -> EPSG:4326'),
                        feature.transform_note)
        self.assertIn(geometry.GR96_REMARK, feature.transform_note)
        self.assertEqual(geometry.source_origin(feature), 'entered')
        self.assertEqual(feature.observation_date, datetime.date(2003, 8, 2))
        self.assertEqual(feature.epoch_date, datetime.date(2003, 8, 2))
        self.assertEqual(feature.created_by, self.dtu_own)
        self.assertEqual(feature.modified_by, self.dtu_own)
        self.assertEqual(list(feature.publications.all()), [self.pub])
        self.assertIsNone(feature.lines)
        self.assertIsNone(feature.polys)
        # The WGS84 copy, as MariaDB has it.
        expected = from_vertices('point', [(430000.25, 7450000.5)], 3182).points[0]
        self.assertAlmostEqual(feature.points[0].x, expected.x, places=9)
        self.assertAlmostEqual(feature.points[0].y, expected.y, places=9)
        self.assertTrue(stored_wkt(feature, 'points').upper().startswith('MULTIPOINT'))

    def test_observation_date_is_null_when_not_given(self):
        self.login(self.dtu_own)
        self.client.post(self.add_path(), form_data(-51.7, 64.2, 4326, name='No GNSS date'))
        feature = Feature.objects.get(name='No GNSS date')
        self.assertIsNone(feature.observation_date)
        self.assertEqual(feature.epoch_date, DAY)
        self.assertEqual(feature.source_srid, 4326)
        self.assertEqual(feature.transform_note, 'EPSG:4326 (no transformation)')

    def test_add_page_defaults_and_cancel(self):
        self.login(self.dtu_own)
        response = self.client.get(self.add_path())
        self.assertEqual(response.context['form'].initial['spatial_reference_system'], '4326')
        self.assertFalse(response.context['editing'])
        report_url = reverse('publications:report', kwargs={'pk': self.pub.pk})
        self.assertEqual(response.context['cancel_url'], report_url)
        self.assertContains(response, f'href="{report_url}" class="btn btn-outline-secondary"')

    def test_access(self):
        path = self.add_path()
        data = form_data(-51.7, 64.2, 4326, name='Sneaked in')
        self.assertRedirectsToLogin(self.client.get(path))
        self.assertRedirectsToLogin(self.client.post(path, data))
        self.assertRedirectsToLogin(self.client.post(path, dict(data, confirm_warnings='1')))
        for user in (self.dtu_not_own, self.staff, self.no_role):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(path))
                self.assertDenied(self.client.post(path, data))
                self.assertDenied(self.client.post(path, dict(data, confirm_warnings='1')))
        # dtu_own on a report they are not listed on.
        self.login(self.dtu_own)
        self.assertDenied(self.client.post(self.add_path(self.public_pub), data))
        self.assertFalse(Feature.objects.exists())
        for user in (self.dtu_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertEqual(self.client.get(path).status_code, 200)
                response = self.client.post(path, form_data(-51.7, 64.2, 4326,
                                                            name=f'By {user.username}'))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(Feature.objects.get(name=f'By {user.username}').created_by, user)
        self.login(self.editor)
        response = self.client.post(self.add_path(self.public_pub),
                                    form_data(-51.7, 64.2, 4326, name='Editor on public'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(page_path('add_feature_coordinates',
                                                   report_pk=self.pub.pk + 1000)).status_code, 404)


class EditFeatureCoordinatesTests(FeatureMapTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Entered in GR96 / UTM 22N.
        cls.gnss = from_vertices('point', [(430000, 7450000)], 3182).apply_to(Feature(
            name='GNSS point', type=Feature.SAMPLE, date=DAY, pos_quality='GPS (phase)',
            observation_date=datetime.date(2003, 8, 2), created_by=cls.editor,
            modified_by=cls.editor))
        cls.gnss.save()
        cls.gnss.publications.add(cls.pub)
        # Registered before the source fields existed: only the WGS84 point.
        cls.old = Feature.objects.create(
            name='Old point', date=DAY, points=MultiPoint(Point(-50.5, 67.0), srid=4326))
        cls.old.publications.add(cls.pub)
        cls.two_points = Feature.objects.create(
            name='Two points', date=DAY,
            points=MultiPoint(Point(-50.5, 67.0), Point(-51.0, 67.5), srid=4326))
        cls.two_points.publications.add(cls.pub)
        cls.line = Feature.objects.create(
            name='Line', date=DAY,
            lines=MultiLineString(LineString((-50, 67), (-51, 68)), srid=4326))
        cls.line.publications.add(cls.pub)
        cls.point_and_line = Feature.objects.create(
            name='Point and line', date=DAY, points=MultiPoint(Point(-50.5, 67.0), srid=4326),
            lines=MultiLineString(LineString((-50, 67), (-51, 68)), srid=4326))
        cls.point_and_line.publications.add(cls.pub)
        cls.empty = Feature.objects.create(name='No geometry', date=DAY)
        cls.empty.publications.add(cls.pub)

    def edit_path(self, feature, report=None):
        path = page_path('edit_feature_coordinates', pk=feature.pk)
        return path if report is None else f'{path}?report={report}'

    def edit_data(self, feature, x, y, srid, **extra):
        data = form_data(x, y, srid, name=feature.name, type=feature.type,
                         date=feature.date.isoformat(), pos_quality=feature.pos_quality)
        data.update(extra)
        return data

    def test_prefill_from_the_source_fields(self):
        self.login(self.dtu_own)
        response = self.client.get(self.edit_path(self.gnss, report=self.pub.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['editing'])
        initial = response.context['form'].initial
        self.assertEqual(initial['spatial_reference_system'], '3182')
        self.assertEqual((initial['x_coordinate'], initial['y_coordinate']), (430000.0, 7450000.0))
        html = response.content.decode()
        self.assertIn('value="GNSS point"', html)
        self.assertIn('value="2003-08-02"', html)
        self.assertIn('value="3182"', html)
        self.assertIn(f'<input type="hidden" name="report" value="{self.pub.pk}">', html)

    def test_prefill_without_source_fields_is_wgs84(self):
        self.login(self.editor)
        response = self.client.get(self.edit_path(self.old))
        initial = response.context['form'].initial
        self.assertEqual(initial['spatial_reference_system'], '4326')
        self.assertEqual((initial['x_coordinate'], initial['y_coordinate']), (-50.5, 67.0))

    def test_new_coordinates_replace_geometry_and_source_fields(self):
        self.login(self.dtu_own)
        response = self.client.post(self.edit_path(self.gnss), self.edit_data(
            self.gnss, 431000, 7451000, 32622, report=self.pub.pk, observation_date=''))
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        after = Feature.objects.get(pk=self.gnss.pk)
        self.assertEqual(after.source_srid, 32622)
        self.assertEqual(GEOSGeometry(after.source_geometry).coords, ((431000.0, 7451000.0),))
        self.assertTrue(after.transform_note.startswith('EPSG:32622 -> EPSG:4326'))
        self.assertNotIn(geometry.GR96_REMARK, after.transform_note)
        expected = from_vertices('point', [(431000, 7451000)], 32622).points[0]
        self.assertAlmostEqual(after.points[0].x, expected.x, places=9)
        self.assertAlmostEqual(after.points[0].y, expected.y, places=9)
        self.assertIsNone(after.observation_date)
        self.assertEqual(after.modified_by, self.dtu_own)
        self.assertEqual(after.created_by, self.editor)   # not changed by an edit

    def test_unchanged_coordinates_keep_geometry_and_source_fields(self):
        Feature.objects.filter(pk=self.gnss.pk).update(transform_note='kept as it was')
        before = Feature.objects.get(pk=self.gnss.pk)
        self.login(self.dtu_own)
        response = self.client.post(self.edit_path(self.gnss), self.edit_data(
            self.gnss, '430000.0', '7450000.0', 'EPSG:3182', name='Renamed',
            observation_date='2003-08-03'))
        self.assertEqual(response.status_code, 302)
        after = Feature.objects.get(pk=self.gnss.pk)
        self.assertEqual(after.name, 'Renamed')
        self.assertEqual(after.observation_date, datetime.date(2003, 8, 3))
        self.assertEqual(after.transform_note, 'kept as it was')
        self.assertEqual(after.source_geometry, before.source_geometry)
        self.assertEqual(after.points.coords, before.points.coords)
        self.assertEqual(after.modified_by, self.dtu_own)

    def test_unchanged_old_feature_keeps_unknown_origin(self):
        self.login(self.editor)
        response = self.client.post(self.edit_path(self.old),
                                    self.edit_data(self.old, '-50.5', '67.0', '4326',
                                                   name='Old point, renamed'))
        self.assertEqual(response.status_code, 302)
        after = Feature.objects.get(pk=self.old.pk)
        self.assertEqual(after.name, 'Old point, renamed')
        self.assertIsNone(after.source_srid)
        self.assertEqual(geometry.source_origin(after), 'unknown')
        self.assertEqual(after.modified_by, self.editor)

    def test_edit_warning_needs_confirmation(self):
        self.login(self.editor)
        data = self.edit_data(self.old, 12.5, 55.7, 4326, report=self.pub.pk)
        response = self.client.post(self.edit_path(self.old), data)
        self.assertTemplateUsed(response, 'publications/feature_coordinates_confirm.html')
        self.assertContains(response, f'<input type="hidden" name="report" value="{self.pub.pk}">')
        self.assertEqual(Feature.objects.get(pk=self.old.pk).points.coords, ((-50.5, 67.0),))
        response = self.client.post(self.edit_path(self.old), dict(data, confirm_warnings='1'))
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        self.assertEqual(Feature.objects.get(pk=self.old.pk).points.coords, ((12.5, 55.7),))

    def test_edit_error_changes_nothing(self):
        self.login(self.editor)
        response = self.client.post(self.edit_path(self.gnss),
                                    self.edit_data(self.gnss, 1, 2, 999999, name='Broken'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Feature.objects.get(pk=self.gnss.pk).name, 'GNSS point')

    def test_other_features_go_to_the_map_edit(self):
        self.login(self.editor)
        for feature in (self.two_points, self.line, self.point_and_line, self.empty):
            with self.subTest(feature=feature.name):
                map_edit = reverse('publications:edit_feature_by_map', kwargs={'pk': feature.pk})
                response = self.client.get(self.edit_path(feature, report=self.pub.pk))
                self.assertRedirects(response, f'{map_edit}?report={self.pub.pk}',
                                     fetch_redirect_response=False)
                response = self.client.post(self.edit_path(feature),
                                            self.edit_data(feature, -50, 67, 4326,
                                                           name='Changed'))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response['Location'].startswith(map_edit))
                after = Feature.objects.get(pk=feature.pk)
                self.assertEqual(after.name, feature.name)
                self.assertIsNone(after.source_srid)

    def test_return_to_the_report_and_cancel(self):
        self.gnss.publications.add(self.public_pub)
        self.login(self.editor)
        for report in (self.pub, self.public_pub):
            with self.subTest(report=report.number):
                report_url = reverse('publications:report', kwargs={'pk': report.pk})
                response = self.client.get(self.edit_path(self.gnss, report=report.pk))
                self.assertEqual(response.context['cancel_url'], report_url)
                response = self.client.post(self.edit_path(self.gnss), self.edit_data(
                    self.gnss, 430000, 7450000, 3182, report=report.pk))
                self.assertRedirects(response, report_url, fetch_redirect_response=False)

    def test_access(self):
        path = self.edit_path(self.gnss)
        data = self.edit_data(self.gnss, 431000, 7451000, 3182, name='Sneaked in')
        self.assertRedirectsToLogin(self.client.get(path))
        self.assertRedirectsToLogin(self.client.post(path, data))
        for user in (self.dtu_not_own, self.staff, self.no_role):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(path))
                self.assertDenied(self.client.post(path, data))
                self.assertDenied(self.client.post(path, dict(data, confirm_warnings='1')))
                # Also for features that would be redirected to the map edit.
                self.assertDenied(self.client.get(self.edit_path(self.line)))
        after = Feature.objects.get(pk=self.gnss.pk)
        self.assertEqual(after.name, 'GNSS point')
        self.assertEqual(GEOSGeometry(after.source_geometry).coords, ((430000.0, 7450000.0),))
        for user in (self.dtu_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertEqual(self.client.get(path).status_code, 200)
        # A feature on a report dtu_own is not listed on: only the editor.
        other = Feature.objects.create(name='Other', date=DAY,
                                       points=MultiPoint(Point(-50.5, 67.0), srid=4326))
        other.publications.add(self.public_pub)
        self.login(self.dtu_own)
        self.assertDenied(self.client.get(self.edit_path(other)))
        self.assertDenied(self.client.post(self.edit_path(other),
                                           self.edit_data(other, -51, 67, 4326, name='Sneaked')))
        self.assertEqual(Feature.objects.get(pk=other.pk).name, 'Other')
        self.login(self.editor)
        self.assertEqual(self.client.get(self.edit_path(other)).status_code, 200)
        self.assertEqual(self.client.get(
            page_path('edit_feature_coordinates', pk=other.pk + 1000)).status_code, 404)

    def test_feature_page_link_only_for_one_point_features(self):
        cases = [(self.editor, self.gnss, True), (self.editor, self.old, True),
                 (self.dtu_own, self.gnss, True), (self.editor, self.two_points, False),
                 (self.editor, self.line, False), (self.editor, self.point_and_line, False),
                 (self.dtu_not_own, self.gnss, False), (None, self.gnss, False)]
        for user, feature, shown in cases:
            with self.subTest(user=getattr(user, 'username', 'anonymous'), feature=feature.name):
                if user is None:
                    self.client.logout()
                else:
                    self.login(user)
                response = self.client.get(page_path('feature', pk=feature.pk))
                if response.status_code in (302, 404):   # hidden report: login or no page
                    self.assertFalse(shown)
                    continue
                self.assertEqual(response.status_code, 200)
                link = reverse('publications:edit_feature_coordinates', kwargs={'pk': feature.pk})
                if shown:
                    self.assertContains(response, f'href="{link}"')
                    self.assertContains(response, 'Edit coordinates')
                else:
                    self.assertNotContains(response, link)


class GeometryCoordinateHelperTests(FeatureMapTestBase):

    def test_single_point_and_entered_point(self):
        point = Feature(name='p', date=DAY, points=MultiPoint(Point(-50.5, 67.0), srid=4326))
        self.assertEqual(geometry.single_point(point).coords, (-50.5, 67.0))
        self.assertEqual(geometry.entered_point(point), (4326, -50.5, 67.0))
        entered = from_vertices('point', [(430000, 7450000)], 3182).apply_to(
            Feature(name='e', date=DAY))
        self.assertEqual(geometry.entered_point(entered), (3182, 430000.0, 7450000.0))
        # Source geometry that is not one point: fall back to the WGS84 point.
        point.source_srid, point.source_geometry = 3182, 'LINESTRING (1 2, 3 4)'
        self.assertEqual(geometry.entered_point(point), (4326, -50.5, 67.0))
        point.source_geometry = 'not WKT'
        self.assertEqual(geometry.entered_point(point), (4326, -50.5, 67.0))
        for feature in (Feature(name='none', date=DAY),
                        Feature(name='two', date=DAY, points=MultiPoint(
                            Point(1, 2), Point(3, 4), srid=4326)),
                        Feature(name='line', date=DAY, points=point.points, lines=MultiLineString(
                            LineString((-50, 67), (-51, 68)), srid=4326))):
            with self.subTest(feature=feature.name):
                self.assertIsNone(geometry.single_point(feature))
                with self.assertRaises(ValueError):
                    geometry.entered_point(feature)
