"""Map scripts served locally and the Dataforsyningen token (plan "features" T2).

- No template loads Leaflet, proj4, Proj4Leaflet, leaflet-rotate or Leaflet.draw from a CDN
  (unpkg, cdnjs, jsdelivr); the pages use the copies in ``static/publications/vendor/``.
- Every vendored file a template references exists, with a licence file next to it.
- ``FA_DATAFORSYNINGEN_TOKEN`` defaults to '' and is rendered only into the map pages, only as
  a ``data-dataforsyningen-token`` attribute of the map element. Tests use a dummy token.
- The map pages still render: overview, report and feature page for anonymous users, the
  add-feature-by-map page for a user who may add features to the report.
"""
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import SimpleTestCase, TestCase, override_settings

from publications.models import Feature
from publications.roles import ARTEK_EDITOR
from publications.test_factories import make_report, make_user, page_path, report_type

APP_MAIN = Path(settings.BASE_DIR)
VENDOR = 'publications/vendor/'

# Leftover templates no view renders (FA-R41: removed as their own change, not built on).
LEFTOVER_TEMPLATES = {'publications/templates/publications/report.old.html'}

# A CDN URL of one of the vendored map libraries.
CDN_MAP_URL = re.compile(
    r'https?://(?:unpkg\.com|cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net)/[^"\'\s>]*'
    r'(?:leaflet|proj4)', re.IGNORECASE)

STATIC_TAG = re.compile(r"""{%\s*static\s+['"](?P<path>[^'"]+)['"]\s*%}""")

# Per map page template: the vendored files it must load.
MAP_TEMPLATES = {
    'map.html': ['leaflet-1.9.4/leaflet.css', 'leaflet-1.9.4/leaflet.js', 'proj4-2.22.0/proj4.js',
                 'proj4leaflet-1.0.2/proj4leaflet.js', 'leaflet-rotate-0.2.8/leaflet-rotate-src.js'],
    'report.html': ['leaflet-1.9.4/leaflet.css', 'leaflet-1.9.4/leaflet.js',
                    'proj4-2.22.0/proj4.js', 'proj4leaflet-1.0.2/proj4leaflet.js',
                    'leaflet-rotate-0.2.8/leaflet-rotate-src.js'],
    'feature.html': ['leaflet-1.9.4/leaflet.css', 'leaflet-1.9.4/leaflet.js'],
    'add_feature_by_map.html': ['leaflet-1.9.4/leaflet.css', 'leaflet-1.9.4/leaflet.js',
                                'leaflet-draw-1.0.4/leaflet.draw.css',
                                'leaflet-draw-1.0.4/leaflet.draw.js'],
}

DUMMY_TOKEN = 'dummy-token-t2'


def template_files():
    """(path relative to app-main, text) of every template under app-main, leftovers excluded."""
    for directory in sorted(APP_MAIN.glob('**/templates')):
        for path in sorted(directory.rglob('*.html')):
            relative = path.relative_to(APP_MAIN).as_posix()
            if relative in LEFTOVER_TEMPLATES:
                continue
            yield relative, path.read_text(encoding='utf-8')


def template_text(name):
    path = APP_MAIN / 'publications' / 'templates' / 'publications' / name
    return path.read_text(encoding='utf-8')


class NoMapScriptsFromCdnTests(SimpleTestCase):

    def test_templates_found(self):
        names = [relative for relative, _ in template_files()]
        self.assertIn('publications/templates/publications/map.html', names)
        self.assertGreater(len(names), 20)

    def test_no_template_loads_a_map_library_from_a_cdn(self):
        for relative, text in template_files():
            with self.subTest(template=relative):
                self.assertEqual(CDN_MAP_URL.findall(text), [])

    def test_the_pattern_catches_the_old_urls(self):
        for url in ('https://unpkg.com/leaflet@1.9.3/dist/leaflet.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.9.2/proj4.js',
                    'https://unpkg.com/leaflet-rotate@0.2.8/dist/leaflet-rotate-src.js',
                    'https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css',
                    'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js'):
            with self.subTest(url=url):
                self.assertTrue(CDN_MAP_URL.search(f'<script src="{url}"></script>'))

    def test_old_local_proj4leaflet_copy_is_gone(self):
        self.assertIsNone(finders.find('publications/js/proj4leaflet.js'))
        for relative, text in template_files():
            with self.subTest(template=relative):
                self.assertNotIn("'publications/js/proj4leaflet.js'", text)


