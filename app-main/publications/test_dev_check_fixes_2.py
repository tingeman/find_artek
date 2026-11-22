"""Fixes from the owner's second round of dev checks (plan release-2026-7 T13).

- Directory lookups have a total time limit (publications.directory_time_limit), name
  resolution included: a lookup that hangs (here: ldap3.Server blocks, as getaddrinfo did) ends
  after DIRECTORY_LOOKUP_TIME_LIMIT seconds. The person step then shows no directory choice
  and logs one WARNING (exception type only); at save the report is not saved ("could not be
  fetched"); at CAS login the roles and user details stay as they are (as on an LDAP error).
- The report form and the appendix upload form are submitted once (submit-guard.js: Submit
  disabled, a "busy" notice); the report form sent by file-upload.js gets the next URL as
  JSON, so the browser loads the next page once.
- The mobile menu has the desktop header's items in the same order; base.css carries the
  release version.
- The "Confirm person" buttons are solid buttons.
- Importing api.views logs nothing.

No network: ldap3 is mocked, and the mocks block on an Event that the test sets at the end.
Everything is made-up factory data.
"""
import importlib
import logging
import re
import threading
import time
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.templatetags.static import static
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from ldap3.core.exceptions import LDAPSocketOpenError

from publications import directory_time_limit, roles, utils_person
from publications.directory_time_limit import DirectoryTimeout, call_with_time_limit
from publications.models import Person, Publication
from publications.roles import ARTEK_EDITOR, ARTEK_STAFF
from publications.test_dev_check_fixes import FixFixture
from publications.test_factories import make_user, page_path
from publications.test_person_ldap_lookup import DIRECTORY, DirectoryLookupTestBase
from publications.test_roles import EDITOR_DN, STAFF_DN, _login, _names

LIMIT = 0.3  # seconds, DIRECTORY_LOOKUP_TIME_LIMIT in these tests
WITHIN = 3.0  # a bounded request ends well within this (the hang would last 30 s)
REAL_FIND_LDAP_PERSON = utils_person.find_ldap_person  # before any test patches it


class HangingDirectoryMixin:
    """ldap3.Server blocks until the test ends (or 30 s), as a name lookup that hangs."""

    def hang_directory(self, *modules):
        release = threading.Event()
        self.addCleanup(release.set)

        def hang(*args, **kwargs):
            release.wait(30)
            raise LDAPSocketOpenError('released')

        for module in modules:
            patcher = mock.patch(f'{module}.ldap3.Server', side_effect=hang)
            patcher.start()
            self.addCleanup(patcher.stop)

    def assertQuick(self, started):
        self.assertLess(time.monotonic() - started, WITHIN)


@override_settings(DIRECTORY_LOOKUP_TIME_LIMIT=LIMIT)
class CallWithTimeLimitTests(HangingDirectoryMixin, SimpleTestCase):

    def test_result_and_exception_are_handed_over(self):
        self.assertEqual(call_with_time_limit(lambda a, b=0: a + b, 1, b=2), 3)
        with self.assertRaises(LDAPSocketOpenError):
            call_with_time_limit(mock.Mock(side_effect=LDAPSocketOpenError('down')))

    def test_a_hanging_call_ends_at_the_limit(self):
        release = threading.Event()
        self.addCleanup(release.set)
        started = time.monotonic()
        with self.assertRaises(DirectoryTimeout):
            call_with_time_limit(release.wait, 30)
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, LIMIT * 0.9)
        self.assertLess(elapsed, WITHIN)

    def test_hanging_calls_do_not_pile_up(self):
        release = threading.Event()
        self.addCleanup(release.set)
        for _ in range(directory_time_limit.MAX_RUNNING):
            with self.assertRaises(DirectoryTimeout):
                call_with_time_limit(release.wait, 30)
        # All slots taken by stuck calls: the next one doesn't start a thread, and still ends.
        threads = threading.active_count()
        started = time.monotonic()
        with self.assertRaises(DirectoryTimeout):
            call_with_time_limit(release.wait, 30)
        self.assertQuick(started)
        self.assertEqual(threading.active_count(), threads)
        # Once the stuck calls return, the slots are free again.
        release.set()
        deadline = time.monotonic() + WITHIN
        while time.monotonic() < deadline:
            try:
                self.assertEqual(call_with_time_limit(lambda: 'ok'), 'ok')
                break
            except DirectoryTimeout:
                pass
        else:
            self.fail('the slots were not freed')

    def test_default_limit(self):
        with self.settings():
            del settings.DIRECTORY_LOOKUP_TIME_LIMIT
            self.assertEqual(directory_time_limit.time_limit(),
                             directory_time_limit.DEFAULT_TIME_LIMIT)

    @override_settings(USE_LDAP=True)
    def test_find_ldap_person_is_bounded(self):
        self.hang_directory('publications.utils_person')
        started = time.monotonic()
        with self.assertRaises(DirectoryTimeout):
            utils_person.find_ldap_person(initials='zqska')
        self.assertQuick(started)


