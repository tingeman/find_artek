"""Map readability fixes from the owner's browser checks (plan "features" T16, T19).

- Feature type colours (publications/map_styles.py): the colours from before T16 (T19, owner
  decision; white OTHER, yellow BOREHOLE, pink LAB MEASUREMENT included), #rrggbb, clearly
  different from each other (CIE76 distance in Lab). The JS fallback colour for unknown types
  is the Python one.
- Point markers (find-artek-map.js, T19): small circles with a black border for every type, so
  white and other light colours show on white; the import preview uses the same style; the
  legend swatches are circles of about the same size with the same black border.
- Lines and polygon outlines of type OTHER (white) have a thin black casing underneath (T19).
- Topographic map (find-artek-map-layers.js, css/find-artek-map.css, T19): blended with
  `mix-blend-mode: multiply`, so its opaque white areas show the Arctic SDI underlay; the other
  base layers are not blended.
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
from pathlib import Path

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
LEAFLET_JS = 'publications/vendor/leaflet-1.9.4/leaflet.js'
PREVIEW = 'publications/js/feature-import-preview.js'
EDIT = 'publications/js/map/find-artek-map-edit.js'
LEGEND_CSS = 'publications/css/map-legend.css'
JS_DIR = 'publications/js'

HEX_COLOR = re.compile(r'^#[0-9a-f]{6}$')
MIN_DISTANCE = 25.0             # CIE76; about 2.3 is "just noticeable"
OLD_POINT_RADIUS = 8            # before T19 (owner: "quite big")
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


def css_rule(css, selector):
    """The declarations of the first rule for `selector` in `css`."""
    rule = css[css.index(selector + ' {') + len(selector) + 2:]
    return rule[:rule.index('}')]


def js_number(code, name):
    return float(re.search(rf'var {name} = ([\d.]+);', code)[1])


class PaletteTests(SimpleTestCase):

    def test_helpers(self):
        self.assertAlmostEqual(relative_luminance('#ffffff'), 1.0)
        self.assertAlmostEqual(relative_luminance('#000000'), 0.0)
        self.assertAlmostEqual(distance('#000000', '#ffffff'), 100.0, places=1)

    def test_every_type_has_a_hex_colour(self):
        self.assertEqual(set(FEATURE_TYPE_COLORS), {value for value, _ in Feature.feature_types})
        for value, color in FEATURE_TYPE_COLORS.items():
            with self.subTest(type=value):
                self.assertRegex(color, HEX_COLOR)
        self.assertRegex(UNKNOWN_TYPE_COLOR, HEX_COLOR)

    def test_the_light_colours_from_before_t16(self):
        # T19 (deliberate change of the T16 tests, owner decision): white, yellow and pink are
        # back; the black marker border keeps them visible (PointMarkerTests).
        self.assertEqual(FEATURE_TYPE_COLORS[Feature.OTHER], '#ffffff')
        self.assertEqual(FEATURE_TYPE_COLORS[Feature.BOREHOLE], '#ffff00')
        self.assertEqual(FEATURE_TYPE_COLORS[Feature.LAB_MEASUREMENT], '#ffc0cb')

    def test_colours_are_distinct(self):
        colors = list(FEATURE_TYPE_COLORS.items()) + [('unknown', UNKNOWN_TYPE_COLOR)]
        for (first, a), (second, b) in itertools.combinations(colors, 2):
            with self.subTest(first=first, second=second):
                self.assertGreaterEqual(distance(a, b), MIN_DISTANCE)

    def test_js_fallback_is_the_python_one(self):
        self.assertIn(f"var UNKNOWN_TYPE_COLOR = '{UNKNOWN_TYPE_COLOR}';",
                      read_static(COMPONENT))


class PointMarkerTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code = code_only(read_static(COMPONENT))

    def test_markers_are_smaller(self):
        radius = js_number(self.code, 'POINT_RADIUS')
        self.assertEqual(radius, 5)
        self.assertLessEqual(radius, OLD_POINT_RADIUS * 2 / 3)
        self.assertNotIn('radius: 8', self.code)

    def test_every_marker_has_a_black_border(self):
        self.assertIn("var POINT_BORDER_COLOR = '#000000';", self.code)
        self.assertGreaterEqual(js_number(self.code, 'POINT_BORDER_WEIGHT'), 1)
        self.assertIn('return {radius: POINT_RADIUS, fillColor: color, color: POINT_BORDER_COLOR,\n'
                      '                weight: POINT_BORDER_WEIGHT, opacity: 1, '
                      'fillOpacity: POINT_FILL_OPACITY};', self.code)
        # No marker border in a light colour anywhere in the component.
        self.assertNotRegex(self.code.lower(), r"color: '(#fff|#ffffff|white)'")

    def test_style_keeps_the_point_style_for_points(self):
        # L.geoJSON applies `style` to the circle markers too (after pointToLayer); before T19
        # it returned the line style for everything, so the border took the type colour.
        self.assertIn("return !!geometry && (geometry.type === 'Point' || "
                      "geometry.type === 'MultiPoint');", self.code)
        self.assertIn('return isPointGeometry(feature && feature.geometry)\n'
                      '                    ? pointStyle(color) : pathStyle(color);', self.code)
        self.assertIn('return L.circleMarker(latlng, pointStyle(colorOf(feature)));', self.code)
        self.assertIn('var options = geoJsonStyle(function () { return color; });', self.code)
        self.assertIn('FindArtekMap.geoJsonStyle = geoJsonStyle;', self.code)

    def test_lines_and_polygons_keep_the_type_colour(self):
        self.assertIn('return {color: color, weight: PATH_WEIGHT, opacity: 1};', self.code)

    def test_import_preview_uses_the_shared_style(self):
        preview = code_only(read_static(PREVIEW))
        self.assertIn('const options = FindArtekMap.geoJsonStyle(function (feature) {', preview)
        self.assertIn('L.geoJSON(data, options)', preview)
        self.assertNotIn('circleMarker', preview)
        self.assertNotIn('radius:', preview)

    def test_only_the_component_makes_circle_markers(self):
        found = []
        for path in sorted(Path(finders.find(JS_DIR)).rglob('*.js')):
            count = code_only(path.read_text(encoding='utf-8')).count('L.circleMarker(')
            if count:
                found.append((path.name, count))
        self.assertEqual(found, [('find-artek-map.js', 1)])


class OtherCasingTests(SimpleTestCase):
    """White OTHER lines and polygon outlines have a thin black casing underneath (T19)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code = code_only(read_static(COMPONENT))

    def test_cased_type_is_the_white_one(self):
        self.assertIn(f"var CASED_TYPE = '{Feature.OTHER}';", self.code)
        self.assertEqual(FEATURE_TYPE_COLORS[Feature.OTHER], '#ffffff')

    def test_casing_is_black_wider_unfilled_and_not_clickable(self):
        self.assertIn("var CASING_STYLE = {color: '#000000', weight: PATH_WEIGHT + 2, opacity: 1, "
                      "fill: false};", self.code)
        casing = self.code[self.code.index('function casingLayer(data, wanted) {'):]
        casing = casing[:casing.index('\n    }\n')]
        self.assertIn('interactive: false,', casing)
        self.assertIn('style: function () { return CASING_STYLE; },', casing)
        # No points; a bare geometry (API fields) or the wanted Features of a collection.
        self.assertIn('if (isPointGeometry(geometry)) {', casing)
        self.assertIn("var geometry = isFeature ? object.geometry : object;", casing)
        self.assertIn('return !(isFeature && wanted) || wanted(object);', casing)

    def test_casing_is_under_the_line_in_the_same_entry(self):
        # One layer per geometry field: the type filter, recordsInView, fitting and the popup
        # treat it like before; the casing comes first, so it is drawn underneath.
        self.assertIn("if (kind !== 'points' && record.type === CASED_TYPE) {", self.code)
        self.assertIn('layer = L.featureGroup([casingLayer(data), layer]);', self.code)
        self.assertIn('layers.push(layer);', self.code)
        self.assertEqual(self.code.count('casingLayer('), 2)   # definition, the one use

    def test_casing_is_not_in_the_edit_layer(self):
        # Edit mode draws only into editLayer from the form field; the casing lives in
        # featureLayer with the other features, so it can't be edited or deleted.
        edit = code_only(read_static(EDIT))
        self.assertNotIn('casing', edit.lower())
        self.assertNotIn('featureLayer', edit)

    def test_import_preview_cases_only_other(self):
        preview = code_only(read_static(PREVIEW))
        self.assertIn('FindArtekMap.casingLayer(data, function (feature) {', preview)
        self.assertIn('return (feature.properties || {}).type === FindArtekMap.CASED_TYPE;',
                      preview)
        self.assertLess(preview.index('FindArtekMap.casingLayer('),
                        preview.index('L.geoJSON(data, options)'))