class VendoredFilesTests(SimpleTestCase):

    def referenced_vendor_files(self):
        found = set()
        for _, text in template_files():
            found.update(m['path'] for m in STATIC_TAG.finditer(text)
                         if m['path'].startswith(VENDOR))
        return found

    def test_map_pages_load_their_vendored_files(self):
        for name, files in MAP_TEMPLATES.items():
            text = template_text(name)
            for file in files:
                with self.subTest(template=name, file=file):
                    self.assertIn(f"{{% static '{VENDOR}{file}' %}}", text)

    def test_every_referenced_vendor_file_exists(self):
        referenced = self.referenced_vendor_files()
        self.assertGreaterEqual(len(referenced), 7)
        for path in sorted(referenced):
            with self.subTest(path=path):
                self.assertIsNotNone(finders.find(path), f'{path} is not a static file')

    def test_every_vendored_library_has_a_licence_file(self):
        libraries = {path[len(VENDOR):].split('/')[0] for path in self.referenced_vendor_files()}
        self.assertEqual(libraries, {'leaflet-1.9.4', 'proj4-2.22.0', 'proj4leaflet-1.0.2',
                                     'leaflet-rotate-0.2.8', 'leaflet-draw-1.0.4'})
        for library in sorted(libraries):
            with self.subTest(library=library):
                self.assertTrue(
                    finders.find(f'{VENDOR}{library}/LICENSE')
                    or finders.find(f'{VENDOR}{library}/LICENSE.md'))

    def test_css_images_are_vendored(self):
        # leaflet.css and leaflet.draw.css load their images relative to the CSS file.
        for css in ('leaflet-1.9.4/leaflet.css', 'leaflet-draw-1.0.4/leaflet.draw.css'):
            directory = css.split('/')[0]
            text = Path(finders.find(VENDOR + css)).read_text(encoding='utf-8')
            for image in re.findall(r"url\(['\"]?(images/[^'\")]+)", text):
                with self.subTest(css=css, image=image):
                    self.assertIsNotNone(finders.find(f'{VENDOR}{directory}/{image}'))


