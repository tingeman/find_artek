"""publications.geometry: build, check and transform feature geometries (plan "features" T4).

Reference values for the projected systems come from an independent inverse transverse
Mercator (Krueger series to n^3, below; accurate to well below 1e-7 degrees within a UTM
zone), not from GDAL itself. Tolerances: 1e-9 degrees for EPSG:4326 (no transformation),
1e-6 degrees (about 0.1 m) for UTM and GR96 / UTM; GR96 -> WGS84 is the null transformation
(GRS80 and WGS84 differ by 0.1 mm here).

Axis order: Django's traditional GIS order, x = longitude / easting. EPSG:4747 (GR96
geographic) has lat/lon authority order; the test with it fails if GDAL used that order.
"""
import json
import math

from django.contrib.gis.geos import GEOSGeometry, MultiLineString, MultiPoint, MultiPolygon
from django.test import SimpleTestCase

from publications import geometry
from publications.geometry import GeometryError, from_geojson, from_vertices

# Ellipsoids: (semi-major axis, flattening)
WGS84_ELLIPSOID = (6378137.0, 1 / 298.257223563)
GRS80_ELLIPSOID = (6378137.0, 1 / 298.257222101)


def utm_to_lonlat(easting, northing, zone, ellipsoid=WGS84_ELLIPSOID):
    """Inverse UTM (northern hemisphere), Krueger series to n^3 (Karney 2011)."""
    a, f = ellipsoid
    k0, e0 = 0.9996, 500000.0
    n = f / (2 - f)
    big_a = a / (1 + n) * (1 + n ** 2 / 4 + n ** 4 / 64)
    beta = (n / 2 - 2 / 3 * n ** 2 + 37 / 96 * n ** 3, n ** 2 / 48 + n ** 3 / 15,
            17 / 480 * n ** 3)
    delta = (2 * n - 2 / 3 * n ** 2 - 2 * n ** 3, 7 / 3 * n ** 2 - 8 / 5 * n ** 3,
             56 / 15 * n ** 3)
    xi = northing / (k0 * big_a)
    eta = (easting - e0) / (k0 * big_a)
    xi_p = xi - sum(b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
                    for j, b in enumerate(beta, 1))
    eta_p = eta - sum(b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
                      for j, b in enumerate(beta, 1))
    chi = math.asin(math.sin(xi_p) / math.cosh(eta_p))
    lat = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(delta, 1))
    lon0 = math.radians(zone * 6 - 183)
    lon = lon0 + math.atan2(math.sinh(eta_p), math.cos(xi_p))
    return math.degrees(lon), math.degrees(lat)


def geojson(*geometries):
    return {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {}, 'geometry': g} for g in geometries]}


SQUARE = [[-51.0, 67.0], [-50.0, 67.0], [-50.0, 68.0], [-51.0, 68.0], [-51.0, 67.0]]