class LegendTests(MapPagesTestBase):

    def test_legend_swatches_have_the_type_colours(self):
        html = self.get(page_path('map'))
        legend = html[html.index('id="feature-type-filter"'):]
        legend = legend[:legend.index('</fieldset>')]
        swatches = SWATCH.findall(legend)
        self.assertEqual(swatches, [style['color'] for style in feature_type_styles()])
        self.assertIn('#ffffff', swatches)

    def test_swatch_is_a_small_circle_with_a_black_border(self):
        rule = css_rule(read_static(LEGEND_CSS), '.fa-map-legend-swatch')
        self.assertIn('border-radius: 50%;', rule)
        self.assertIn('box-sizing: border-box;', rule)
        size = float(re.search(r'\bwidth: (\d+)px;', rule)[1])
        self.assertIn(f'height: {size:g}px;', rule)
        self.assertLess(size, 16)   # before T19
        # About the size of a marker on the map (diameter plus border).
        component = code_only(read_static(COMPONENT))
        marker = (2 * js_number(component, 'POINT_RADIUS')
                  + js_number(component, 'POINT_BORDER_WEIGHT'))
        self.assertLessEqual(abs(size - marker), 1)

    def test_swatch_border_is_the_marker_border(self):
        rule = css_rule(read_static(LEGEND_CSS), '.fa-map-legend-swatch')
        component = code_only(read_static(COMPONENT))
        weight = js_number(component, 'POINT_BORDER_WEIGHT')
        color = re.search(r"var POINT_BORDER_COLOR = '(#[0-9a-f]{6})';", component)[1]
        self.assertIn(f'border: {weight:g}px solid {color};', rule)


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
        for call in ("dataforsyningenWms(TOPO_WMS, 'gl_aabent_land', false, "
                     "BLEND_UNDERLAY_CLASS)",
                     "dataforsyningenWms(SATELLITE_WMS, 'ortofoto', false)",
                     "dataforsyningenWms(SATELLITE_WMS, 'sentinel2_10m_2022', false)",
                     "dataforsyningenWms(SATELLITE_WMS, 'stednavne', true)",
                     "dataforsyningenWms(SATELLITE_WMS, 'hoejdekurver_og_koter', true)",
                     "dataforsyningenWms(SATELLITE_WMS, 'utm_net', true)"):
            with self.subTest(call=call):
                self.assertIn(call, self.code)


class TopographicBlendTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code = code_only(read_static(LAYERS))
        cls.css = read_static(MAP_CSS)

    def test_only_the_topographic_layer_has_the_class(self):
        self.assertIn("var BLEND_UNDERLAY_CLASS = 'fa-blend-underlay';", self.code)
        self.assertIn("dataforsyningenWms(TOPO_WMS, 'gl_aabent_land', false, "
                      "BLEND_UNDERLAY_CLASS)", self.code)
        # var, topographic layer, export (name and value).
        self.assertEqual(self.code.count('BLEND_UNDERLAY_CLASS'), 4)
        for layer in ('ortofoto', 'sentinel2_10m_2022'):
            with self.subTest(layer=layer):
                self.assertIn(f"dataforsyningenWms(SATELLITE_WMS, '{layer}', false)}},",
                              self.code)

    def test_class_goes_to_the_layer_not_the_wms_request(self):
        # className is a GridLayer option (default ''), so Leaflet puts it on the layer's
        # container and doesn't send it as a WMS parameter.
        self.assertIn('function dataforsyningenWms(url, layerName, overlay, className) {',
                      self.code)
        self.assertIn("className: className || '',", self.code)
        leaflet = read_static(LEAFLET_JS)
        self.assertIn('pane:"tilePane",className:""', leaflet)
        self.assertIn('"leaflet-layer "+(this.options.className||"")', leaflet)

    def test_css_multiplies_the_topographic_layer(self):
        self.assertEqual(css_rule(self.css, '.leaflet-layer.fa-blend-underlay').strip(),
                         'mix-blend-mode: multiply;')
        self.assertEqual(self.css.count('mix-blend-mode:'), 1)

    def test_blend_stays_inside_the_tile_pane(self):
        # Every tile layer stays in Leaflet's tile pane (no `pane` option), and the tile pane is
        # positioned with a z-index, i.e. a stacking context and an isolated blending group:
        # the topographic layer blends only with the underlay below it, not with the map
        # background or the page.
        self.assertNotRegex(self.code, r'\bpane:')
        leaflet_css = read_static(LEAFLET_CSS)
        self.assertRegex(leaflet_css, r'\.leaflet-tile-pane\s*\{\s*z-index: 200;')
        self.assertRegex(leaflet_css, r'\.leaflet-pane,[^{]*\{\s*position: absolute;')


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
