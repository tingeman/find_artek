"""Login-state marker in the base template (plan PLAN_confidential T6, roadmap FA-R75).

base.html renders ``<meta name="auth-marker" content="...">``; an inline script compares it
with the marker stored in sessionStorage and drops the cached API data (``reportData*``,
``featureData*``) when it changed. The marker is ``anon`` for anonymous users and, for
logged-in users, a value that changes on every login and reveals neither the user id nor the
username.
"""
import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from publications.test_factories import app_path

MARKER_RE = re.compile(r'<meta name="auth-marker" content="([^"]*)">')


class AuthMarkerTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.reports_path = app_path(reverse('publications:reports'))
        cls.frontpage_path = app_path(reverse('publications:frontpage'))
        # A long explicit id, so "the id doesn't appear in the hex marker" is a meaningful check
        # (a one-digit id would appear in most hex strings by chance).
        cls.user = User.objects.create_user('s990042', password='x', id=987654321)

    def _marker(self, path=None):
        response = self.client.get(path or self.reports_path)
        self.assertEqual(response.status_code, 200)
        markers = MARKER_RE.findall(response.content.decode())
        self.assertEqual(len(markers), 1, 'base.html must render exactly one auth-marker')
        return markers[0]

    def test_anonymous_marker_is_anon(self):
        self.assertEqual(self._marker(), 'anon')
        self.assertEqual(self._marker(self.frontpage_path), 'anon')

    def test_logged_in_marker_is_not_anon_and_reveals_no_identity(self):
        self.client.force_login(self.user)
        marker = self._marker()
        self.assertNotEqual(marker, 'anon')
        self.assertRegex(marker, r'^[0-9a-f]{16}$')
        self.assertNotIn(self.user.username, marker)
        self.assertNotIn(str(self.user.pk), marker)
        self.assertNotIn(self.client.session.session_key, marker)

    def test_marker_is_stable_within_a_session(self):
        self.client.force_login(self.user)
        self.assertEqual(self._marker(), self._marker(self.frontpage_path))

    def test_marker_changes_on_logout_and_new_login(self):
        self.client.force_login(self.user)
        first = self._marker()
        self.client.logout()
        self.assertEqual(self._marker(), 'anon')
        self.client.force_login(self.user)
        second = self._marker()
        self.assertNotEqual(second, 'anon')
        self.assertNotEqual(first, second)

    def test_page_script_clears_report_and_feature_caches(self):
        """The inline script that clears the caches is in the head, before any page script."""
        html = self.client.get(self.reports_path).content.decode()
        head = html[:html.index('</head>')]
        clear_at = head.index("sessionStorage.setItem('authMarker'")
        self.assertIn("indexOf('reportData') === 0", head)
        self.assertIn("indexOf('featureData') === 0", head)
        self.assertLess(clear_at, head.index('my-reports-class.js'))
