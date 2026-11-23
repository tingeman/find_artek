"""The shared map component (plan "features" T3).

- The overview map, the report page and the feature page load the vendored libraries and the
  component in the right order: leaflet, proj4, Proj4Leaflet, then find-artek-map-layers.js,
  find-artek-map.js and the page script (our files versioned).
- EPSG:3574 without rotation (owner decision 2026-11-23): leaflet-rotate is on no page and no
  longer a static file; it and the old EPSG:3575 map class are kept outside static/ in
  docs/archive/map_epsg3575_rotate/.
- The map element tells the component what to show: data-map-mode, the report pk
  (data-publication-id) on the report page, the feature pk (data-feature-id) on the feature page.
- my-map-class.js and the front-page prefetch (frontpage.js) are gone and nothing references them.
- Every static file the map page templates (and base/frontpage) reference exists.
- The JS sources keep the agreed projection, tile grid, layers and token handling. There is no
  JS test runner (FA-R40), so these checks read the sources; the behaviour in the browser is
  checked by hand.

Everything is made up factory data; the token is a dummy value.
"""
import re

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import SimpleTestCase, override_settings

from publications.test_factories import page_path
from publications.test_map_assets import MapPagesTestBase, template_files

VENDOR = 'publications/vendor/'
COMPONENT = 'publications/js/map/find-artek-map.js'
LAYERS = 'publications/js/map/find-artek-map-layers.js'
MAP_JS_FILES = (COMPONENT, LAYERS, 'publications/js/map.js', 'publications/js/report.js',
                'publications/js/feature.js')

LIBRARIES = (
    VENDOR + 'leaflet-1.9.4/leaflet.js',
    VENDOR + 'proj4-2.22.0/proj4.js',
    VENDOR + 'proj4leaflet-1.0.2/proj4leaflet.js',
)
OWN_SCRIPTS = (LAYERS, COMPONENT)

STATIC_TAG = re.compile(
    r"""{%\s*(?:static|versioned_static)\s+['"](?P<path>[^'"]+)['"]\s*%}""")
SCRIPT_SRC = re.compile(r'<script[^>]*\bsrc="([^"]+)"')


def read_static(path):
    found = finders.find(path)
    if not found:
        raise AssertionError(f'static file {path} not found')
    with open(found, encoding='utf-8') as handle:
        return handle.read()


class MapPageScriptTests(MapPagesTestBase):

    def pages(self):
        """name -> (path, page script)."""
        return {
            'map': (page_path('map'), 'publications/js/map.js'),
            'report': (page_path('report', pk=self.pub.pk), 'publications/js/report.js'),
            'feature': (page_path('feature', pk=self.feature.pk), 'publications/js/feature.js'),
        }

    def test_scripts_load_in_order(self):
        version = settings.STATIC_ASSET_VERSION
        expected = [static(path) for path in LIBRARIES]
        expected += [f'{static(path)}?v={version}' for path in OWN_SCRIPTS]
        for name, (path, page_script) in self.pages().items():
            with self.subTest(page=name):
                sources = SCRIPT_SRC.findall(self.get(path))
                wanted = expected + [f'{static(page_script)}?v={version}']
                for src in wanted:
                    self.assertEqual(sources.count(src), 1, src)
                positions = [sources.index(src) for src in wanted]
                self.assertEqual(positions, sorted(positions))

    def test_map_element_attributes(self):
        expected = {
            'map': ['data-map-mode="overview"'],
            'report': ['data-map-mode="report"', f'data-publication-id="{self.pub.pk}"'],
            'feature': ['data-map-mode="feature"', f'data-feature-id="{self.feature.pk}"'],
        }
        for name, (path, _) in self.pages().items():
            html = self.get(path)
            element = re.search(r'<div[^>]*\bid="map"[^>]*>', html)
            self.assertIsNotNone(element, name)
            for attribute in expected[name]:
                with self.subTest(page=name, attribute=attribute):
                    self.assertIn(attribute, element[0])

    @override_settings(FA_DATAFORSYNINGEN_TOKEN='dummy-token-t3')
    def test_token_stays_on_the_map_element(self):
        for name, (path, _) in self.pages().items():
            with self.subTest(page=name):
                element = re.search(r'<div[^>]*\bid="map"[^>]*>', self.get(path))[0]
                self.assertIn('data-dataforsyningen-token="dummy-token-t3"', element)

    def test_frontpage_loads_no_map_or_prefetch_script(self):
        html = self.get(page_path('frontpage'))
        for name in ('my-map-class.js', 'find-artek-map', 'frontpage.js', 'my-reports-class.js'):
            with self.subTest(script=name):
                self.assertNotIn(name, html)


