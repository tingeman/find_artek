"""Map readability fixes from the owner's browser check (plan "features" T16).

- Feature type colours (publications/map_styles.py): every type has a #rrggbb colour that
  stands out on white (contrast ratio against white at least 3:1, WCAG 2.x formula) and the
  colours differ clearly from each other (CIE76 distance in Lab). The legend shows them as they
  are; the JS fallback colour for unknown types is the Python one.
- The Arctic SDI basemap lies under every other base layer (find-artek-map-layers.js): its own
  layer object, not in the layer control, below the base layers, removed when Arctic SDI is
  itself chosen. The Dataforsyningen WMS layers are requested transparent, so the underlay
  shows where they have no data.
- Every map page loads css/find-artek-map.css (border, non-white background), and the component
  gives the map element its class.

There is no JS test runner (FA-R40): the JS and CSS checks read the sources; the behaviour in
the browser is checked by hand. Everything is made up factory data.
"""
import itertools
import re

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import SimpleTestCase

from publications.map_styles import (FEATURE_TYPE_COLORS, UNKNOWN_TYPE_COLOR,
                                     feature_type_styles)
from publications.models import Feature
from publications.test_factories import page_path
from publications.test_map_assets import MapPagesTestBase, template_files

COMPONENT = 'publications/js/map/find-artek-map.js'
LAYERS = 'publications/js/map/find-artek-map-layers.js'
MAP_CSS = 'publications/css/find-artek-map.css'
LEAFLET_CSS = 'publications/vendor/leaflet-1.9.4/leaflet.css'

HEX_COLOR = re.compile(r'^#[0-9a-f]{6}$')
MIN_CONTRAST_ON_WHITE = 3.0     # WCAG 2.x minimum for graphical objects
MIN_DISTANCE = 25.0             # CIE76; about 2.3 is "just noticeable"
SWATCH = re.compile(r'class="fa-map-legend-swatch" style="background-color: ([^;"]+);"')


def read_static(path):
    found = finders.find(path)
    if not found:
        raise AssertionError(f'static file {path} not found')
    with open(found, encoding='utf-8') as handle:
        return handle.read()


def code_only(source):
    """The JS source without comment lines (so the checks don't match the explanations)."""
    return '\n'.join(line for line in source.splitlines()
                     if not line.lstrip().startswith(('*', '//', '/*')))


def linear_rgb(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]


