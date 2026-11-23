"""Overview map: type filter, legend, reports in view; map fixes from the T5 check (plan
"features" T11, FA-R65 part).

- One source for the feature type colours (publications/map_styles.py): every type has one;
  the map pages get them as a JSON block (#find-artek-type-colors) that find-artek-map.js
  reads, and the legend on the overview map and the report page shows the same colours.
- The overview map renders a checkbox per feature type, all checked without ``?types=``;
  ``?types=<slug>,...`` round-trips into the checked boxes (unknown values ignored,
  ``types=`` = none).
- The report page uses the shared legend (no checkboxes); the hard-coded legend is gone.
- The overview page has the "reports in view" panel; the list is built in the browser from
  the features the API already returned (no new endpoint, the API output is unchanged: the
  API snapshot tests cover that).
- JS sources (no JS test runner, FA-R40): no colour table in the component, filter and view
  helpers, wheel zoom only after a click on embedded maps, the base layer choice kept per tab.

Everything is made up factory data.
"""
import json
import re

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import QueryDict
from django.templatetags.static import static
from django.test import SimpleTestCase

from publications.map_styles import (COLORS_SCRIPT_ID, FEATURE_TYPE_COLORS, TYPE_FILTER_PARAM,
                                     feature_type_slug, feature_type_styles, selected_type_slugs)
from publications.models import Feature
from publications.test_factories import page_path
from publications.test_map_assets import MapPagesTestBase, template_files

ALL_SLUGS = {feature_type_slug(value) for value, _ in Feature.feature_types}
COMPONENT = 'publications/js/map/find-artek-map.js'
LAYERS = 'publications/js/map/find-artek-map-layers.js'
OVERVIEW_JS = 'publications/js/map.js'

CHECKBOX = re.compile(r'<input type="checkbox"[^>]*>')
SWATCH = re.compile(r'class="fa-map-legend-swatch" style="background-color: ([^;"]+);"')


def read_static(path):
    found = finders.find(path)
    if not found:
        raise AssertionError(f'static file {path} not found')
    with open(found, encoding='utf-8') as handle:
        return handle.read()


def colors_block(html):
    match = re.search(r'<script id="%s" type="application/json">(.*?)</script>'
                      % COLORS_SCRIPT_ID, html, re.S)
    return json.loads(match[1]) if match else None