@override_settings(DIRECTORY_LOOKUP_TIME_LIMIT=LIMIT)
class HangingDirectoryInReportFormTests(HangingDirectoryMixin, DirectoryLookupTestBase):
    """The report form's person step and save with the real find_ldap_person and ldap3.Server
    hanging."""

    def real_directory(self):
        self.find.side_effect = REAL_FIND_LDAP_PERSON
        self.hang_directory('publications.utils_person')

    def test_person_step_shows_no_directory_choice_and_logs_one_warning(self):
        self.real_directory()
        self.start(authors=['zqska'])
        started = time.monotonic()
        with self.assertLogs('publications', level='WARNING') as logs:
            page = self.step_page()
        self.assertQuick(started)
        self.assertEqual(page.context['directory_choices'], [])
        self.assertContains(page, 'value="create_new"')
        warnings = [r for r in logs.records if r.levelno >= logging.WARNING]
        self.assertEqual(len(warnings), 1, logs.output)
        self.assertEqual(warnings[0].name, 'publications.workflows.person')
        self.assertIn('DirectoryTimeout', logs.output[0])
        self.assertNotIn('zqska', logs.output[0])

    def test_save_is_refused_and_nothing_saved(self):
        persons_before = Person.objects.count()
        self.walk(self.start(authors=['zqska']), {'zqska': DIRECTORY})  # directory answers
        self.real_directory()  # ... and hangs at save
        started = time.monotonic()
        with self.assertLogs('publications.workflows.person', level='WARNING'):
            response, _ = self.finalize(page_path('add_report_finalize'))
        self.assertQuick(started)
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)
        self.assertIn('could not be fetched', ' '.join(self.messages_of(response)))
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(Person.objects.count(), persons_before)


@override_settings(USE_LDAP=True, DIRECTORY_LOOKUP_TIME_LIMIT=LIMIT,
                   LDAP_GROUP_ARTEK_STAFF=STAFF_DN, LDAP_GROUP_ARTEK_EDITOR=EDITOR_DN)
class HangingDirectoryAtLoginTests(HangingDirectoryMixin, TestCase):

    def test_roles_and_details_kept_as_on_an_ldap_error(self):
        user = User.objects.create_user('s990002', first_name='Kept', email='kept@example.org')
        user.groups.add(Group.objects.get(name=ARTEK_EDITOR))
        self.hang_directory('publications.roles')
        started = time.monotonic()
        with self.assertLogs('publications.roles', level='WARNING') as logs:
            _login(user)
        self.assertQuick(started)
        user.refresh_from_db()
        self.assertEqual(_names(user), {'dtu_user', ARTEK_EDITOR})
        self.assertEqual((user.first_name, user.email), ('Kept', 'kept@example.org'))
        self.assertIn('DirectoryTimeout', logs.output[0])
        self.assertNotIn('kept@example.org', logs.output[0])

    def test_ad_user_info_raises_ldap_lookup_error(self):
        self.hang_directory('publications.roles')
        with self.assertRaises(roles.LdapLookupError):
            roles.ad_user_info('s990002', [STAFF_DN])


