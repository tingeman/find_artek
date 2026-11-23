"""Coverage outline, the underlay clipped outside it, and the box-zoom button (plan "features"
T22, T23).

- The coverage outline (publications/static/publications/data/greenland_topo_coverage.geojson,
  made by ``manage.py make_greenland_coverage`` from Natural Earth 10m land): a WGS84 GeoJSON
  (Multi)Polygon around Greenland, a few hundred vertices, inside lon -75..-10, lat 59..84,
  covering the towns and the wide fjords and bays (Scoresby Sund, Disko Bay, Vaigat; T23) and
  not Iceland, Canada or the open sea.
- The management command, on made-up polygons (no Natural Earth file in the tests): Greenland
  is the largest polygon, nearby islands are kept, islands nearer another large landmass and
  far polygons are left out, the buffer reaches seaward; T23: ``--fill-km`` closes a fjord
  (``0`` doesn't), other large landmasses are cut out with a margin, bad arguments are refused.
- find-artek-map-layers.js (T23, deliberate change of T22's TopographicClipTests): the
  topographic layer is no longer clipped; instead the Arctic SDI underlay is clipped per zoom
  level to the outside of the outline (a large rectangle minus the outline, even-odd), only
  while the topographic map is the base layer; hidden while the outline loads, unclipped if it
  can't be loaded; the outline is fetched once from the URL next to the script.
- find-artek-map.js: a box-zoom button under +/- on the overview, report and feature maps, not
  on edit maps (dragging draws there) or the import preview. T23 (deliberate change): it stays
  armed after a box zoom; a second click, Escape or the mouse wheel over the map disarm it.

There is no JS test runner (FA-R40): the JS checks read the sources; the behaviour was checked
in an offline headless browser with stub tiles and is checked by hand in the browser.
"""
import io
import json
import os
import re
import tempfile

from django.contrib.gis.geos import GEOSGeometry, Point
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from publications.management.commands import make_greenland_coverage as command
from publications.test_map_styles import code_only, css_rule, read_static

COVERAGE = 'publications/data/greenland_topo_coverage.geojson'
LAYERS = 'publications/js/map/find-artek-map-layers.js'
COMPONENT = 'publications/js/map/find-artek-map.js'
MAP_CSS = 'publications/css/find-artek-map.css'
PAGE_SCRIPTS = {
    'publications/js/map.js': "mode: 'overview'",
    'publications/js/report.js': "mode: 'report'",
    'publications/js/feature.js': "mode: 'feature'",
}
EDIT_SCRIPT = 'publications/js/feature-map-form.js'
PREVIEW_SCRIPT = 'publications/js/feature-import-preview.js'


def coverage_geometry():
    data = json.loads(read_static(COVERAGE))
    geometry = GEOSGeometry(json.dumps(data['features'][0]['geometry']))
    geometry.srid = 4326
    return data, geometry


class CoverageFileTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data, cls.geometry = coverage_geometry()

    def test_is_one_feature_with_a_polygon(self):
        self.assertEqual(self.data['type'], 'FeatureCollection')
        self.assertEqual(len(self.data['features']), 1)
        self.assertIn(self.data['features'][0]['geometry']['type'], ('Polygon', 'MultiPolygon'))
        self.assertTrue(self.geometry.valid, self.geometry.valid_reason)
        # GeoJSON is WGS84 lon/lat; no "crs" member (RFC 7946).
        self.assertNotIn('crs', self.data)

    def test_source_and_licence_are_named(self):
        properties = self.data['features'][0]['properties']
        self.assertIn('Natural Earth', properties['source'])
        self.assertIn('public domain', properties['source'])
        self.assertIn('make_greenland_coverage', properties['source'])
        # Made with the command's defaults (fjords closed with 45 km, 12 km seaward, 2.5 km
        # tolerance).
        self.assertEqual(properties['fill_km'], 45.0)
        self.assertEqual(properties['buffer_km'], 12.0)
        self.assertEqual(properties['tolerance_km'], 2.5)

    def test_box_is_inside_greenland_box_in_lon_lat_order(self):
        lon_min, lat_min, lon_max, lat_max = self.geometry.extent
        self.assertGreaterEqual(lon_min, -75)
        self.assertLessEqual(lon_max, -10)
        self.assertGreaterEqual(lat_min, 59)
        self.assertLessEqual(lat_max, 84)
        # Covers Greenland from Kap Farvel to Peary Land, not just a part.
        self.assertLess(lat_min, 60)
        self.assertGreater(lat_max, 83.5)
        self.assertLess(lon_min, -72)
        self.assertGreater(lon_max, -12)

    def test_vertex_count_and_size_are_small(self):
        self.assertGreaterEqual(self.geometry.num_coords, 100)
        self.assertLessEqual(self.geometry.num_coords, 1500)
        self.assertLess(len(read_static(COVERAGE)), 30_000)
        positions = re.findall(r'\[(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)\]', read_static(COVERAGE))
        self.assertEqual(len(positions), self.geometry.num_coords)
        for lon, lat in positions:
            self.assertLessEqual(len(lon.partition('.')[2]), command.DECIMALS)
            self.assertLessEqual(len(lat.partition('.')[2]), command.DECIMALS)

    def test_rings_are_closed(self):
        geometry = self.data['features'][0]['geometry']
        polygons = ([geometry['coordinates']] if geometry['type'] == 'Polygon'
                    else geometry['coordinates'])
        for polygon in polygons:
            for ring in polygon:
                self.assertGreaterEqual(len(ring), 4)
                self.assertEqual(ring[0], ring[-1])

    def test_covers_greenland_not_its_neighbours_or_the_open_sea(self):
        inside = {'Nuuk': (-51.72, 64.18), 'Ilulissat': (-51.10, 69.22),
                  'Tasiilaq': (-37.63, 65.61), 'Qaanaaq': (-69.23, 77.47),
                  'Summit': (-38.46, 72.58), 'Danmarkshavn': (-18.67, 76.77),
                  'Narsarsuaq': (-45.43, 61.16)}
        outside = {'Reykjavik': (-21.94, 64.15), 'Iqaluit': (-68.52, 63.75),
                   'Ellesmere (Eureka)': (-85.94, 79.99), 'Svalbard': (15.6, 78.2),
                   'Davis Strait': (-57.0, 66.0), 'Denmark Strait': (-27.0, 67.0),
                   'Greenland Sea': (-10.5, 75.0), 'Labrador Sea': (-50.0, 59.5)}
        for name, (lon, lat) in inside.items():
            with self.subTest(name=name):
                self.assertTrue(self.geometry.contains(Point(lon, lat, srid=4326)))
        for name, (lon, lat) in outside.items():
            with self.subTest(name=name):
                self.assertFalse(self.geometry.contains(Point(lon, lat, srid=4326)))

    def test_covers_the_wide_fjords_not_the_large_neighbours(self):
        # T23: the fjords and bays that are blue on the topographic map are inside the outline
        # (the Arctic basemap must not show there); Ellesmere and Iceland are cut out.
        inside = {'Scoresby Sund': (-24.5, 70.5), 'Disko Bay': (-52.5, 69.0),
                  'Vaigat': (-53.5, 70.1)}
        outside = {'Ellesmere': (-75.0, 80.0), 'Iceland': (-19.0, 64.9)}
        for name, (lon, lat) in inside.items():
            with self.subTest(name=name):
                self.assertTrue(self.geometry.contains(Point(lon, lat, srid=4326)))
        for name, (lon, lat) in outside.items():
            with self.subTest(name=name):
                self.assertFalse(self.geometry.contains(Point(lon, lat, srid=4326)))

    def test_natural_earth_files_are_not_in_the_repository(self):
        # Only the outline is committed, not the source data (ne_10m_land.*).
        static_dir = os.path.dirname(finders.find(COVERAGE))
        self.assertEqual(sorted(os.listdir(static_dir)), ['greenland_topo_coverage.geojson'])


def square(lon_min, lat_min, lon_max, lat_max):
    return [[[lon_min, lat_min], [lon_max, lat_min], [lon_max, lat_max], [lon_min, lat_max],
             [lon_min, lat_min]]]


def feature(geometry_type, coordinates):
    return {'type': 'Feature', 'properties': {},
            'geometry': {'type': geometry_type, 'coordinates': coordinates}}