def relative_luminance(color):
    r, g, b = linear_rgb(color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_on_white(color):
    return 1.05 / (relative_luminance(color) + 0.05)


def lab(color):
    """CIE L*a*b* (D65) of an sRGB colour."""
    r, g, b = linear_rgb(color)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def distance(first, second):
    return sum((a - b) ** 2 for a, b in zip(lab(first), lab(second))) ** 0.5


class PaletteTests(SimpleTestCase):

    def test_helpers(self):
        self.assertAlmostEqual(contrast_on_white('#ffffff'), 1.0)
        self.assertAlmostEqual(contrast_on_white('#000000'), 21.0)
        self.assertAlmostEqual(contrast_on_white('#767676'), 4.54, places=2)
        self.assertAlmostEqual(distance('#000000', '#ffffff'), 100.0, places=1)

    def test_every_type_has_a_hex_colour(self):
        self.assertEqual(set(FEATURE_TYPE_COLORS), {value for value, _ in Feature.feature_types})
        for value, color in FEATURE_TYPE_COLORS.items():
            with self.subTest(type=value):
                self.assertRegex(color, HEX_COLOR)
        self.assertRegex(UNKNOWN_TYPE_COLOR, HEX_COLOR)

    def test_every_colour_stands_out_on_white(self):
        for value, color in FEATURE_TYPE_COLORS.items():
            with self.subTest(type=value, color=color):
                self.assertGreaterEqual(contrast_on_white(color), MIN_CONTRAST_ON_WHITE)

    def test_the_old_colours_would_fail(self):
        # The check catches what the owner saw: white, yellow and pink on a white map.
        for color in ('#ffffff', '#ffff00', '#ffc0cb'):
            with self.subTest(color=color):
                self.assertLess(contrast_on_white(color), MIN_CONTRAST_ON_WHITE)

    def test_other_is_not_white(self):
        self.assertNotIn(FEATURE_TYPE_COLORS[Feature.OTHER], ('#ffffff', 'white'))

    def test_colours_are_distinct(self):
        colors = list(FEATURE_TYPE_COLORS.items()) + [('unknown', UNKNOWN_TYPE_COLOR)]
        for (first, a), (second, b) in itertools.combinations(colors, 2):
            with self.subTest(first=first, second=second):
                self.assertGreaterEqual(distance(a, b), MIN_DISTANCE)

    def test_js_fallback_is_the_python_one(self):
        self.assertIn(f"var UNKNOWN_TYPE_COLOR = '{UNKNOWN_TYPE_COLOR}';",
                      read_static(COMPONENT))

    def test_points_keep_a_dark_outline(self):
        # A light fill would still show its outline; the outline must not be white.
        component = read_static(COMPONENT)
        self.assertIn("radius: 8, fillColor: color, color: '#000', weight: 1,", component)
        self.assertNotRegex(code_only(component).lower(), r"color: '(#fff|#ffffff|white)'")


class LegendTests(MapPagesTestBase):

    def test_legend_swatches_have_the_new_colours(self):
        html = self.get(page_path('map'))
        legend = html[html.index('id="feature-type-filter"'):]
        legend = legend[:legend.index('</fieldset>')]
        swatches = SWATCH.findall(legend)
        self.assertEqual(swatches, [style['color'] for style in feature_type_styles()])
        self.assertIn(FEATURE_TYPE_COLORS[Feature.OTHER], swatches)
        self.assertNotIn('white', swatches)


class UnderlayTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.layers = read_static(LAYERS)
        cls.code = code_only(cls.layers)

    def test_stacking_order(self):
        values = {name: int(re.search(rf'var {name} = (\d+);', self.code)[1])
                  for name in ('UNDERLAY_Z_INDEX', 'BASE_Z_INDEX', 'OVERLAY_Z_INDEX')}
        self.assertLess(values['UNDERLAY_Z_INDEX'], values['BASE_Z_INDEX'])
        self.assertLess(values['BASE_Z_INDEX'], values['OVERLAY_Z_INDEX'])
        self.assertIn('zIndex: overlay ? OVERLAY_Z_INDEX : BASE_Z_INDEX,', self.code)
        # No hard-coded zIndex numbers left.
        self.assertNotRegex(self.code, r'zIndex: \d')

    def test_underlay_is_its_own_arctic_sdi_layer(self):
        self.assertIn('underlay: arcticSdi(layerOptions, UNDERLAY_Z_INDEX)', self.code)
        self.assertIn('create: function (options) { return arcticSdi(options, BASE_Z_INDEX); }',
                      self.code)
        self.assertIn("var ARCTIC_SDI_ID = 'arctic-sdi';", self.code)

    def test_underlay_follows_the_base_layer(self):
        self.assertIn("var wanted = !!baseEntry && baseEntry.id !== ARCTIC_SDI_ID;", self.code)
        self.assertIn('if (wanted && !map.hasLayer(underlay)) {', self.code)
        self.assertIn('} else if (!wanted && map.hasLayer(underlay)) {', self.code)
        # On the first base layer and on every change in the layer control.
        self.assertIn('updateUnderlay(map, layers.underlay, active);', self.code)
        change = self.code[self.code.index("map.on('baselayerchange'"):]
        change = change[:change.index('});\n')]
        self.assertIn('rememberBaseLayer(entry.id);', change)
        self.assertIn('updateUnderlay(map, layers.underlay, entry);', change)

    def test_underlay_is_not_in_the_layer_control(self):
        self.assertIn('L.control.layers(bases, overlays, {collapsed: true})', self.code)
        for name in ('bases', 'overlays'):
            with self.subTest(name=name):
                self.assertNotRegex(self.code, rf'{name}\[[^\]]*\] = layers\.underlay')
        self.assertEqual(self.code.count('layers.underlay'), 3)

    def test_only_the_base_layer_id_is_still_stored(self):
        self.assertEqual(self.code.count('sessionStorage.setItem('), 1)
        self.assertIn('sessionStorage.setItem(STORAGE_KEY, id)', self.code)

    def test_every_wms_layer_is_transparent(self):
        self.assertIn('transparent: true,', self.code)
        self.assertNotIn('transparent: false', self.code)
        self.assertNotIn('transparent: transparent', self.code)
        self.assertEqual(self.code.count('L.tileLayer.wms('), 1)
        self.assertIn("format: 'image/png',", self.code)

    def test_base_layers_are_marked_as_base_layers(self):
        for call in ("dataforsyningenWms(TOPO_WMS, 'gl_aabent_land', false)",
                     "dataforsyningenWms(SATELLITE_WMS, 'ortofoto', false)",
                     "dataforsyningenWms(SATELLITE_WMS, 'sentinel2_10m_2022', false)",
                     "dataforsyningenWms(SATELLITE_WMS, 'stednavne', true)",
                     "dataforsyningenWms(SATELLITE_WMS, 'hoejdekurver_og_koter', true)",
                     "dataforsyningenWms(SATELLITE_WMS, 'utm_net', true)"):
            with self.subTest(call=call):
                self.assertIn(call, self.code)


class MapCssTests(MapPagesTestBase):

    def test_css_has_border_radius_and_a_non_white_background(self):
        css = read_static(MAP_CSS)
        rule = css[css.index('.leaflet-container.fa-map {'):]
        rule = rule[:rule.index('}')]
        self.assertRegex(rule, r'border: 1px solid ')
        self.assertRegex(rule, r'border-radius: [\d.]+rem;')
        background = re.search(r'background: (#[0-9a-f]{6});', rule)
        self.assertIsNotNone(background)
        self.assertNotIn(background[1], ('#ffffff', '#f0f0f0'))   # not white, not the page grey
        self.assertLess(relative_luminance(background[1]), 0.85)

    def test_component_sets_the_class_and_no_inline_background(self):
        component = code_only(read_static(COMPONENT))
        self.assertIn("var MAP_CLASS = 'fa-map';", component)
        self.assertIn('L.DomUtil.addClass(element, MAP_CLASS);', component)
        self.assertNotIn('style.background', component)
        self.assertNotIn('NO_BACKGROUND_COLOR', component)

    def test_every_template_with_the_component_loads_the_css_after_leaflet(self):
        checked = 0
        for path, text in template_files():
            if 'js/map/find-artek-map.js' in text:
                checked += 1
                with self.subTest(template=path):
                    link = f"{{% versioned_static '{MAP_CSS}' %}}"
                    self.assertEqual(text.count(link), 1)
                    self.assertLess(text.index(LEAFLET_CSS), text.index(link))
        self.assertGreaterEqual(checked, 5)

    def test_every_rendered_map_page_links_the_versioned_css(self):
        href = f'href="{static(MAP_CSS)}?v={settings.STATIC_ASSET_VERSION}"'
        for name, (path, user) in self.map_pages().items():
            with self.subTest(page=name):
                self.assertIn(href, self.get(path, user))
