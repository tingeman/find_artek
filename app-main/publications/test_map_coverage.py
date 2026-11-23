"""Topographic map clipped to its coverage, and the box-zoom button (plan "features" T22).

- The coverage outline (publications/static/publications/data/greenland_topo_coverage.geojson,
  made by ``manage.py make_greenland_coverage`` from Natural Earth 10m land): a WGS84 GeoJSON
  (Multi)Polygon around Greenland, a few hundred vertices, inside lon -75..-10, lat 59..84,
  covering the towns and not Iceland, Canada or the open sea.
- The management command, on made-up polygons (no Natural Earth file in the tests): Greenland
  is the largest polygon, nearby islands are kept, islands nearer another large landmass and
  far polygons are left out, the buffer reaches seaward.
- find-artek-map-layers.js clips the topographic layer (only that one) per zoom level with a
  CSS clip-path, fetching the outline once from the URL next to the script.
- find-artek-map.js: a box-zoom button under +/- on the overview, report and feature maps, not
  on edit maps (dragging draws there) or the import preview.

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
        # Made with the command's defaults (12 km seaward, 2.5 km tolerance).
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


class TopographicClipTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code = code_only(read_static(LAYERS))

    def test_only_the_topographic_layer_is_clipped(self):
        self.assertIn("dataforsyningenWms(TOPO_WMS, 'gl_aabent_land', false, true)}", self.code)
        # Satellite and Sentinel-2 (and the overlays) are not clipped: no fourth argument.
        for call in ("dataforsyningenWms(SATELLITE_WMS, 'ortofoto', false)}",
                     "dataforsyningenWms(SATELLITE_WMS, 'sentinel2_10m_2022', false)}",
                     "dataforsyningenWms(SATELLITE_WMS, 'stednavne', true)}",
                     "dataforsyningenWms(SATELLITE_WMS, 'hoejdekurver_og_koter', true)}",
                     "dataforsyningenWms(SATELLITE_WMS, 'utm_net', true)}"):
            with self.subTest(call=call):
                self.assertIn(call, self.code)
        self.assertIn('return clip ? clipToCoverage(layer) : layer;', self.code)
        self.assertEqual(self.code.count('clipToCoverage('), 2)     # definition and use

    def test_clip_is_set_per_zoom_level(self):
        # GridLayer's hook for each new level container; the level is moved and scaled by
        # Leaflet, so the clip stays aligned on pan and zoom without any map event.
        self.assertIn('layer._onCreateLevel = clipLevel;', self.code)
        self.assertIn('level.el.style.clipPath = levelClipPath(', self.code)
        self.assertIn("crs.latLngToPoint(latlng, level.zoom).subtract(level.origin)", self.code)
        self.assertIn("'path(evenodd, \"' + path + '\")'", self.code)
        for event in ("'zoomend'", "'moveend'", "'viewreset'", "'zoomanim'", "'move'"):
            with self.subTest(event=event):
                self.assertNotIn(event, self.code)
        leaflet = read_static('publications/vendor/leaflet-1.9.4/leaflet.js')
        self.assertIn('this._onCreateLevel(n)', leaflet)
        self.assertIn('_onCreateLevel:u', leaflet)

    def test_hidden_while_loading_unclipped_on_failure(self):
        self.assertIn("var CLIP_NOTHING = 'path(\"M0 0Z\")';", self.code)
        self.assertIn('level.el.style.clipPath = CLIP_NOTHING;', self.code)
        self.assertIn("level.el.style.clipPath = '';", self.code)

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
        # Only when the clipped layer is on the map.
        self.assertEqual(self.code.count('loadCoverage().then('), 1)
        self.assertIn("layer.on('add', function () {\n            loadCoverage()", self.code)

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

    def test_arming_pauses_dragging_and_escape_cancels(self):
        control = self.code[self.code.index('var BoxZoomControl'):]
        control = control[:control.index('\n    });\n')]
        for line in ('map.dragging.disable();', 'map.boxZoom.disable();',
                     'map.dragging.enable();', 'map.boxZoom.enable();',
                     "L.DomEvent.on(document, 'keydown', this._onKeyDown, this);",
                     "L.DomEvent.off(document, 'keydown', this._onKeyDown, this);",
                     'if (e.keyCode === ESCAPE_KEY) {',
                     "this._handler.onFinish = L.Util.bind(this.disarm, this);"):
            with self.subTest(line=line):
                self.assertIn(line, control)
        self.assertIn('var ESCAPE_KEY = 27;', self.code)

    def test_button_css(self):
        css = read_static(MAP_CSS)
        self.assertIn('display: flex;', css_rule(css, '.leaflet-bar a.fa-box-zoom-button'))
        self.assertIn('background-color:',
                      css_rule(css, '.leaflet-bar a.fa-box-zoom-button[aria-pressed="true"]'))