# Made-up land: a "Greenland" (with a small island 4 km off its east coast, in one
# MultiPolygon), a large "Canada" 100 km to the west with an island 8 km off its coast (88 km
# from "Greenland": nearer Canada), an "Iceland" and a polygon outside the box.
MAINLAND = square(-50, 65, -40, 75)
EAST_ISLAND = square(-39.9, 70.0, -39.8, 70.05)
CANADA = square(-66, 67, -52.5, 71)
CANADA_ISLAND = square(-52.3, 69.0, -52.2, 69.05)
ICELAND = square(-24, 63.5, -14, 66)
FAR_AWAY = square(10, 60, 20, 70)
LAND = {'type': 'FeatureCollection', 'features': [
    feature('MultiPolygon', [MAINLAND, EAST_ISLAND]),
    feature('Polygon', CANADA),
    feature('Polygon', CANADA_ISLAND),
    feature('Polygon', ICELAND),
    feature('Polygon', FAR_AWAY),
]}

# T23: the same "Greenland" with a fjord in its east coast, 0.4 degrees (about 44 km) wide and
# 4 degrees of longitude (about 150 km) long, and nothing else.
FJORD_MAINLAND = [[[-50, 65], [-40, 65], [-40, 69.8], [-44, 69.8], [-44, 70.2], [-40, 70.2],
                   [-40, 75], [-50, 75], [-50, 65]]]
FJORD_LAND = {'type': 'FeatureCollection', 'features': [feature('Polygon', FJORD_MAINLAND)]}
# T23: a large landmass ("Ellesmere", about 115 000 km2) 0.5 degrees of longitude (about 15 km
# at lat 74) west of "Greenland".
NEAR_LARGE = square(-62, 73, -50.5, 76)
NEAR_LARGE_LAND = {'type': 'FeatureCollection', 'features': [
    feature('Polygon', MAINLAND), feature('Polygon', NEAR_LARGE)]}