class OldFilesGoneTests(SimpleTestCase):

    def test_old_files_are_removed(self):
        for path in ('publications/js/class/my-map-class.js', 'publications/js/frontpage.js',
                     VENDOR + 'leaflet-rotate-0.2.8/leaflet-rotate-src.js',
                     VENDOR + 'leaflet-rotate-0.2.8/LICENSE'):
            with self.subTest(path=path):
                self.assertIsNone(finders.find(path))

    def test_no_static_file_of_leaflet_rotate_or_the_old_class(self):
        # The archive (docs/archive/map_epsg3575_rotate/) is outside every static directory.
        found = [path for finder in finders.get_finders() for path, _ in finder.list([])
                 if 'leaflet-rotate' in path or 'my-map-class' in path]
        self.assertEqual(found, [])

    def test_no_page_loads_leaflet_rotate(self):
        for relative, text in template_files():
            with self.subTest(template=relative):
                self.assertNotIn('leaflet-rotate', text)

    def test_nothing_references_the_old_class(self):
        for relative, text in template_files():
            with self.subTest(template=relative):
                self.assertNotIn('my-map-class', text)
                self.assertNotIn('MyMapClass', text)
                self.assertNotIn('frontpage.js', text)
        for path in MAP_JS_FILES:
            with self.subTest(path=path):
                self.assertNotIn('MyMapClass', read_static(path))

    def test_every_static_file_referenced_by_a_map_page_exists(self):
        # The map pages. Not all templates: login.html (login.css) references a missing file
        # already; reported, not part of T3. add_feature_by_map.html added in T5 (the broken
        # marker icon paths are gone).
        names = {f'publications/templates/publications/{name}' for name in
                 ('base.html', 'frontpage.html', 'map.html', 'report.html', 'feature.html',
                  'add_feature_by_map.html')}
        checked = 0
        for relative, text in template_files():
            if relative not in names:
                continue
            for match in STATIC_TAG.finditer(text):
                checked += 1
                with self.subTest(template=relative, path=match['path']):
                    self.assertIsNotNone(finders.find(match['path']))
        self.assertGreater(checked, 20)


class ComponentSourceTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.component = read_static(COMPONENT)
        cls.layers = read_static(LAYERS)

    def test_polar_projection_and_tile_grid(self):
        self.assertIn("'EPSG:3574'", self.component)
        self.assertIn('+proj=laea +lat_0=90 +lon_0=-40 +x_0=0 +y_0=0 +datum=WGS84 +units=m '
                      '+no_defs', self.component)
        # The Arctic SDI WMTS grid (tile matrix set 3574).
        self.assertIn('var GRID_EXTENT = 4889334.802955;', self.component)
        self.assertIn('var TILE_SIZE = 256;', self.component)
        self.assertIn('2 * GRID_EXTENT / TILE_SIZE / Math.pow(2, z)', self.component)
        self.assertIn('origin: [-GRID_EXTENT, GRID_EXTENT]', self.component)
        # Proj4Leaflet 1.0.2 is unpatched: no plain-array `bounds` option.
        self.assertNotIn('bounds:', self.component)

    def test_no_rotation(self):
        for source in (self.component, self.layers):
            for needle in ('rotate', 'setBearing', 'bearing'):
                with self.subTest(needle=needle):
                    # Only the comment pointing to the archived rotated map may mention it.
                    code = '\n'.join(line for line in source.splitlines()
                                     if not line.lstrip().startswith(('*', '//', '/*')))
                    self.assertNotIn(needle, code)

    def test_feature_api(self):
        self.assertIn("'/api/feature/'", self.component)
        self.assertIn('publication_id', self.component)
        for kind in ("'points'", "'lines'", "'polys'"):
            self.assertIn(kind, self.component)

    def test_edit_mode_hook_for_t5(self):
        self.assertIn('FindArtekMap.prototype.enableEditing', self.component)
        self.assertIn('FindArtekMap.addInitHook', self.component)

    def test_popup_text_is_escaped(self):
        self.assertIn('escapeHtml(record.name)', self.component)

    def test_layers(self):
        self.assertNotIn('tile.gbif.org', self.layers)   # GBIF serves EPSG:3575 only
        self.assertIn("'https://basemap.arctic-sdi.org/mapcache/wmts/1.0.0/arctic_cascading/"
                      "default/3574/{z}/{y}/{x}.png'", self.layers)
        self.assertIn('ARCTIC_SDI_MAX_NATIVE_ZOOM = 10', self.layers)
        self.assertIn("'Arctic SDI basemap'", self.layers)
        for name in ("'ortofoto'", "'sentinel2_10m_2022'", "'gl_aabent_land'", "'stednavne'",
                     "'hoejdekurver_og_koter'", "'utm_net'"):
            with self.subTest(layer=name):
                self.assertIn(name, self.layers)
        self.assertIn("'https://api.dataforsyningen.dk/wms/gl_satellitfoto'", self.layers)
        self.assertIn("'https://api.dataforsyningen.dk/wms/gl_aabent_land'", self.layers)
        self.assertIn("version: '1.3.0'", self.layers)
        self.assertIn('token: options.token,', self.layers)
        self.assertIn('Styrelsen for Dataforsyning og Infrastruktur / Klimadatastyrelsen',
                      self.layers)

    def test_base_layer_order_and_token_flags(self):
        """Topographic first (the default with a token); Arctic SDI is the only layer without
        a token; every Dataforsyningen layer needs the token and the filter honours it."""
        config = self.layers[self.layers.index('var BASE_LAYERS = ['):]
        ids = re.findall(r"\{id: '([^']+)', name: '[^']+', needsToken: (true|false)", config)
        self.assertEqual(ids, [('topographic', 'true'), ('satellite', 'true'),
                               ('sentinel2-2022', 'true'), ('arctic-sdi', 'false'),
                               ('place-names', 'true'), ('contours', 'true'),
                               ('utm-grid', 'true')])
        self.assertIn('return options.token || !entry.needsToken;', self.layers)
        self.assertIn("NO_TOKEN_NOTE = 'More map layers need FA_DATAFORSYNINGEN_TOKEN'",
                      self.layers)

    def test_only_the_base_layer_id_is_stored(self):
        self.assertEqual(self.layers.count('localStorage.setItem('), 1)
        self.assertIn('localStorage.setItem(STORAGE_KEY, id)', self.layers)
        for path in MAP_JS_FILES:
            with self.subTest(path=path):
                source = read_static(path)
                self.assertNotIn('sessionStorage', source)
                self.assertNotIn('indexedDB', source)
                if path != LAYERS:
                    self.assertNotIn('localStorage', source)

    def test_no_debug_output_or_dialogs(self):
        for path in MAP_JS_FILES:
            source = read_static(path)
            for needle in ('console.log', 'alert(', 'confirm(', 'prompt('):
                with self.subTest(path=path, needle=needle):
                    self.assertNotIn(needle, source)