class SubmitGuardTests(FixFixture):

    def guard_script(self):
        return f'<script src="{static("publications/js/submit-guard.js")}?v={settings.STATIC_ASSET_VERSION}"'

    def test_report_form_pages(self):
        for path in (page_path('add_report'), page_path('edit_report', pk=self.pub.pk)):
            with self.subTest(path=path):
                html = self.get(path).content.decode()
                self.assertRegex(html, r'<form [^>]*id="add-report-form"[^>]*data-submit-guard=')
                self.assertIn(self.guard_script(), html)
                # Loaded before file-upload.js, which uses window.submitGuard.
                self.assertLess(html.index(self.guard_script()),
                                html.index(static('publications/js/file-upload.js')))
                # No name on the submit button: a disabled button is not sent.
                self.assertRegex(html, r'<button type="submit" class="btn btn-primary" id="process-submit">')

    def test_appendix_upload_page(self):
        path = page_path('upload_appendix', pk=self.pub.pk)
        html = self.get(path).content.decode()
        self.assertIn(self.guard_script(), html)
        self.assertEqual(len(re.findall(r'<form [^>]*data-submit-guard=', html)), 1)  # upload
        session = self.client.session
        session[f'appendix_upload_{self.pub.pk}'] = [{'filename': 'appendix.pdf', 'size': 10}]
        session.save()
        html = self.get(path).content.decode()
        # Upload and "Submit and Attach"; not the Remove and Cancel forms.
        self.assertEqual(len(re.findall(r'<form [^>]*data-submit-guard=', html)), 2)
        self.assertRegex(html, r'data-submit-guard="[^"]*">\s*<input type="hidden" name="csrfmiddlewaretoken"[^>]*>\s*<input type="hidden" name="action" value="submit">')

    def test_script_guards_once_and_unlocks_on_pageshow(self):
        path = settings.BASE_DIR / 'publications' / 'static' / 'publications' / 'js' / 'submit-guard.js'
        script = path.read_text(encoding='utf-8')
        self.assertIn("document.addEventListener('submit'", script)
        self.assertIn('stopImmediatePropagation', script)
        self.assertIn("addEventListener('pageshow'", script)
        self.assertIn('button.disabled = true', script)
        upload = (path.parent / 'file-upload.js').read_text(encoding='utf-8')
        self.assertIn('window.submitGuard.setText', upload)
        self.assertIn('window.submitGuard.unlock', upload)


@override_settings(USE_LDAP=False)
class ReportFormXhrTests(FixFixture):

    def form_data(self):
        return {'title': 'Xhr report', 'type': str(self.pubtype.pk), 'year': '2011',
                'abstract': '', 'comment': '', 'authors': [str(self.plain.pk)]}

    def test_xhr_gets_the_next_url_as_json(self):
        self.client.force_login(self.editor)
        response = self.client.post(page_path('add_report'), self.form_data(),
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True,
                                           'redirect': reverse('publications:add_report_review')})

    def test_plain_post_is_redirected(self):
        self.client.force_login(self.editor)
        response = self.client.post(page_path('add_report'), self.form_data())
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)

    def test_invalid_xhr_post_gets_the_form_page(self):
        self.client.force_login(self.editor)
        response = self.client.post(page_path('add_report'), {'title': ''},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="add-report-form"')


class MobileMenuTests(FixFixture):

    def menu(self, user=None):
        if user is None:
            self.client.logout()
            response = self.client.get(page_path('frontpage'))
            self.assertEqual(response.status_code, 200)
        else:
            response = self.get(page_path('frontpage'), user)
        html = response.content.decode()
        menu = html[html.index('id="mobile-menu-expanded"'):]
        menu = menu[:menu.index('</ul>')]
        return re.findall(r'<a class="nav-link [^"]*" href="[^"]*">([^<]+)</a>', menu)

    def test_items_in_the_desktop_order(self):
        items = ['Frontpage', 'Map', 'Reports', 'Persons', 'API']
        self.assertEqual(self.menu(), items)
        self.assertEqual(self.menu(make_user('dtu913', 'dtu_user')), items)
        self.assertEqual(self.menu(make_user('staff913', ARTEK_STAFF)), items + ['Administration'])
        self.assertEqual(self.menu(self.editor), items + ['Administration'])

    def test_api_link(self):
        html = self.get(page_path('frontpage')).content.decode()
        menu = html[html.index('id="mobile-menu-expanded"'):]
        self.assertIn(f'href="{reverse("schema-swagger-ui")}"', menu[:menu.index('</ul>')])

    def test_menu_box_sizes_to_its_items(self):
        css = (settings.BASE_DIR / 'publications' / 'static' / 'publications' / 'css'
               / 'base.css').read_text(encoding='utf-8')
        rule = css[css.index('.mobile-menu-expanded {'):]
        rule = rule[:rule.index('}')]
        self.assertIn('height: auto;', rule)
        self.assertNotIn('100vh', rule)

    def test_base_css_carries_the_version(self):
        html = self.get(page_path('frontpage')).content.decode()
        self.assertIn(f'href="{static("publications/css/base.css")}?v={settings.STATIC_ASSET_VERSION}"',
                      html)


class ConfirmButtonTests(FixFixture):

    def test_solid_confirm_buttons(self):
        for name in ('person_merge', 'person'):
            with self.subTest(page=name):
                html = self.get(page_path(name, pk=self.marked.pk)).content.decode()
                self.assertIn('<button type="submit" class="btn btn-success">Confirm person</button>',
                              html)
                self.assertNotIn('btn-outline-success', html)


class ApiImportLogTests(SimpleTestCase):

    def test_importing_api_views_logs_nothing(self):
        import api.views
        with self.assertNoLogs(level='INFO'):
            importlib.reload(api.views)