class MakeCoverageCommandTests(SimpleTestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = os.path.join(self.directory.name, 'out', 'coverage.geojson')

    def write_land(self, data):
        path = os.path.join(self.directory.name, 'land.geojson')
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(data, handle)
        return path

    def run_command(self, data=LAND, *arguments):
        call_command('make_greenland_coverage', self.write_land(data), '--output', self.output,
                     *arguments, stdout=io.StringIO())
        with open(self.output, encoding='utf-8') as handle:
            data = json.load(handle)
        geometry = GEOSGeometry(json.dumps(data['features'][0]['geometry']))
        geometry.srid = 4326
        return data, geometry

    def assertCovers(self, geometry, lon, lat, expected=True):
        self.assertEqual(geometry.contains(Point(lon, lat, srid=4326)), expected, (lon, lat))

    def test_greenland_and_its_island_buffered_seaward(self):
        data, geometry = self.run_command(LAND, '--buffer-km', '10', '--tolerance-km', '1')
        self.assertEqual(data['features'][0]['geometry']['type'], 'MultiPolygon')
        self.assertTrue(geometry.valid)
        self.assertCovers(geometry, -45, 70)            # inland
        self.assertCovers(geometry, -39.85, 70.025)     # the east island
        # East coast at lon -40, lat 72: 1 degree of longitude is about 34.5 km there.
        self.assertCovers(geometry, -39.88, 72)         # about 4 km offshore
        self.assertCovers(geometry, -39.45, 72, False)  # about 19 km offshore
        self.assertCovers(geometry, -52.25, 69.025, False)    # Canada's island
        self.assertCovers(geometry, -60, 69, False)            # Canada
        self.assertCovers(geometry, -19, 65, False)            # Iceland
        self.assertCovers(geometry, 15, 65, False)             # outside the box
        self.assertEqual(data['features'][0]['properties']['buffer_km'], 10.0)
        self.assertIn('Natural Earth', data['features'][0]['properties']['source'])

    def test_larger_buffer_reaches_farther(self):
        _, geometry = self.run_command(LAND, '--buffer-km', '25', '--tolerance-km', '1')
        self.assertCovers(geometry, -39.45, 72)         # about 19 km offshore

    def test_coordinates_are_rounded(self):
        self.run_command(LAND, '--buffer-km', '10', '--tolerance-km', '1')
        with open(self.output, encoding='utf-8') as handle:
            text = handle.read()
        self.assertIsNone(re.search(r'\.\d{5,}', text))

    def test_fill_closes_a_fjord(self):
        # The middle of the fjord is about 22 km from both shores: the 10 km buffer alone
        # doesn't reach it; closing with 40 km (openings up to about 80 km) fills it.
        data, geometry = self.run_command(FJORD_LAND, '--fill-km', '40', '--buffer-km', '10',
                                          '--tolerance-km', '1')
        self.assertTrue(geometry.valid)
        self.assertCovers(geometry, -42, 70.0)          # middle of the fjord
        self.assertCovers(geometry, -43.8, 70.0)        # its head
        self.assertCovers(geometry, -40.1, 70.0)        # its mouth
        self.assertCovers(geometry, -39.45, 72, False)  # open sea, about 19 km offshore
        self.assertEqual(data['features'][0]['properties']['fill_km'], 40.0)

    def test_fill_zero_leaves_the_fjord_open(self):
        data, geometry = self.run_command(FJORD_LAND, '--fill-km', '0', '--buffer-km', '10',
                                          '--tolerance-km', '1')
        self.assertCovers(geometry, -42, 70.0, False)
        self.assertCovers(geometry, -43.95, 70.0)       # 2 km from the head: in the buffer
        self.assertEqual(data['features'][0]['properties']['fill_km'], 0.0)

    def test_fill_narrower_than_the_fjord_leaves_it_open(self):
        # Closing with 10 km fills openings up to about 20 km, not the 44 km fjord.
        _, geometry = self.run_command(FJORD_LAND, '--fill-km', '10', '--buffer-km', '10',
                                       '--tolerance-km', '1')
        self.assertCovers(geometry, -42, 70.0, False)

    def test_default_fill_is_45_km(self):
        data, geometry = self.run_command(FJORD_LAND, '--buffer-km', '10', '--tolerance-km', '1')
        self.assertEqual(data['features'][0]['properties']['fill_km'], 45.0)
        self.assertCovers(geometry, -42, 70.0)

    def test_large_landmasses_are_cut_out(self):
        # A 25 km buffer would reach 10 km into "Ellesmere" (15 km away); it is cut out with
        # a 2 km margin. 1 degree of longitude is about 30.6 km at lat 74.5.
        _, geometry = self.run_command(NEAR_LARGE_LAND, '--fill-km', '0', '--buffer-km', '25',
                                       '--tolerance-km', '1')
        self.assertTrue(geometry.valid)
        self.assertCovers(geometry, -45, 74.5)              # inland
        self.assertCovers(geometry, -50.1, 74.5)            # 3 km off "Greenland"
        self.assertCovers(geometry, -50.66, 74.5, False)    # 5 km inside "Ellesmere"
        self.assertCovers(geometry, -50.47, 74.5, False)    # 1 km off "Ellesmere"
        self.assertCovers(geometry, -50.0, 72.6)            # south of "Ellesmere": buffered
        self.assertEqual(command.LANDMASS_MARGIN_KM, 2.0)

    def test_select_greenland_returns_the_large_landmasses(self):
        polygons = []
        for coordinates in (MAINLAND, CANADA, CANADA_ISLAND, ICELAND, FAR_AWAY):
            polygon = GEOSGeometry(json.dumps({'type': 'Polygon', 'coordinates': coordinates}))
            polygon.srid = 4326
            polygons.append(polygon)
        mainland, islands, large = command.select_greenland(polygons)
        self.assertEqual(islands, [])
        self.assertEqual(len(large), 2)     # "Canada" and "Iceland"; FAR_AWAY isn't in the box
        for polygon in large:
            self.assertEqual(polygon.srid, command.METRIC_SRID)
            self.assertGreaterEqual(polygon.area, 20_000e6)
        self.assertGreater(mainland.area, max(polygon.area for polygon in large))

    def test_invalid_fill_is_refused(self):
        for value in ('-1', 'nan', 'inf', '500'):
            with self.subTest(value=value), self.assertRaises(CommandError):
                self.run_command(LAND, '--fill-km', value)
        with self.assertRaises(CommandError):
            self.run_command(LAND, '--buffer-km', 'nan')
        self.assertFalse(os.path.exists(self.output))

    def test_tolerance_must_be_below_the_buffer(self):
        with self.assertRaises(CommandError):
            self.run_command(LAND, '--buffer-km', '5', '--tolerance-km', '5')

    def test_no_land_in_the_box(self):
        only_far = {'type': 'FeatureCollection', 'features': [feature('Polygon', FAR_AWAY)]}
        with self.assertRaises(CommandError):
            self.run_command(only_far)

    def test_unreadable_source(self):
        with self.assertRaises(CommandError):
            call_command('make_greenland_coverage',
                         os.path.join(self.directory.name, 'missing.shp'),
                         '--output', self.output, stdout=io.StringIO())


class UnderlayClipTests(SimpleTestCase):
    """T23 (deliberate change of T22's TopographicClipTests): the topographic layer is drawn
    whole and blended (test_map_styles.TopographicBlendTests); the underlay is clipped to the
    outside of the coverage outline instead, while the topographic map is the base layer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code = code_only(read_static(LAYERS))
        clip = cls.code[cls.code.index('function coverageClip(layer) {'):]
        cls.clip = clip[:clip.index('\n    }\n')]

    def test_the_topographic_layer_is_not_clipped(self):
        self.assertNotIn('clipToCoverage', self.code)
        self.assertIn("dataforsyningenWms(TOPO_WMS, 'gl_aabent_land', false, "
                      "BLEND_UNDERLAY_CLASS)}", self.code)
        wms = self.code[self.code.index('function dataforsyningenWms('):]
        wms = wms[:wms.index('\n    }\n')]
        self.assertNotIn('clip', wms.lower())
        # Only the underlay gets the clip.
        self.assertEqual(self.code.count('coverageClip('), 2)     # definition and use
        self.assertIn('result.coverageClip = coverageClip(result.underlay);', self.code)
        self.assertIn('underlay: arcticSdi(layerOptions, UNDERLAY_Z_INDEX)};', self.code)

    def test_inverse_clip_rectangle_and_outline_even_odd(self):
        path = self.code[self.code.index('function levelClipPath('):]
        path = path[:path.index('\n    }\n')]
        self.assertIn('function levelClipPath(crs, rings, level, worldSize) {', path)
        # A rectangle one world larger than the tile grid on every side, then every ring.
        self.assertIn('var low = -worldSize;', path)
        self.assertIn('var high = 2 * worldSize;', path)
        self.assertIn("var path = 'M' + move(low, low) + 'L' + move(high, low) + 'L' + "
                      "move(high, high) +", path)
        self.assertIn("'L' + move(low, high) + 'Z';", path)
        self.assertIn('path += rings.map(', path)
        self.assertIn('crs.latLngToPoint(latlng, level.zoom).subtract(level.origin)', path)
        self.assertIn('L.point(x, y).subtract(level.origin)', path)
        self.assertIn("return 'path(evenodd, \"' + path + '\")';", path)
        # World size from the CRS: level 0 is one tile over the grid extent.
        self.assertIn('return tileSize * crs.scale(zoom) / crs.scale(0);', self.code)
        self.assertIn('worldPixelSize(crs, layer.getTileSize().x, level.zoom)', self.clip)

    def test_clip_is_set_per_zoom_level(self):
        # GridLayer's hook for each new level container; the level is moved and scaled by
        # Leaflet, so the clip stays aligned on pan and zoom without any map event.
        self.assertIn('layer._onCreateLevel = clipLevel;', self.clip)
        self.assertIn('level.el.style.clipPath = levelClipPath(', self.clip)
        for event in ("'zoomend'", "'moveend'", "'viewreset'", "'zoomanim'", "'move'"):
            with self.subTest(event=event):
                self.assertNotIn(event, self.code)
        leaflet = read_static('publications/vendor/leaflet-1.9.4/leaflet.js')
        self.assertIn('this._onCreateLevel(n)', leaflet)
        self.assertIn('_onCreateLevel:u', leaflet)

    def test_only_while_the_topographic_map_is_the_base_layer(self):
        self.assertIn("var TOPOGRAPHIC_ID = 'topographic';", self.code)
        # The id of the topographic entry in BASE_LAYERS is that constant's value.
        self.assertIn("{id: 'topographic', name: 'Topographic map (Dataforsyningen)'",
                      self.code)
        update = self.code[self.code.index('function updateUnderlay('):]
        update = update[:update.index('\n    }\n')]
        self.assertIn('underlay.coverageClip.setActive(!!baseEntry && baseEntry.id === '
                      'TOPOGRAPHIC_ID);', update)
        # Set before the underlay is added, so its first level has the right clip.
        self.assertLess(update.index('setActive('), update.index('underlay.addTo(map);'))
        # updateUnderlay runs on the first base layer and on every change (UnderlayTests);
        # a change sets the clip of every existing level again.
        self.assertIn('if (!state.active || state.failed) {\n'
                      "                level.el.style.clipPath = '';", self.clip)
        set_active = self.clip[self.clip.index('setActive: function (active) {'):]
        set_active = set_active[:set_active.index('\n            },')]
        self.assertIn('state.active = !!active;', set_active)
        self.assertIn('clipAllLevels();', set_active)
        self.assertIn("var state = {active: false, requested: false, rings: null, "
                      "failed: false};", self.clip)

    def test_hidden_while_loading_unclipped_on_failure(self):
        self.assertIn("var CLIP_NOTHING = 'path(\"M0 0Z\")';", self.code)
        self.assertIn('} else if (!state.rings) {\n'
                      '                level.el.style.clipPath = CLIP_NOTHING;', self.clip)
        load = self.clip[self.clip.index('function load() {'):]
        load = load[:load.index('\n        }\n')]
        self.assertIn('state.failed = true;', load)
        self.assertEqual(load.count('console.error('), 1)
        # The promise is made once (loadCoverage), so its rejection is logged once.
        self.assertIn('if (state.active && !state.requested) {', self.clip)
        self.assertIn('state.requested = true;', load)

    def test_outline_is_fetched_once_from_next_to_the_script(self):
        self.assertIn("var SCRIPT_PATH = 'js/map/find-artek-map-layers.js';", self.code)
        self.assertIn("var COVERAGE_PATH = 'data/greenland_topo_coverage.geojson';", self.code)
        self.assertTrue(LAYERS.endswith(re.search(r"var SCRIPT_PATH = '([^']+)';",
                                                  self.code)[1]))
        self.assertIsNotNone(finders.find('publications/data/greenland_topo_coverage.geojson'))
        self.assertIn('var COVERAGE_URL = coverageUrl(document.currentScript);', self.code)
        # Same prefix and ?v= version as the script itself.
        self.assertIn('return src.replace(SCRIPT_PATH, COVERAGE_PATH);', self.code)
        self.assertEqual(self.code.count('fetch('), 1)
        load = self.code[self.code.index('function loadCoverage() {'):]
        load = load[:load.index('\n    }\n')]
        self.assertIn('if (!coverage) {', load)
        self.assertIn("credentials: 'same-origin'", load)
        # Only when the topographic map is first chosen.
        self.assertEqual(self.code.count('loadCoverage().then('), 1)
        self.assertIn('loadCoverage().then(', self.clip)

    def test_no_change_to_the_tile_requests(self):
        self.assertEqual(self.code.count('L.tileLayer.wms('), 1)
        self.assertNotIn('getTileUrl', self.code)
        self.assertNotIn('createTile', self.code)


class BoxZoomTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code = code_only(read_static(COMPONENT))

    def test_modes_and_edit_maps(self):
        self.assertIn("var BOX_ZOOM_MODES = ['overview', 'report', 'feature'];", self.code)
        self.assertIn('BOX_ZOOM_MODES.indexOf(this.mode) !== -1 && !this.editable;', self.code)
        # editable is known before the button is decided.
        self.assertLess(self.code.index('this.editable = !!options.editable;'),
                        self.code.index('BOX_ZOOM_MODES.indexOf(this.mode)'))
        self.assertIn('this.boxZoomControl = this.boxZoomButton ? new BoxZoomControl().addTo('
                      'this.map) : null;', self.code)

    def test_pages(self):
        for path, mode in PAGE_SCRIPTS.items():
            with self.subTest(path=path):
                source = read_static(path)
                self.assertIn(mode, source)
                self.assertNotIn('editable', source)
                self.assertNotIn('boxZoomButton', source)
        edit = read_static(EDIT_SCRIPT)
        self.assertIn('editable: true', edit)
        self.assertNotIn('boxZoomButton', edit)
        preview = read_static(PREVIEW_SCRIPT)
        self.assertIn("mode: 'preview'", preview)
        self.assertNotIn('boxZoomButton', preview)

    def test_button_is_under_the_zoom_buttons_and_accessible(self):
        self.assertIn("var BOX_ZOOM_LABEL = 'Zoom to a rectangle: drag a box';", self.code)
        self.assertIn("options: {position: 'topleft'},", self.code)
        for line in ("button.title = BOX_ZOOM_LABEL;",
                     "button.setAttribute('role', 'button');",
                     "button.setAttribute('aria-label', BOX_ZOOM_LABEL);",
                     "button.setAttribute('aria-pressed', 'false');",
                     "this._button.setAttribute('aria-pressed', 'true');",
                     'L.DomEvent.disableClickPropagation(container);'):
            with self.subTest(line=line):
                self.assertIn(line, self.code)
        self.assertIn('aria-hidden="true"', self.code)      # the icon

    def test_reuses_leaflet_box_zoom_without_shift(self):
        self.assertIn('var ArmedBoxZoom = L.Map.BoxZoom.extend({', self.code)
        handler = self.code[self.code.index('var ArmedBoxZoom'):]
        handler = handler[:handler.index('\n    });\n')]
        self.assertIn('if (!this.armed || ((e.which !== 1) && (e.button !== 1))) {', handler)
        self.assertNotIn('shiftKey', handler)
        self.assertIn('L.Map.BoxZoom.prototype._finish.call(this);', handler)
        # Leaflet's own Shift box zoom stays (only paused while the button is armed).
        self.assertNotIn('boxZoom: false', self.code)

    def control(self):
        control = self.code[self.code.index('var BoxZoomControl'):]
        return control[:control.index('\n    });\n')]

    def method(self, name):
        control = self.control()
        body = control[control.index(f'        {name}: function ('):]
        return body[:body.index('\n        },')]

    def test_arming_pauses_dragging(self):
        control = self.control()
        for line in ('map.dragging.disable();', 'map.boxZoom.disable();',
                     'map.dragging.enable();', 'map.boxZoom.enable();',
                     "L.DomEvent.on(document, 'keydown', this._onKeyDown, this);",
                     "L.DomEvent.off(document, 'keydown', this._onKeyDown, this);"):
            with self.subTest(line=line):
                self.assertIn(line, control)
        self.assertIn('var ESCAPE_KEY = 27;', self.code)

    def test_stays_armed_after_a_box_zoom(self):
        # T23 (deliberate change of T22, where the end of the box disarmed the button).
        control = self.control()
        self.assertIn('this._handler.onFinish = L.Util.bind(this._onFinish, this);', control)
        self.assertNotIn('L.Util.bind(this.disarm', control)
        finish = self.method('_onFinish')
        self.assertNotIn('disarm', finish)
        # Leaflet's _finish removes the crosshair after a drag: it is put back while armed.
        self.assertIn('if (this.isArmed()) {', finish)
        self.assertIn("L.DomUtil.addClass(this._map.getContainer(), 'leaflet-crosshair');",
                      finish)
        leaflet = read_static('publications/vendor/leaflet-1.9.4/leaflet.js')
        self.assertIn('_finish:function(){this._moved&&(T(this._box),z(this._container,'
                      '"leaflet-crosshair"))', leaflet)

    def test_escape_cancels_the_box_and_disarms(self):
        key = self.method('_onKeyDown')
        self.assertIn('if (e.keyCode === ESCAPE_KEY) {', key)
        self.assertIn('this._handler._onKeyDown(e);', key)
        self.assertIn('this.disarm();', key)
        self.assertLess(key.index('this._handler._onKeyDown(e);'), key.index('this.disarm();'))

    def test_mouse_wheel_over_the_map_disarms(self):
        arm = self.method('arm')
        disarm = self.method('disarm')
        self.assertIn("L.DomEvent.on(map.getContainer(), 'wheel', this._onWheel, this);", arm)
        self.assertIn("L.DomEvent.off(map.getContainer(), 'wheel', this._onWheel, this);",
                      disarm)
        self.assertNotIn("'wheel'", self.method('onAdd'))
        wheel = self.method('_onWheel')
        self.assertIn('this.disarm();', wheel)
        # The wheel still zooms: the event is not stopped.
        self.assertNotIn('stop', wheel.lower())
        self.assertNotIn('preventDefault', wheel)

    def test_second_click_disarms(self):
        add = self.method('onAdd')
        self.assertIn('if (this.isArmed()) {\n                    this.disarm();\n'
                      '                } else {\n                    this.arm();', add)

    def test_button_css(self):
        css = read_static(MAP_CSS)
        self.assertIn('display: flex;', css_rule(css, '.leaflet-bar a.fa-box-zoom-button'))
        self.assertIn('background-color:',
                      css_rule(css, '.leaflet-bar a.fa-box-zoom-button[aria-pressed="true"]'))