class MapStylesTests(SimpleTestCase):

    def test_every_type_has_a_colour(self):
        types = [value for value, _ in Feature.feature_types]
        self.assertEqual(set(FEATURE_TYPE_COLORS), set(types))
        self.assertEqual([style['value'] for style in feature_type_styles()], types)
        for style in feature_type_styles():
            with self.subTest(type=style['value']):
                self.assertEqual(style['color'], FEATURE_TYPE_COLORS[style['value']])

    def test_colours(self):
        # The colours my-map-class.js and the report legend used before T11, as hex; T16
        # (deliberate change) replaced the three that were hard to see on white: BOREHOLE
        # yellow, LAB MEASUREMENT pink and OTHER white (test_map_styles.py checks contrast).
        self.assertEqual(FEATURE_TYPE_COLORS, {
            'PHOTO': '#ff0000', 'SAMPLE': '#008000', 'BOREHOLE': '#b8860b',
            'GEOPHYSICAL DATA': '#0000ff', 'FIELD MEASUREMENT': '#800080',
            'LAB MEASUREMENT': '#d6337f', 'RESOURCE': '#a52a2a', 'OTHER': '#00838f'})

    def test_slugs(self):
        self.assertEqual(feature_type_slug('GEOPHYSICAL DATA'), 'geophysical-data')
        self.assertEqual(len(ALL_SLUGS), len(Feature.feature_types))
        for slug in ALL_SLUGS:
            with self.subTest(slug=slug):
                self.assertRegex(slug, r'^[a-z-]+$')

    def test_selected_types_from_the_query(self):
        cases = {
            '': ALL_SLUGS,                                   # no parameter: all
            'types=': set(),                                 # empty: none
            'types=photo': {'photo'},
            'types=photo,Geophysical-Data, borehole': {'photo', 'geophysical-data', 'borehole'},
            'types=photo%2Csample': {'photo', 'sample'},     # comma encoded by URLSearchParams
            'types=nothing,PHOTO': {'photo'},                # unknown dropped, case ignored
            'lat=70&lng=-44&zoom=4': ALL_SLUGS,
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(selected_type_slugs(QueryDict(query)), expected)
        self.assertEqual(TYPE_FILTER_PARAM, 'types')


class OverviewFilterAndLegendTests(MapPagesTestBase):

    def checkboxes(self, query=''):
        html = self.get(page_path('map') + query)
        boxes = {}
        for tag in CHECKBOX.findall(html):
            slug = re.search(r'value="([^"]+)"', tag)[1]
            boxes[slug] = ' checked' in tag
        return html, boxes

    def test_a_checkbox_per_type_all_checked_by_default(self):
        html, boxes = self.checkboxes()
        self.assertEqual(set(boxes), ALL_SLUGS)
        self.assertTrue(all(boxes.values()))
        self.assertIn('id="feature-type-filter"', html)
        self.assertIn(f'data-param="{TYPE_FILTER_PARAM}"', html)
        for value, label in Feature.feature_types:
            with self.subTest(type=value):
                self.assertIn(f'value="{feature_type_slug(value)}" data-type="{value}"', html)
                self.assertIn(f'>{label}</span>', html)

    def test_types_parameter_round_trips_into_the_checkboxes(self):
        cases = {
            '?types=photo,geophysical-data': {'photo', 'geophysical-data'},
            '?lat=71.5&lng=-50.1&zoom=6.00&types=borehole': {'borehole'},
            '?types=': set(),
            '?types=unknown': set(),
            '?lat=71.5&lng=-50.1&zoom=6.00': ALL_SLUGS,
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                _, boxes = self.checkboxes(query)
                self.assertEqual(set(boxes), ALL_SLUGS)
                self.assertEqual({slug for slug, on in boxes.items() if on}, expected)

    def test_legend_colours_come_from_the_single_source(self):
        html, _ = self.checkboxes()
        filter_html = html[html.index('id="feature-type-filter"'):]
        filter_html = filter_html[:filter_html.index('</fieldset>')]
        expected = [style['color'] for style in feature_type_styles()]
        self.assertEqual(SWATCH.findall(filter_html), expected)
        self.assertEqual(colors_block(html), FEATURE_TYPE_COLORS)

    def test_reports_in_view_panel(self):
        html = self.get(page_path('map'))
        for needle in ('id="reports-in-view"', 'id="reports-in-view-summary"',
                       'id="reports-in-view-list"', 'Reports in view'):
            with self.subTest(needle=needle):
                self.assertIn(needle, html)

    def test_overview_styles_are_versioned(self):
        html = self.get(page_path('map'))
        version = settings.STATIC_ASSET_VERSION
        for path in ('publications/css/map.css', 'publications/css/map-legend.css'):
            with self.subTest(path=path):
                self.assertIn(f'href="{static(path)}?v={version}"', html)


class ReportLegendTests(MapPagesTestBase):

    def test_report_page_uses_the_shared_legend(self):
        html = self.get(page_path('report', pk=self.pub.pk))
        self.assertIn('id="feature-type-legend"', html)
        self.assertNotIn('id="feature-type-filter"', html)
        self.assertEqual(CHECKBOX.findall(html), [])
        legend = html[html.index('id="feature-type-legend"'):]
        legend = legend[:legend.index('</ul>')]
        self.assertEqual(SWATCH.findall(legend),
                         [style['color'] for style in feature_type_styles()])
        for _, label in Feature.feature_types:
            with self.subTest(label=label):
                self.assertIn(f'>{label}</span>', legend)
        # The hard-coded legend is gone.
        self.assertNotIn('color-guide-box', html)
        self.assertNotIn('GEOPHYSICAL-DATA', html)
        self.assertIn(
            f'href="{static("publications/css/map-legend.css")}?v={settings.STATIC_ASSET_VERSION}"',
            html)


class ColoursOnEveryMapPageTests(MapPagesTestBase):

    def test_every_rendered_map_page_has_the_colours_before_the_component(self):
        component = f'{static(COMPONENT)}?v={settings.STATIC_ASSET_VERSION}'
        for name, (path, user) in self.map_pages().items():
            with self.subTest(page=name):
                html = self.get(path, user)
                self.assertEqual(colors_block(html), FEATURE_TYPE_COLORS)
                self.assertEqual(html.count(f'id="{COLORS_SCRIPT_ID}"'), 1)
                self.assertLess(html.index(f'id="{COLORS_SCRIPT_ID}"'), html.index(component))

    def test_every_template_with_the_component_includes_the_colours(self):
        checked = 0
        for path, text in template_files():
            if 'js/map/find-artek-map.js' in text:
                checked += 1
                with self.subTest(template=path):
                    self.assertIn('{% feature_type_colors_script %}', text)
                    self.assertRegex(text, r'{%\s*load\s[^%]*\bmap_legend\b')
        self.assertGreaterEqual(checked, 5)


class MapScriptSourceTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.component = read_static(COMPONENT)
        cls.layers = read_static(LAYERS)
        cls.overview = read_static(OVERVIEW_JS)

    def test_no_colour_table_in_the_component(self):
        self.assertNotRegex(self.component, r'\bTYPE_COLORS\b')
        for value, color in FEATURE_TYPE_COLORS.items():
            with self.subTest(type=value):
                self.assertNotIn(f"'{value}': '{color}'", self.component)
        self.assertIn(f"var TYPE_COLORS_ID = '{COLORS_SCRIPT_ID}';", self.component)
        self.assertIn('JSON.parse(block.textContent)', self.component)

    def test_filter_and_view_helpers(self):
        for needle in ('FindArtekMap.prototype.setTypeFilter', 'FindArtekMap.prototype.recordsInView',
                       'map.getPixelBounds()', 'transformation.untransform(',
                       'FindArtekMap.reportUrl = reportUrl'):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.component)

    def test_overview_script(self):
        for needle in ("getElementById('feature-type-filter')", 'findArtekMap.recordsInView()',
                       'findArtekMap.setTypeFilter(checkedTypes())',
                       "findArtekMap.map.on('moveend', scheduleShowReports)",
                       'window.setTimeout(showReports, UPDATE_DELAY_MS)',
                       'window.history.replaceState', 'params.delete(param)',
                       "params.set(param, slugs.join(','))", 'FindArtekMap.reportUrl(report.id)',
                       'record.related_publications'):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.overview)
        # Report numbers and titles are put in as text, never as HTML; no new API call.
        self.assertNotIn('innerHTML', self.overview)
        self.assertNotIn('fetch(', self.overview)

    def test_wheel_zoom_only_after_a_click_on_embedded_maps(self):
        self.assertIn("options.wheelZoom || (this.mode === 'overview' ? 'always' : 'focus')",
                      self.component)
        for needle in ('map.scrollWheelZoom.disable();', "addEventListener('mousedown', enable)",
                       "addEventListener('focus', enable)",
                       "addEventListener('mouseleave', disable)",
                       "addEventListener('blur', disable)"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.component)

    def test_topographic_is_the_default_base_layer_and_the_choice_is_per_tab(self):
        config = self.layers[self.layers.index('var BASE_LAYERS = ['):]
        self.assertTrue(config.startswith("var BASE_LAYERS = [\n        {id: 'topographic'"))
        self.assertNotIn('localStorage.', self.layers)
        self.assertIn('window.sessionStorage.getItem(STORAGE_KEY)', self.layers)