class GeoJsonKindTests(SimpleTestCase):

    def test_point(self):
        result = from_geojson(geojson({'type': 'Point', 'coordinates': [-51.0, 67.0]}))
        self.assertIsInstance(result.points, MultiPoint)
        self.assertEqual(result.points.srid, 4326)
        self.assertEqual(result.points.coords, ((-51.0, 67.0),))
        self.assertIsNone(result.lines)
        self.assertIsNone(result.polys)

    def test_several_points_make_one_multipoint(self):
        result = from_geojson(geojson({'type': 'Point', 'coordinates': [-51.0, 67.0]},
                                      {'type': 'Point', 'coordinates': [-52.0, 68.0]}))
        self.assertEqual(result.points.coords, ((-51.0, 67.0), (-52.0, 68.0)))

    def test_multipoint(self):
        result = from_geojson({'type': 'MultiPoint', 'coordinates': [[-51, 67], [-52, 68]]})
        self.assertEqual(len(result.points), 2)

    def test_linestring(self):
        result = from_geojson(geojson(
            {'type': 'LineString', 'coordinates': [[-51, 67], [-52, 68], [-53, 68]]}))
        self.assertIsInstance(result.lines, MultiLineString)
        self.assertEqual(result.lines.srid, 4326)
        self.assertEqual(result.lines[0].coords, ((-51, 67), (-52, 68), (-53, 68)))
        self.assertIsNone(result.points)

    def test_multilinestring(self):
        result = from_geojson({'type': 'MultiLineString', 'coordinates': [
            [[-51, 67], [-52, 68]], [[-53, 69], [-54, 70]]]})
        self.assertEqual(len(result.lines), 2)

    def test_polygon(self):
        result = from_geojson(geojson({'type': 'Polygon', 'coordinates': [SQUARE]}))
        self.assertIsInstance(result.polys, MultiPolygon)
        self.assertEqual(result.polys.srid, 4326)
        self.assertEqual(result.polys[0].exterior_ring.coords, tuple(map(tuple, SQUARE)))

    def test_polygon_with_hole(self):
        hole = [[-50.8, 67.2], [-50.2, 67.2], [-50.2, 67.8], [-50.8, 67.2]]
        result = from_geojson({'type': 'Polygon', 'coordinates': [SQUARE, hole]})
        self.assertEqual(result.polys[0].num_interior_rings, 1)

    def test_multipolygon(self):
        other = [[-40, 70], [-39, 70], [-39, 71], [-40, 70]]
        result = from_geojson({'type': 'MultiPolygon', 'coordinates': [[SQUARE], [other]]})
        self.assertEqual(len(result.polys), 2)

    def test_mixed_collection_fills_each_column(self):
        result = from_geojson(json.dumps(geojson(
            {'type': 'Point', 'coordinates': [-51.0, 67.0]},
            {'type': 'LineString', 'coordinates': [[-51, 67], [-52, 68]]},
            {'type': 'Polygon', 'coordinates': [SQUARE]})))
        self.assertEqual(len(result.points), 1)
        self.assertEqual(len(result.lines), 1)
        self.assertEqual(len(result.polys), 1)
        self.assertTrue(result.source_geometry.startswith('GEOMETRYCOLLECTION'))
        source = GEOSGeometry(result.source_geometry)
        self.assertEqual(len(source), 3)

    def test_single_feature_and_height_accepted(self):
        result = from_geojson({'type': 'Feature', 'geometry': {
            'type': 'Point', 'coordinates': [-51.0, 67.0, 120.0]}})
        self.assertEqual(result.points.coords, ((-51.0, 67.0),))

    def test_unclosed_ring_is_closed(self):
        result = from_geojson({'type': 'Polygon', 'coordinates': [SQUARE[:-1]]})
        ring = result.polys[0].exterior_ring
        self.assertEqual(ring.coords[0], ring.coords[-1])
        self.assertEqual(len(ring), 5)

    def test_rejected_input(self):
        cases = {
            'geometry collection': {'type': 'GeometryCollection', 'geometries': []},
            'unknown type': {'type': 'Circle', 'coordinates': [0, 0]},
            'empty collection': geojson(),
            'not json': 'no json {',
            'not an object': [1, 2],
            'no coordinates': {'type': 'Point'},
            'text coordinate': {'type': 'Point', 'coordinates': ['a', 67]},
            'one coordinate': {'type': 'Point', 'coordinates': [67]},
            'nan': {'type': 'Point', 'coordinates': [float('nan'), 67]},
            'line with one vertex': {'type': 'LineString', 'coordinates': [[-51, 67]]},
            'line with repeated vertex': {'type': 'LineString',
                                          'coordinates': [[-51, 67], [-51, 67]]},
            'polygon with two vertices': {'type': 'Polygon',
                                          'coordinates': [[[-51, 67], [-52, 68], [-51, 67]]]},
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(GeometryError):
                from_geojson(data)

    def test_self_intersecting_polygon(self):
        bowtie = [[-51, 67], [-50, 68], [-50, 67], [-51, 68]]
        with self.assertRaisesMessage(GeometryError, 'not valid'):
            from_geojson({'type': 'Polygon', 'coordinates': [bowtie]})

    def test_overlapping_polygons_of_one_feature(self):
        shifted = [[x + 0.5, y] for x, y in SQUARE]
        with self.assertRaisesMessage(GeometryError, 'must not overlap'):
            from_geojson(geojson({'type': 'Polygon', 'coordinates': [SQUARE]},
                                 {'type': 'Polygon', 'coordinates': [shifted]}))

    def test_error_is_value_error_with_message(self):
        with self.assertRaises(ValueError) as cm:
            from_geojson({'type': 'LineString', 'coordinates': [[-51, 67]]})
        self.assertIn('at least 2', str(cm.exception))


class VertexTests(SimpleTestCase):

    def test_point_kinds(self):
        result = from_vertices('point', [(-51.0, 67.0)], 4326)
        self.assertEqual(result.points.coords, ((-51.0, 67.0),))
        result = from_vertices('Point', [(-51.0, 67.0), (-52.0, 68.0)], '4326')
        self.assertEqual(len(result.points), 2)
        self.assertIsNone(result.lines)

    def test_line(self):
        result = from_vertices('LINE', [(-51, 67), (-52, 68)], 'EPSG:4326')
        self.assertEqual(result.lines[0].coords, ((-51, 67), (-52, 68)))
        self.assertIsNone(result.points)

    def test_polygon_closed_automatically(self):
        result = from_vertices('polygon', [(-51, 67), (-50, 67), (-50, 68)], 4326)
        ring = result.polys[0].exterior_ring
        self.assertEqual(ring.coords, ((-51, 67), (-50, 67), (-50, 68), (-51, 67)))

    def test_polygon_already_closed_is_kept(self):
        vertices = [tuple(v) for v in SQUARE]
        result = from_vertices('polygon', vertices, 4326)
        self.assertEqual(len(result.polys[0].exterior_ring), 5)

    def test_numbers_as_text(self):
        result = from_vertices('point', [('-51.5', ' 67.25 ')], 4326)
        self.assertEqual(result.points.coords, ((-51.5, 67.25),))

    def test_too_few_vertices(self):
        cases = [
            ('point', []),
            ('line', [(-51, 67)]),
            ('line', [(-51, 67), (-51, 67), (-51, 67)]),
            ('polygon', [(-51, 67), (-50, 67)]),
            ('polygon', [(-51, 67), (-50, 67), (-51, 67), (-50, 67)]),
        ]
        for kind, vertices in cases:
            with self.subTest(kind=kind, vertices=vertices), self.assertRaises(GeometryError):
                from_vertices(kind, vertices, 4326)

    def test_self_intersecting_polygon(self):
        with self.assertRaises(GeometryError):
            from_vertices('polygon', [(-51, 67), (-50, 68), (-50, 67), (-51, 68)], 4326)

    def test_unknown_kind(self):
        with self.assertRaisesMessage(GeometryError, 'Unknown geometry type'):
            from_vertices('circle', [(-51, 67)], 4326)

    def test_source_wkt_in_original_coordinates(self):
        result = from_vertices('point', [(500000, 7400000), (430000, 7450000)], 32622)
        self.assertEqual(result.source_srid, 32622)
        self.assertTrue(result.source_geometry.startswith('MULTIPOINT'))
        self.assertTrue(GEOSGeometry(result.source_geometry).equals(
            GEOSGeometry('MULTIPOINT ((500000 7400000), (430000 7450000))')))
        line = from_vertices('line', [(500000, 7400000), (430000, 7450000)], 3182)
        self.assertTrue(GEOSGeometry(line.source_geometry).equals(
            GEOSGeometry('LINESTRING (500000 7400000, 430000 7450000)')))


class SridTests(SimpleTestCase):

    def test_parse_srid(self):
        self.assertEqual(geometry.parse_srid(4326), 4326)
        self.assertEqual(geometry.parse_srid(' 32622 '), 32622)
        self.assertEqual(geometry.parse_srid('epsg:3182'), 3182)

    def test_unknown_or_invalid_epsg(self):
        for value in (999999, '999999', 'EPSG:999999', 'abc', '', None, 0, -4326, True, '43.26'):
            with self.subTest(value=value), self.assertRaises(GeometryError):
                from_vertices('point', [(500000, 7400000)], value)

    def test_unknown_epsg_message(self):
        with self.assertRaisesMessage(GeometryError, 'EPSG:999999'):
            from_geojson({'type': 'Point', 'coordinates': [1, 2]}, srid=999999)

    def test_gr96_codes(self):
        for srid in (4747, 4909, 3178, 3182, 3183, 3184, 3189):
            with self.subTest(srid=srid):
                self.assertTrue(geometry.is_gr96(srid))
        for srid in (4326, 32622, 3575):
            with self.subTest(srid=srid):
                self.assertFalse(geometry.is_gr96(srid))


class TransformTests(SimpleTestCase):
    """Transformation to EPSG:4326 and the x = lon axis order."""

    def assertLonLat(self, result, expected, places):
        point = result.points[0]
        self.assertEqual(result.points.srid, 4326)
        self.assertAlmostEqual(point.x, expected[0], places=places, msg='longitude (x)')
        self.assertAlmostEqual(point.y, expected[1], places=places, msg='latitude (y)')

    def test_4326_is_unchanged_x_is_lon(self):
        result = from_vertices('point', [(-51.123456789, 67.987654321)], 4326)
        self.assertLonLat(result, (-51.123456789, 67.987654321), places=9)

    def test_4747_gr96_geographic_x_is_lon(self):
        # Authority axis order of EPSG:4747 is lat/lon; we pass and get x = lon.
        result = from_vertices('point', [(-51.5, 67.25)], 4747)
        self.assertLonLat(result, (-51.5, 67.25), places=6)

    def test_reference_check_of_the_series(self):
        # Central meridian of zone 22 is 51 W; the equator is northing 0.
        self.assertAlmostEqual(utm_to_lonlat(500000, 0, 22)[0], -51.0, places=12)
        self.assertAlmostEqual(utm_to_lonlat(500000, 0, 22)[1], 0.0, places=12)

    def test_wgs84_utm_22n(self):
        for easting, northing in ((500000, 7400000), (430000, 7450000), (610000, 7650000)):
            with self.subTest(easting=easting, northing=northing):
                result = from_vertices('point', [(easting, northing)], 32622)
                self.assertLonLat(result, utm_to_lonlat(easting, northing, 22), places=6)

    def test_gr96_utm_22n(self):
        result = from_vertices('point', [(430000, 7450000)], 3182)
        self.assertLonLat(result, utm_to_lonlat(430000, 7450000, 22, GRS80_ELLIPSOID), places=6)
        # West of the central meridian (51 W): easting below 500000 is a smaller longitude.
        self.assertLess(result.points[0].x, -51.0)

    def test_gr96_utm_23n(self):
        result = from_vertices('point', [(560000, 7700000)], 3183)
        self.assertLonLat(result, utm_to_lonlat(560000, 7700000, 23, GRS80_ELLIPSOID), places=6)

    def test_lines_and_polygons_are_transformed(self):
        line = from_vertices('line', [(500000, 7400000), (430000, 7450000)], 32622)
        self.assertEqual(line.lines.srid, 4326)
        for (lon, lat), (e, n) in zip(line.lines[0].coords, [(500000, 7400000), (430000, 7450000)]):
            ref = utm_to_lonlat(e, n, 22)
            self.assertAlmostEqual(lon, ref[0], places=6)
            self.assertAlmostEqual(lat, ref[1], places=6)
        poly = from_vertices('polygon', [(500000, 7400000), (510000, 7400000),
                                         (510000, 7410000)], 3182)
        self.assertEqual(poly.polys.srid, 4326)
        lon, lat = poly.polys[0].exterior_ring.coords[1]
        ref = utm_to_lonlat(510000, 7400000, 22, GRS80_ELLIPSOID)
        self.assertAlmostEqual(lon, ref[0], places=6)
        self.assertAlmostEqual(lat, ref[1], places=6)

    def test_out_of_range_is_an_error(self):
        for vertex in ((-200.0, 67.0), (-51.0, 95.0), (67.0, -200.0)):
            with self.subTest(vertex=vertex), self.assertRaisesMessage(
                    GeometryError, 'out of range'):
                from_vertices('point', [vertex], 4326)

    def test_swapped_utm_coordinates_are_a_warning(self):
        # Northing and easting exchanged: PROJ finds a position far from Greenland.
        result = from_vertices('point', [(7400000, 500000)], 32622)
        self.assertEqual(len(result.warnings), 1)

    def test_impossible_projected_coordinates_are_an_error(self):
        # Far outside the domain of the projection: no finite WGS84 position.
        with self.assertRaises(GeometryError):
            from_vertices('point', [(1e12, 1e12)], 32622)

    def test_outside_greenland_is_a_warning(self):
        result = from_vertices('point', [(12.57, 55.68)], 4326)   # Copenhagen
        self.assertEqual(len(result.warnings), 1)
        self.assertIn('outside Greenland', result.warnings[0])
        self.assertIsNotNone(result.points)

    def test_inside_greenland_has_no_warning(self):
        self.assertEqual(from_vertices('point', [(-51.0, 67.0)], 4326).warnings, ())
        self.assertEqual(from_vertices('point', [(430000, 7450000)], 3182).warnings, ())


class TransformNoteTests(SimpleTestCase):

    def test_note_text(self):
        version = geometry.gdal_version()
        self.assertRegex(version, r'^\d+\.\d+\.\d+$')
        self.assertEqual(from_vertices('point', [(-51, 67)], 4326).transform_note,
                         'EPSG:4326 (no transformation)')
        self.assertEqual(from_vertices('point', [(430000, 7450000)], 32622).transform_note,
                         f'EPSG:32622 -> EPSG:4326 (PROJ via GDAL {version})')

    def test_gr96_note_is_approximate(self):
        for srid, vertex in ((3182, (430000, 7450000)), (4747, (-51, 67))):
            with self.subTest(srid=srid):
                note = from_vertices('point', [vertex], srid).transform_note
                self.assertTrue(note.startswith(f'EPSG:{srid} -> EPSG:4326 (PROJ via GDAL '))
                self.assertTrue(note.endswith(
                    '; approximate (~1 m): no time-dependent transformation'), note)
                self.assertLessEqual(len(note), 255)
