"""The "Administration" page and its header link (plan release-2026-7 T6, roadmap FA-R100).

Replaces test_menu.py (the "Add" drop-down of FA-R56). The header shows one link
"Administration" (desktop and mobile) to users with publications.add_publication (action
``add``) or publications.change_publication (action ``manage``), nothing to anonymous users or
a plain dtu_user. The page has the same guard (anonymous: login redirect, others without
either permission: 403) and shows the classic tiles; the ones a user may not use or that
aren't built yet are greyed out with the reason and are not links. "Django admin" only for
is_staff.
"""
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from publications.permissions import ADD, MANAGE, user_may
from publications.roles import ARTEK_EDITOR, ARTEK_STAFF
from publications.test_factories import app_path, make_user
from publications.views_administration import may_open_administration

DESKTOP_START = '<div class="default-header-content'
MOBILE_START = '<div class="mobile-header-content">'
HEADER_END = '</header>'

TILE_ORDER = ['add-report', 'add-feature', 'add-person', 'import-reports', 'import-features']


class AdministrationTestBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin_url = reverse('publications:administration')
        cls.admin_path = app_path(cls.admin_url)
        cls.add_report_url = reverse('publications:add_report')
        cls.import_url = reverse('publications:add_reports_from_file_upload')
        cls.frontpage_path = app_path(reverse('publications:frontpage'))

        # make_user: users in artek_staff/artek_editor are also in dtu_user (roles.py).
        cls.dtu_user = make_user('s990001')
        cls.staff = make_user('staff', ARTEK_STAFF)            # add_publication, no change_publication
        cls.editor = make_user('editor', ARTEK_EDITOR)
        cls.superuser = User.objects.create_superuser('admin')
        # Only add_publication, no group at all.
        cls.only_add = User.objects.create_user('onlyadd')
        cls.only_add.user_permissions.add(
            Permission.objects.get(content_type__app_label='publications',
                                   codename='add_publication'))
        # An ARTEK editor who is also Django staff (is_staff), not a superuser.
        cls.staff_editor = make_user('staffed', ARTEK_EDITOR)
        cls.staff_editor.is_staff = True
        cls.staff_editor.save()

    def get_as(self, user, path):
        self.client.logout()
        if user is not None:
            self.client.force_login(user)
        return self.client.get(path)


class HeaderLinkTests(AdministrationTestBase):

    def _navs(self, user):
        """(desktop nav HTML, mobile nav HTML) of the frontpage for ``user``."""
        response = self.get_as(user, self.frontpage_path)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        start = html.index(DESKTOP_START)
        mobile = html.index(MOBILE_START, start)
        end = html.index(HEADER_END, mobile)
        return html[start:mobile], html[mobile:end]

    def assertHeader(self, user, shown):
        desktop, mobile = self._navs(user)
        for name, nav in (('desktop', desktop), ('mobile', mobile)):
            with self.subTest(nav=name):
                self.assertEqual(f'href="{self.admin_url}"' in nav, shown,
                                 f'"Administration" link in {name} nav')
                self.assertEqual('header-nav-administration' in nav, shown)
                # The old drop-down and its direct entries are gone.
                self.assertNotIn('dropdown-toggle', nav)
                self.assertNotIn('dropdown-menu', nav)
                self.assertNotIn('header-nav-add', nav)
                self.assertNotIn('header-nav-import-excel', nav)
                self.assertNotIn(f'href="{self.add_report_url}"', nav)
                self.assertNotIn(f'href="{self.import_url}"', nav)

    def test_anonymous_sees_no_link(self):
        self.assertHeader(None, shown=False)

    def test_plain_dtu_user_sees_no_link(self):
        # dtu_user has neither add_publication nor change_publication.
        self.assertFalse(user_may(self.dtu_user, ADD) or user_may(self.dtu_user, MANAGE))
        self.assertHeader(self.dtu_user, shown=False)

    def test_artek_staff_sees_link(self):
        self.assertHeader(self.staff, shown=True)

    def test_artek_editor_sees_link(self):
        self.assertHeader(self.editor, shown=True)

    def test_user_with_only_add_publication_sees_link(self):
        self.assertHeader(self.only_add, shown=True)

    def test_superuser_sees_link(self):
        self.assertHeader(self.superuser, shown=True)

    def test_link_agrees_with_page_guard(self):
        for user in (self.dtu_user, self.staff, self.editor, self.only_add, self.superuser):
            with self.subTest(user=user.username):
                desktop, mobile = self._navs(user)
                for nav in (desktop, mobile):
                    self.assertEqual(f'href="{self.admin_url}"' in nav,
                                     may_open_administration(user))


