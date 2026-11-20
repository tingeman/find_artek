"""The URLconf loads and the system checks pass without a database (roadmap FA-R14).

``api/views.py`` used to query the ``Topic`` table while the module was imported (the topic
list in the Swagger description of ``/api/report/``), so ``manage.py check`` and ``migrate``
(without ``--skip-checks``) failed on an empty database. The list is now built lazily, when
the Swagger schema is generated.
"""
import importlib
import json

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