class TokenSettingTests(SimpleTestCase):

    def test_default_is_empty_when_the_variable_is_unset(self):
        # settings.py is imported in a fresh interpreter without the variable.
        env = {key: value for key, value in os.environ.items()
               if key != 'FA_DATAFORSYNINGEN_TOKEN'}
        code = ('import find_artek.settings as s; '
                'print(repr(s.FA_DATAFORSYNINGEN_TOKEN))')
        result = subprocess.run([sys.executable, '-c', code], cwd=APP_MAIN, env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertEqual(result.stdout.strip().splitlines()[-1], "''")

    def test_value_comes_from_the_variable(self):
        env = dict(os.environ, FA_DATAFORSYNINGEN_TOKEN=DUMMY_TOKEN)
        code = ('import find_artek.settings as s; '
                'print(s.FA_DATAFORSYNINGEN_TOKEN == "%s")' % DUMMY_TOKEN)
        result = subprocess.run([sys.executable, '-c', code], cwd=APP_MAIN, env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertEqual(result.stdout.strip().splitlines()[-1], 'True')


class MapPagesTestBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        cls.pub = make_report(pubtype, '98-31', verified=True, confidential=False,
                              title='Map report', year=1998)
        cls.feature = Feature.objects.create(name='BH-T2', date=datetime.date(1998, 7, 1))
        cls.feature.publications.add(cls.pub)
        cls.editor = make_user('mapedtr', ARTEK_EDITOR)    # may add features to any report

    def anonymous_map_pages(self):
        return {
            'map': page_path('map'),
            'report': page_path('report', pk=self.pub.pk),
            'feature': page_path('feature', pk=self.feature.pk),
        }

    def add_by_map_path(self):
        return page_path('add_feature_by_map', report_pk=self.pub.pk)

    def map_pages(self):
        """name -> (path, user or None) of every page with a map."""
        pages = {name: (path, None) for name, path in self.anonymous_map_pages().items()}
        pages['add_feature_by_map'] = (self.add_by_map_path(), self.editor)
        return pages

    def get(self, path, user=None):
        if user is not None:
            self.client.force_login(user)
        else:
            self.client.logout()
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()


class MapPagesRenderTests(MapPagesTestBase):

    def test_map_pages_render_for_anonymous(self):
        for name, path in self.anonymous_map_pages().items():
            with self.subTest(page=name):
                self.get(path)

    def test_add_feature_by_map_renders_for_a_user_who_may_add_features(self):
        self.get(self.add_by_map_path(), self.editor)

    def test_pages_load_the_vendored_files(self):
        templates = {'map': 'map.html', 'report': 'report.html', 'feature': 'feature.html',
                     'add_feature_by_map': 'add_feature_by_map.html'}
        for name, (path, user) in self.map_pages().items():
            html = self.get(path, user)
            for file in MAP_TEMPLATES[templates[name]]:
                with self.subTest(page=name, file=file):
                    self.assertIn(static(VENDOR + file), html)
            with self.subTest(page=name):
                self.assertEqual(CDN_MAP_URL.findall(html), [])


class TokenRenderingTests(MapPagesTestBase):

    def non_map_pages(self):
        return {
            'frontpage': (page_path('frontpage'), None),
            'reports': (page_path('reports'), None),
            'reports (editor)': (page_path('reports'), self.editor),
        }

    @override_settings(FA_DATAFORSYNINGEN_TOKEN=DUMMY_TOKEN)
    def test_map_pages_render_the_token_as_data_attribute(self):
        for name, (path, user) in self.map_pages().items():
            with self.subTest(page=name):
                html = self.get(path, user)
                self.assertEqual(html.count(f'data-dataforsyningen-token="{DUMMY_TOKEN}"'), 1)
                # Only in the attribute, nowhere else on the page.
                self.assertEqual(html.count(DUMMY_TOKEN), 1)

    @override_settings(FA_DATAFORSYNINGEN_TOKEN=DUMMY_TOKEN)
    def test_token_is_on_the_map_element(self):
        expected = {
            'map': r'<div class="map" id="map" data-dataforsyningen-token="([^"]*)"',
            'report': r'<div id="map" data-dataforsyningen-token="([^"]*)"',
            'feature': r'<div class="map-box-inner" id="map" data-dataforsyningen-token="([^"]*)"',
            'add_feature_by_map': r'<div id="feature-map" data-dataforsyningen-token="([^"]*)"',
        }
        for name, (path, user) in self.map_pages().items():
            with self.subTest(page=name):
                match = re.search(expected[name], self.get(path, user))
                self.assertIsNotNone(match)
                self.assertEqual(match[1], DUMMY_TOKEN)

    @override_settings(FA_DATAFORSYNINGEN_TOKEN=DUMMY_TOKEN)
    def test_other_pages_do_not_contain_the_token(self):
        for name, (path, user) in self.non_map_pages().items():
            with self.subTest(page=name):
                html = self.get(path, user)
                self.assertNotIn(DUMMY_TOKEN, html)
                self.assertNotIn('data-dataforsyningen-token', html)

    @override_settings(FA_DATAFORSYNINGEN_TOKEN='')
    def test_no_attribute_without_a_token(self):
        for name, (path, user) in self.map_pages().items():
            with self.subTest(page=name):
                self.assertNotIn('data-dataforsyningen-token', self.get(path, user))

    @override_settings(FA_DATAFORSYNINGEN_TOKEN='a"b<c')
    def test_token_is_escaped(self):
        html = self.get(page_path('map'))
        self.assertIn('data-dataforsyningen-token="a&quot;b&lt;c"', html)
