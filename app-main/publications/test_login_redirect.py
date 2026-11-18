"""Where login_required sends an anonymous user (plan "registration", T6).

LOGIN_URL is the URL name of the CAS login view, so Django reverses it and the redirect
carries FORCE_SCRIPT_NAME: /find/login?next=/find/... in production, /login?next=/... in
development. A plain path ('/login') would leave the /find/ nginx location in production.
The same holds for django-cas-ng's CAS_REDIRECT_URL (default '/') and for the service URL it
sends to the CAS server. No request goes to the CAS server here: only the redirect to it is
inspected.
"""
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.http import QueryDict
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from publications.models import Publication, PubType
from publications.test_upload_appendix_access import _app_path


def _expected_login_redirect(next_path):
    query = QueryDict(mutable=True)
    query['next'] = next_path
    return resolve_url('cas_ng_login') + '?' + query.urlencode(safe='/')


class LoginRedirectTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')
        cls.publication = Publication.objects.create(
            type=pubtype, title='Test report', number='99-02', year=1999, verified=True)
        cls.upload_url = reverse('publications:upload_appendix',
                                 kwargs={'pk': cls.publication.pk})

    def assertRedirectsToCasLogin(self, url, query_string=''):
        """GET url (as reversed, i.e. with the script prefix) anonymously."""
        response = self.client.get(_app_path(url) + query_string)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], _expected_login_redirect(url + query_string))
        return response

    def test_login_url_resolves_to_cas_login_view(self):
        self.assertEqual(resolve_url(settings.LOGIN_URL), reverse('cas_ng_login'))

    def test_anonymous_appendix_upload_redirects_to_cas_login_with_next(self):
        self.assertRedirectsToCasLogin(self.upload_url)

    def test_anonymous_add_report_redirects_to_cas_login_with_next(self):
        self.assertRedirectsToCasLogin(reverse('publications:add_report'))

    def test_next_keeps_the_query_string(self):
        self.assertRedirectsToCasLogin(reverse('publications:add_report'), '?a=1')

    def test_production_prefix_stays_under_find(self):
        if settings.FORCE_SCRIPT_NAME != '/find':
            self.skipTest("only with FORCE_SCRIPT_NAME = '/find' (production settings, tests/run.sh)")
        response = self.client.get(_app_path(self.upload_url))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('/find/login?next=/find/'),
                        response['Location'])


class CasLoginViewTests(TestCase):
    """The CAS login view behind the script prefix."""

    def test_service_url_comes_back_to_the_prefixed_login_with_next(self):
        next_path = reverse('publications:add_report')
        query = QueryDict(mutable=True)
        query['next'] = next_path
        response = self.client.get(
            _app_path(reverse('cas_ng_login')) + '?' + query.urlencode(safe='/'))
        self.assertEqual(response.status_code, 302)
        location = response['Location']
        self.assertTrue(location.startswith(settings.CAS_SERVER_URL), location)
        service = urlsplit(parse_qs(urlsplit(location).query)['service'][0])
        self.assertEqual(service.path, reverse('cas_ng_login'))
        self.assertEqual(parse_qs(service.query)['next'], [next_path])

    def test_without_next_or_referer_returns_to_the_frontpage(self):
        # A logged-in user is sent on at once, to the same place a fresh login would go.
        self.client.force_login(User.objects.create_user('s990002', password='x'))
        response = self.client.get(_app_path(reverse('cas_ng_login')))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('publications:frontpage'))
