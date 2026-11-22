"""Feature points are stored, not lost as NULL (FA-R101).

GEOS 3.12+ writes a MultiPoint as ``MULTIPOINT ((x y), ...)`` (each point in its own
parentheses, the OGC form). MariaDB 11.2's ``ST_GeomFromText`` returns NULL for that form
without an error, so points saved through Django were silently stored as NULL. Lines and
polygons were not affected. The tests save points through the ORM and through both add-feature
forms and read them back from the database with SQL.

Also: coordinates in another SRID (e.g. UTM 22N, EPSG:32622) are transformed to WGS84 in
Python; MariaDB has no ST_Transform, so Django's own transform in SQL fails.
"""
import datetime

from django.contrib.gis.geos import LineString, MultiLineString, MultiPoint, Point
from django.db import connection
from django.test import SimpleTestCase

from publications.fields import mariadb_multipoint_wkt
from publications.models import Feature
from publications.test_factories import page_path
from publications.test_report_access import ReportAccessTestBase


def stored_points_wkt(feature):
    """The ``points`` column as MariaDB has it (ST_AsText), or None for NULL."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT ST_AsText(points) FROM publications_feature WHERE id = %s',
                       [feature.pk])
        return cursor.fetchone()[0]


class MultiPointWktTests(SimpleTestCase):

    def test_points_lose_their_own_parentheses(self):
        self.assertEqual(mariadb_multipoint_wkt('MULTIPOINT ((-50.5 67), (1 2))'),
                         'MULTIPOINT (-50.5 67, 1 2)')

    def test_z_and_empty_and_old_form(self):
        self.assertEqual(mariadb_multipoint_wkt('MULTIPOINT Z ((1 2 3))'), 'MULTIPOINT Z (1 2 3)')
        self.assertEqual(mariadb_multipoint_wkt('MULTIPOINT EMPTY'), 'MULTIPOINT EMPTY')
        self.assertEqual(mariadb_multipoint_wkt('MULTIPOINT (1 2, 3 4)'), 'MULTIPOINT (1 2, 3 4)')


class FeaturePointsStoredTests(ReportAccessTestBase):

    def assertStoredPoints(self, feature, expected):
        """``points`` is not NULL in the database and holds ``expected`` (lon, lat) pairs."""
        self.assertIsNotNone(stored_points_wkt(feature), 'points stored as NULL')
        points = Feature.objects.get(pk=feature.pk).points
        self.assertIsNotNone(points)
        self.assertEqual(points.srid, 4326)
        self.assertEqual(len(points), len(expected))
        for point, (lon, lat) in zip(points, expected):
            self.assertAlmostEqual(point.x, lon, places=6)
            self.assertAlmostEqual(point.y, lat, places=6)

    def test_orm_save_keeps_points(self):
        feature = Feature.objects.create(
            name='ORM', date=datetime.date(2000, 1, 1),
            points=MultiPoint(Point(-50.5, 67.0), Point(-51.25, 66.5), srid=4326))
        self.assertStoredPoints(feature, [(-50.5, 67.0), (-51.25, 66.5)])

    def test_orm_update_keeps_points(self):
        feature = Feature.objects.create(name='ORM', date=datetime.date(2000, 1, 1))
        feature.points = MultiPoint(Point(-53.0, 69.25), srid=4326)
        feature.save()
        self.assertStoredPoints(feature, [(-53.0, 69.25)])

    def test_lines_still_stored(self):
        feature = Feature.objects.create(
            name='Line', date=datetime.date(2000, 1, 1),
            lines=MultiLineString(LineString((-50, 67), (-51, 68)), srid=4326))
        self.assertIsNotNone(Feature.objects.get(pk=feature.pk).lines)

    def test_point_lookup_finds_feature(self):
        # Lookups send the geometry the same way as saving does.
        feature = Feature.objects.create(
            name='ORM', date=datetime.date(2000, 1, 1),
            points=MultiPoint(Point(-50.5, 67.0), srid=4326))
        self.assertEqual(
            list(Feature.objects.filter(points__equals=MultiPoint(Point(-50.5, 67.0), srid=4326))),
            [feature])

    def post_coordinates(self, x, y, srid):
        self.client.force_login(self.dtu_own)
        return self.client.post(page_path('add_feature_coordinates', report_pk=self.pub.pk), {
            'name': 'By coordinates', 'type': Feature.PHOTO, 'date': '2000-01-01',
            'pos_quality': 'Unknown', 'x_coordinate': x, 'y_coordinate': y,
            'spatial_reference_system': srid,
        })

    def test_add_by_coordinates_keeps_point(self):
        response = self.post_coordinates('-50.5', '67.0', '4326')
        self.assertEqual(response.status_code, 302)
        self.assertStoredPoints(Feature.objects.get(name='By coordinates'), [(-50.5, 67.0)])

    def test_add_by_coordinates_in_utm_is_stored_as_wgs84(self):
        # Easting 500000 is the central meridian of UTM zone 22N (51 W).
        response = self.post_coordinates('500000', '7400000', '32622')
        self.assertEqual(response.status_code, 302)
        feature = Feature.objects.get(name='By coordinates')
        self.assertIsNotNone(stored_points_wkt(feature), 'points stored as NULL')
        point = Feature.objects.get(pk=feature.pk).points[0]
        self.assertAlmostEqual(point.x, -51.0, places=6)
        self.assertTrue(66.5 < point.y < 67.0, point.y)

    def test_add_by_map_keeps_points(self):
        self.client.force_login(self.dtu_own)
        response = self.client.post(page_path('add_feature_by_map', report_pk=self.pub.pk), {
            'name': 'By map', 'type': Feature.PHOTO, 'date': '2000-01-01', 'pos_quality': 'Unknown',
            'geojson_data': '{"type": "FeatureCollection", "features": ['
                            '{"type": "Feature", "geometry": {"type": "Point", "coordinates": [-50.5, 67.0]}},'
                            '{"type": "Feature", "geometry": {"type": "Point", "coordinates": [-51.5, 68.0]}}]}',
        })
        self.assertEqual(response.status_code, 302)
        self.assertStoredPoints(Feature.objects.get(name='By map'), [(-50.5, 67.0), (-51.5, 68.0)])