class PageAccessTests(AdministrationTestBase):

    def test_anonymous_is_redirected_to_login(self):
        response = self.get_as(None, self.admin_path)
        self.assertEqual(response.status_code, 302)
        query = urlencode({'next': self.admin_url}, safe='/')
        self.assertEqual(response['Location'], resolve_url(settings.LOGIN_URL) + '?' + query)

    def test_user_without_either_permission_gets_403(self):
        self.assertEqual(self.get_as(self.dtu_user, self.admin_path).status_code, 403)

    def test_permitted_users_get_the_page(self):
        for user in (self.staff, self.editor, self.only_add, self.superuser, self.staff_editor):
            with self.subTest(user=user.username):
                response = self.get_as(user, self.admin_path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Administration')

    def test_post_is_not_allowed(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.post(self.admin_path).status_code, 405)


class TileTests(AdministrationTestBase):

    def _tiles(self, user):
        """{key: tile HTML} in page order, and the ordered keys."""
        response = self.get_as(user, self.admin_path)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        marker = '<div class="fmitem admin-tile admin-tile-'
        parts = html.split(marker)[1:]
        tiles = {}
        order = []
        for part in parts:
            key = part.split('"', 1)[0].split()[0]
            order.append(key)
            tiles[key] = part
        return tiles, order

    def assertLink(self, tile, url):
        self.assertIn(f'<a class="fmtile" href="{url}">', tile)
        self.assertNotIn('aria-disabled', tile)
        self.assertNotIn('admin-tile-disabled', tile.split('>', 1)[0])

    def assertGreyed(self, tile, reason):
        self.assertIn('admin-tile-disabled', tile.split('>', 1)[0])
        self.assertIn('aria-disabled="true"', tile)
        self.assertNotIn('<a ', tile)
        self.assertNotIn('href=', tile)
        self.assertIn(reason, tile)

    def test_classic_order_without_backup(self):
        tiles, order = self._tiles(self.editor)
        self.assertEqual(order, TILE_ORDER)
        self.assertNotIn('Backup', ''.join(tiles.values()))

    def test_tiles_use_the_classic_images(self):
        tiles, _ = self._tiles(self.editor)
        images = {
            'add-report': 'reports_3_190x150.jpg',
            'add-feature': 'add_feature_190x150.png',
            'add-person': 'add_person_190x150.png',
            'import-reports': 'reports_file_190x150.png',
            'import-features': 'add_feature_file_190x150.png',
        }
        for key, image in images.items():
            with self.subTest(tile=key):
                self.assertIn(image, tiles[key])

    def test_editor_tiles(self):
        tiles, _ = self._tiles(self.editor)
        self.assertLink(tiles['add-report'], self.add_report_url)
        self.assertLink(tiles['import-reports'], self.import_url)
        self.assertGreyed(tiles['add-feature'], 'Open a report to add features')
        self.assertGreyed(tiles['add-person'], 'Not available yet')
        self.assertGreyed(tiles['import-features'], 'Not available yet')

    def test_user_with_only_add_publication(self):
        for user in (self.only_add, self.staff):
            with self.subTest(user=user.username):
                tiles, _ = self._tiles(user)
                self.assertLink(tiles['add-report'], self.add_report_url)
                self.assertGreyed(tiles['import-reports'], 'Needs the editor role')
                self.assertGreyed(tiles['add-feature'], 'Open a report to add features')
                self.assertGreyed(tiles['add-person'], 'Not available yet')
                self.assertGreyed(tiles['import-features'], 'Not available yet')

    def test_user_with_only_change_publication(self):
        user = User.objects.create_user('onlychange')
        user.user_permissions.add(Permission.objects.get(
            content_type__app_label='publications', codename='change_publication'))
        tiles, _ = self._tiles(user)
        self.assertGreyed(tiles['add-report'], 'Needs permission to add reports')
        self.assertLink(tiles['import-reports'], self.import_url)

    def test_superuser_tiles(self):
        tiles, order = self._tiles(self.superuser)
        self.assertEqual(order, TILE_ORDER + ['django-admin'])
        self.assertLink(tiles['add-report'], self.add_report_url)
        self.assertLink(tiles['import-reports'], self.import_url)
        self.assertLink(tiles['django-admin'], reverse('admin:index'))

    def test_django_admin_tile_only_for_staff(self):
        for user, shown in ((self.staff, False), (self.editor, False), (self.only_add, False),
                            (self.staff_editor, True), (self.superuser, True)):
            with self.subTest(user=user.username):
                tiles, _ = self._tiles(user)
                self.assertEqual('django-admin' in tiles, shown)
                if shown:
                    self.assertLink(tiles['django-admin'], reverse('admin:index'))

    def test_tile_links_open_for_the_users_who_see_them(self):
        # Following a working tile must not end on the access-denied page.
        for user in (self.staff, self.only_add, self.editor, self.superuser):
            tiles, _ = self._tiles(user)
            for key, tile in tiles.items():
                if 'aria-disabled' in tile:
                    continue
                url = tile.split('href="', 1)[1].split('"', 1)[0]
                with self.subTest(user=user.username, tile=key):
                    self.assertEqual(self.get_as(user, app_path(url)).status_code, 200)
