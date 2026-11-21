"""The CAS login flow with django-cas-ng 5.1 / python-cas 1.7 (plan "django-5", T3).

The CAS server is never contacted: the ticket check (python-cas ``CASClientV2.verify_ticket``,
CAS_VERSION '2') and the AD lookup (``roles.ad_user_info``) are mocked.

- The callback (``/login?ticket=...``) creates the user, logs them in, stores the session
  ticket, sends cas_user_authenticated (roles: dtu_user) and redirects to ``next``.
- A ``next`` on another host is a 400 (find_artek.cas_views), never a redirect there and never
  a 500. Up to django-cas-ng 5.0.1 it was followed after the login.
- The login view stays csrf_exempt (the CAS server POSTs to it), the admin CAS login only lets
  its listed users through, and the CAS logout now also takes POST (django-cas-ng 5.1), with
  Django's CSRF check.
"""
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from cas import CASClientV2
from django.conf import settings
from django.contrib.auth.models import User
from django.http import QueryDict
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django_cas_ng.models import SessionTicket

from publications import roles
from publications.test_factories import app_path, make_user

OFF_SITE = 'https://evil.example/find/'


def _login_path(**params):
    query = QueryDict(mutable=True)
    query.update(params)
    return app_path(reverse('cas_ng_login')) + '?' + query.urlencode(safe='/')


def _no_ad_info(*args, **kwargs):
    return roles.AdUserInfo(first_name='', last_name='', email='', memberships={})


@override_settings(USE_LDAP=True, LDAP_GROUP_ARTEK_STAFF='', LDAP_GROUP_ARTEK_EDITOR='')
class CasCallbackTests(TestCase):

    def setUp(self):
        patcher = mock.patch.object(roles, 'ad_user_info', side_effect=_no_ad_info)
        self.ad_lookup = patcher.start()
        self.addCleanup(patcher.stop)

    def verify(self, username='s990010'):
        """Patch the ticket check: a valid ticket for username (None: invalid ticket)."""
        return mock.patch.object(CASClientV2, 'verify_ticket', autospec=True,
                                 return_value=(username, {}, None))

    def test_valid_ticket_creates_user_logs_in_and_redirects_to_next(self):
        next_path = reverse('publications:add_report')
        with self.verify() as verify_ticket:
            response = self.client.get(_login_path(ticket='ST-1-test', next=next_path))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], next_path)

        user = User.objects.get(username='s990010')
        self.assertEqual(str(user.pk), self.client.session['_auth_user_id'])
        self.assertEqual(set(user.groups.values_list('name', flat=True)), {'dtu_user'})
        self.ad_lookup.assert_called_once()
        self.assertTrue(SessionTicket.objects.filter(
            ticket='ST-1-test', session_key=self.client.session.session_key).exists())

        # The ticket is checked once, for the service URL CAS issued it for: the login URL
        # (with the script prefix) with the same next.
        verify_ticket.assert_called_once()
        client, ticket = verify_ticket.call_args.args
        self.assertEqual(ticket, 'ST-1-test')
        service = urlsplit(client.service_url)
        self.assertEqual(service.path, reverse('cas_ng_login'))
        self.assertEqual(parse_qs(service.query)['next'], [next_path])

    def test_existing_user_is_reused(self):
        existing = User.objects.create_user('s990011')
        with self.verify('s990011'):
            response = self.client.get(_login_path(ticket='ST-2-test'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('publications:frontpage'))
        self.assertEqual(User.objects.filter(username='s990011').count(), 1)
        self.assertEqual(self.client.session['_auth_user_id'], str(existing.pk))

    def test_invalid_ticket_is_403_without_user(self):
        with self.verify(None):
            response = self.client.get(_login_path(ticket='ST-bad'))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(User.objects.filter(username='s990010').exists())
        self.ad_lookup.assert_not_called()

    def test_off_site_next_with_ticket_is_400_and_ticket_not_checked(self):
        with self.verify() as verify_ticket:
            response = self.client.get(_login_path(ticket='ST-3-test', next=OFF_SITE))
        self.assertEqual(response.status_code, 400)
        verify_ticket.assert_not_called()
        self.assertNotIn('_auth_user_id', self.client.session)


class CasLoginNextTests(TestCase):
    """``next`` on another host (django-cas-ng CAS_CHECK_NEXT, find_artek.cas_views)."""

    def test_anonymous_off_site_next_is_400_not_a_redirect_to_cas(self):
        response = self.client.get(_login_path(next=OFF_SITE))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.has_header('Location'))

    def test_logged_in_off_site_next_is_400_not_a_redirect_there(self):
        self.client.force_login(make_user('s990012'))
        response = self.client.get(_login_path(next=OFF_SITE))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.has_header('Location'))

    def test_same_host_absolute_next_is_allowed(self):
        self.client.force_login(make_user('s990013'))
        next_url = 'http://testserver' + reverse('publications:add_report')
        response = self.client.get(_login_path(next=next_url))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], next_url)

    def test_off_site_next_on_admin_cas_login_is_400(self):
        response = self.client.get(
            app_path(reverse('admin-cas-login')) + '?next=' + OFF_SITE)
        self.assertEqual(response.status_code, 400)


class CasLoginCsrfTests(TestCase):

    def test_login_view_is_csrf_exempt(self):
        # The CAS server POSTs (single logout) without a CSRF token. With CAS_VERSION '2'
        # python-cas has no single logout, so the view only redirects to next. (Without next
        # django-cas-ng's POST uses CAS_REDIRECT_URL unresolved, a URL name: 400, as in 5.0.1.)
        client = Client(enforce_csrf_checks=True)
        next_path = reverse('publications:frontpage')
        response = client.post(app_path(reverse('cas_ng_login')),
                               {'logoutRequest': '<x/>', 'next': next_path})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], next_path)


@override_settings(USE_LDAP=False)
class AdminCasLoginTests(TestCase):
    """publications_meta.views.AdminCasLoginView: only its listed users reach the admin."""

    def login(self, username):
        with mock.patch.object(CASClientV2, 'verify_ticket',
                               return_value=(username, {}, None)):
            return self.client.get(app_path(reverse('admin-cas-login')) + '?ticket=ST-admin')

    def test_other_user_is_refused(self):
        response = self.login('s990014')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You are not allowed to access the admin page')

    def test_listed_user_goes_to_admin_index(self):
        response = self.login('thin')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('admin:index'))


class CasLogoutPostTests(TestCase):
    """django-cas-ng 5.1 LogoutView accepts POST (as GET); Django's CSRF check applies."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(make_user('s990015'))

    def test_post_without_csrf_token_is_403_and_keeps_the_session(self):
        response = self.client.post(app_path(reverse('cas_ng_logout')))
        self.assertEqual(response.status_code, 403)
        self.assertIn('_auth_user_id', self.client.session)

    def test_post_with_csrf_token_logs_out_and_redirects_to_cas_server(self):
        token = 'a' * 32
        self.client.cookies[settings.CSRF_COOKIE_NAME] = token
        response = self.client.post(app_path(reverse('cas_ng_logout')), HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(settings.CAS_SERVER_URL),
                        response['Location'])
        self.assertNotIn('_auth_user_id', self.client.session)
