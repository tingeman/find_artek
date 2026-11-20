"""The "Add" menu in the header of the base template (plan "registration" T9, roadmap FA-R56).

"Add report" is shown to users with publications.add_publication (action ``add``), "Import
from Excel" to users with publications.change_publication (action ``manage``), in the
desktop and in the mobile navigation; nothing to anonymous users or a plain dtu_user. The
menu must agree with the view guards (publications/permissions.py ``user_may``).
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from publications.permissions import ADD, MANAGE, user_may
from publications.test_factories import app_path, make_user


DESKTOP_START = '<div class="default-header-content'
MOBILE_START = '<div class="mobile-header-content">'
HEADER_END = '</header>'


class AddMenuTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.add_report_url = reverse('publications:add_report')
        cls.import_url = reverse('publications:add_reports_from_file_upload')
        cls.frontpage_path = app_path(reverse('publications:frontpage'))

        # make_user: users in artek_staff/artek_editor are also in dtu_user (roles.py).
        cls.dtu_user = make_user('s990001')
        cls.staff = make_user('staff', 'artek_staff')
        cls.editor = make_user('editor', 'artek_editor')
        cls.superuser = User.objects.create_superuser('admin')

    def _navs(self, user=None):
        """(desktop nav HTML, mobile nav HTML) of the frontpage for ``user``."""
        if user is not None:
            self.client.force_login(user)
        response = self.client.get(self.frontpage_path)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        start = html.index(DESKTOP_START)
        mobile = html.index(MOBILE_START, start)
        end = html.index(HEADER_END, mobile)
        return html[start:mobile], html[mobile:end]

    def _link(self, url):
        return f'href="{url}"'

    def assertMenu(self, user, add_report, import_excel):
        desktop, mobile = self._navs(user)
        for name, nav in (('desktop', desktop), ('mobile', mobile)):
            with self.subTest(nav=name):
                self.assertEqual(self._link(self.add_report_url) in nav, add_report,
                                 f'"Add report" in {name} nav')
                self.assertEqual(self._link(self.import_url) in nav, import_excel,
                                 f'"Import from Excel" in {name} nav')
        # The "Add" dropdown itself only when it has an entry.
        self.assertEqual('header-nav-add-toggle' in desktop, add_report or import_excel)

    def test_anonymous_sees_no_add_menu(self):
        self.assertMenu(None, add_report=False, import_excel=False)

    def test_plain_dtu_user_sees_no_add_menu(self):
        self.assertMenu(self.dtu_user, add_report=False, import_excel=False)

    def test_artek_staff_sees_add_report_only(self):
        self.assertMenu(self.staff, add_report=True, import_excel=False)

    def test_artek_editor_sees_add_report_and_import(self):
        self.assertMenu(self.editor, add_report=True, import_excel=True)

    def test_superuser_sees_add_report_and_import(self):
        self.assertMenu(self.superuser, add_report=True, import_excel=True)

    def test_menu_agrees_with_view_guards(self):
        for user in (self.dtu_user, self.staff, self.editor, self.superuser):
            with self.subTest(user=user.username):
                self.client.logout()
                desktop, mobile = self._navs(user)
                for nav in (desktop, mobile):
                    self.assertEqual(self._link(self.add_report_url) in nav, user_may(user, ADD))
                    self.assertEqual(self._link(self.import_url) in nav, user_may(user, MANAGE))

    def test_menu_links_open_for_the_users_who_see_them(self):
        # Following a shown link must not end on the access-denied page.
        for user, paths in ((self.staff, [self.add_report_url]),
                             (self.editor, [self.add_report_url, self.import_url])):
            self.client.force_login(user)
            for url in paths:
                with self.subTest(user=user.username, url=url):
                    self.assertEqual(self.client.get(app_path(url)).status_code, 200)
