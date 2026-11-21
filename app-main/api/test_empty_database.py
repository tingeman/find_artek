"""The URLconf loads and the system checks pass without a database (roadmap FA-R14).

``api/views.py`` used to query the ``Topic`` table while the module was imported (the topic
list in the Swagger description of ``/api/report/``), so ``manage.py check`` and ``migrate``
(without ``--skip-checks``) failed on an empty database. The list is now built lazily, when
the Swagger schema is generated.
"""
import importlib
import json
import warnings

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import clear_url_caches, reverse

from publications.models import Topic
from publications.test_factories import app_path


class ImportWithoutDatabaseTests(SimpleTestCase):
    """SimpleTestCase forbids database queries: any query at import time fails the test."""

    def tearDown(self):
        clear_url_caches()

    def test_api_views_import_without_database(self):
        import api.views
        importlib.reload(api.views)

    def test_root_urlconf_imports_without_database(self):
        import api.urls
        import api.views
        importlib.reload(api.views)
        importlib.reload(api.urls)
        importlib.reload(importlib.import_module(settings.ROOT_URLCONF))
        clear_url_caches()
        self.assertTrue(reverse('api:report-list'))

    def test_system_checks_run_without_database(self):
        import api.views
        importlib.reload(api.views)
        call_command('check', verbosity=0)


class SwaggerSchemaTests(TestCase):

    def get_schema(self):
        response = self.client.get(app_path(reverse('schema-swagger-ui')), {'format': 'openapi'})
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def topic_description(self, schema):
        # drf-yasg moves the common prefix of all paths into basePath, so match the end only
        path = next(p for p in schema['paths'] if p.endswith('/report/'))
        params = schema['paths'][path]['get']['parameters']
        return next(p['description'] for p in params if p['name'] == 'topic')

    def test_schema_lists_topics_at_request_time(self):
        Topic.objects.create(topic='Made-up test topic')
        description = self.topic_description(self.get_schema())
        self.assertIn('Made-up test topic', description)

    def test_schema_renders_without_topics(self):
        description = self.topic_description(self.get_schema())
        self.assertIn('Filter publications by topic name', description)

    def test_schema_is_valid_swagger_2(self):
        # swagger-spec-validator is a dependency of drf-yasg since 1.21.11 (plan "django-5" T3)
        from swagger_spec_validator.validator20 import validate_spec

        Topic.objects.create(topic='Made-up test topic')
        schema = self.get_schema()
        self.assertEqual(schema['swagger'], '2.0')
        validate_spec(schema)  # raises SwaggerValidationError
        for suffix in ('/report/', '/feature/', '/person/'):
            with self.subTest(path=suffix):
                self.assertTrue([p for p in schema['paths'] if p.endswith(suffix)])

    def test_redoc_serves_the_same_schema(self):
        response = self.client.get(app_path(reverse('schema-redoc')), {'format': 'openapi'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('paths', json.loads(response.content))


class SwaggerCompatRenderersTests(SimpleTestCase):
    """SWAGGER_USE_COMPAT_RENDERERS = False (plan "django-5" T1): building the schema view
    raises no drf-yasg DeprecationWarning, and only the dot-less spec formats exist."""

    def test_schema_view_without_deprecation_warning(self):
        from drf_yasg import openapi
        from drf_yasg.views import get_schema_view

        self.assertIs(settings.SWAGGER_USE_COMPAT_RENDERERS, False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            view = get_schema_view(openapi.Info(title='t', default_version='v1'), public=True)
        self.assertEqual([str(w.message) for w in caught
                          if issubclass(w.category, DeprecationWarning)], [])
        formats = {renderer.format for renderer in view.renderer_classes}
        self.assertIn('openapi', formats)
        self.assertFalse([f for f in formats if f.startswith('.')], formats)
