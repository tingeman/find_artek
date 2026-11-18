"""Access control of the other write views (plan "registration" T5, roadmap FA-R53 S3, S5, S6).

Per view: anonymous (302 to LOGIN_URL with next; JSON 401 for the ajax endpoint), a logged-in
user who may not (403), and a user who may (works), following the permission matrix:

- change report number, Excel import:  change_publication (artek_editor)
- bulk delete:                         delete_publication (artek_editor)
- add feature (coordinates, map):      add_feature and may edit the report (dtu_user/artek_staff
                                       own, artek_editor any)
- delete feature:                      delete_feature, or delete_own_feature and listed on a
                                       report the feature belongs to (T16; the creator alone
                                       no longer counts)
- add_person_ajax:                     add_person (every role group)

Also: /debug-root/ is gone (404), the report page shows the feature buttons only to users who
may use them, and the uploaded Excel file is removed after parsing, also when parsing fails.

The users get their rights only from the role groups of migration 0003 (see
test_report_access). No media files are used; the Excel tests mock or feed the parser small
bytes made in the test.
"""
import datetime
import os
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from publications import views
from publications.models import Feature, Person, Publication
from publications.test_report_access import ReportAccessTestBase, _path


class WriteAccessTestBase(ReportAccessTestBase):
    """cls.pub (unverified) with its author cls.dtu_own (dtu_user) and supervisor
    cls.staff_own (artek_staff); cls.dtu_not_own, cls.staff (not listed), cls.editor."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.no_role = User.objects.create_user('norole', password='x')   # in no group


class DebugRootRemovedTests(WriteAccessTestBase):

    def test_debug_root_is_404(self):
        self.assertEqual(self.client.get('/debug-root/').status_code, 404)
        self.login(self.editor)
        self.assertEqual(self.client.get('/debug-root/').status_code, 404)


class ChangeReportNumberAccessTests(WriteAccessTestBase):

    def path(self):
        return _path('change_report_number', pk=self.pub.pk)

    def post_new_number(self):
        return self.client.post(self.path(), {'new_number': '99-55', 'confirm_change': 'on'})

    def test_anonymous_redirected_to_login(self):
        self.assertRedirectsToLogin(self.client.get(self.path()))
        self.assertRedirectsToLogin(self.post_new_number())

    def test_only_editors_may_change_the_number(self):
        for user in (self.dtu_own, self.staff_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(self.path()))
                self.assertDenied(self.post_new_number())
        self.pub.refresh_from_db()
        self.assertEqual(self.pub.number, '99-01')

    def test_editor_may_open_the_form(self):
        self.login(self.editor)
        self.assertEqual(self.client.get(self.path()).status_code, 200)

    def test_unknown_report_is_404_for_logged_in_user(self):
        self.login(self.editor)
        self.assertEqual(
            self.client.get(_path('change_report_number', pk=self.pub.pk + 1000)).status_code, 404)


class AddFeatureAccessTests(WriteAccessTestBase):

    def coordinates_data(self, name):
        return {
            'name': name, 'type': Feature.PHOTO, 'date': '2000-01-01', 'pos_quality': 'Unknown',
            'x_coordinate': '-50.5', 'y_coordinate': '67.0', 'spatial_reference_system': '4326',
        }

    def map_data(self, name):
        return {
            'name': name, 'type': Feature.PHOTO, 'date': '2000-01-01', 'pos_quality': 'Unknown',
            'geojson_data': '{"type": "FeatureCollection", "features": [{"type": "Feature", '
                            '"geometry": {"type": "Point", "coordinates": [-50.5, 67.0]}}]}',
        }

    def paths(self, pk=None):
        pk = self.pub.pk if pk is None else pk
        return {
            'coordinates': _path('add_feature_coordinates', report_pk=pk),
            'map': _path('add_feature_by_map', report_pk=pk),
        }

    def post_both(self, name):
        paths = self.paths()
        return (self.client.post(paths['coordinates'], self.coordinates_data(name)),
                self.client.post(paths['map'], self.map_data(name)))

    def test_anonymous_redirected_to_login(self):
        for path in self.paths().values():
            with self.subTest(path=path):
                self.assertRedirectsToLogin(self.client.get(path))
        for response in self.post_both('Sneaked in'):
            self.assertRedirectsToLogin(response)
        self.assertFalse(Feature.objects.exists())

    def test_users_who_may_not_edit_the_report_are_denied(self):
        for user in (self.dtu_not_own, self.staff, self.no_role):
            with self.subTest(user=user.username):
                self.login(user)
                for path in self.paths().values():
                    self.assertDenied(self.client.get(path))
                for response in self.post_both('Sneaked in'):
                    self.assertDenied(response)
        self.assertFalse(Feature.objects.exists())

    def test_own_users_and_editor_may_open_the_forms(self):
        for user in (self.dtu_own, self.staff_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                for path in self.paths().values():
                    self.assertEqual(self.client.get(path).status_code, 200)

    def test_author_adds_features_by_coordinates_and_by_map(self):
        self.login(self.dtu_own)
        report_url = reverse('publications:report', kwargs={'pk': self.pub.pk})
        for response in self.post_both('Own feature'):
            self.assertRedirects(response, report_url, fetch_redirect_response=False)
        features = Feature.objects.filter(name='Own feature')
        self.assertEqual(features.count(), 2)
        for feature in features:
            self.assertEqual(feature.created_by, self.dtu_own)
            self.assertEqual(list(feature.publications.all()), [self.pub])

    def test_unknown_report_is_404_for_logged_in_user(self):
        self.login(self.editor)
        for path in self.paths(pk=self.pub.pk + 1000).values():
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_report_page_shows_add_feature_buttons_only_to_users_who_may_add(self):
        coordinates_url = reverse('publications:add_feature_coordinates',
                                  kwargs={'report_pk': self.pub.pk})
        for user, allowed in ((self.dtu_own, True), (self.editor, True),
                              (self.dtu_not_own, False), (self.staff, False)):
            with self.subTest(user=user.username):
                self.login(user)
                response = self.client.get(_path('report', pk=self.pub.pk))
                self.assertEqual(response.status_code, 200)
                self.assertIs(response.context['can_add_feature'], allowed)
                if allowed:
                    self.assertContains(response, coordinates_url)
                else:
                    self.assertNotContains(response, coordinates_url)


class DeleteFeatureAccessTests(WriteAccessTestBase):
    """Delete rights follow the report (T16): cls.pub lists cls.dtu_own (author) and
    cls.staff_own (supervisor); cls.other_pub (verified, public) lists none of the users."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_pub = Publication.objects.create(
            type=cls.pubtype, title='Other report', number='99-02', year=1999, verified=True)

        def feature(name, created_by, *pubs):
            f = Feature.objects.create(name=name, date=datetime.date(2000, 1, 1),
                                       created_by=created_by)
            f.publications.add(*pubs)
            return f

        # On cls.pub, created by a user who is not listed on it.
        cls.pub_feature = feature('Feature on pub', cls.dtu_not_own, cls.pub)
        # On cls.pub, created by an editor.
        cls.editor_feature = feature('Editor feature', cls.editor, cls.pub)
        # On cls.pub and cls.other_pub, created by a user listed on neither.
        cls.both_feature = feature('Feature on both', cls.staff, cls.pub, cls.other_pub)
        # Only on cls.other_pub, created by the author of cls.pub.
        cls.other_feature = feature('Feature on other', cls.dtu_own, cls.other_pub)
        # On no report, created by the author of cls.pub.
        cls.orphan_feature = feature('Orphan feature', cls.dtu_own)

    def path(self, feature):
        return _path('delete_feature', pk=feature.pk)

    def assertDeniedAndKept(self, feature):
        self.assertDenied(self.client.get(self.path(feature)))
        self.assertDenied(self.client.post(self.path(feature)))
        self.assertTrue(Feature.objects.filter(pk=feature.pk).exists())

    def test_anonymous_redirected_to_login(self):
        for feature in (self.pub_feature, self.other_feature, self.orphan_feature):
            with self.subTest(feature=feature.name):
                self.assertRedirectsToLogin(self.client.get(self.path(feature)))
                self.assertRedirectsToLogin(self.client.post(self.path(feature)))
                self.assertTrue(Feature.objects.filter(pk=feature.pk).exists())

    def test_users_not_listed_on_a_linked_report_are_denied(self):
        # dtu_not_own created pub_feature and staff created both_feature, but neither is
        # listed on a report of them: having created a feature no longer counts (T16).
        for user in (self.dtu_not_own, self.staff, self.no_role):
            with self.subTest(user=user.username):
                self.login(user)
                for feature in (self.pub_feature, self.both_feature, self.editor_feature):
                    self.assertDeniedAndKept(feature)

    def test_creator_not_listed_is_denied(self):
        # dtu_own created other_feature and orphan_feature but is not listed on their reports
        # (orphan_feature is on none); staff_own is listed on cls.pub only.
        for user in (self.dtu_own, self.staff_own):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDeniedAndKept(self.other_feature)
                self.assertDeniedAndKept(self.orphan_feature)

    def test_listed_author_deletes_feature_created_by_someone_else(self):
        self.login(self.dtu_own)
        self.assertEqual(self.client.get(self.path(self.pub_feature)).status_code, 200)
        response = self.client.post(self.path(self.pub_feature))
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        self.assertFalse(Feature.objects.filter(pk=self.pub_feature.pk).exists())

    def test_listed_supervisor_deletes_feature_created_by_an_editor(self):
        self.login(self.staff_own)
        self.assertEqual(self.client.get(self.path(self.editor_feature)).status_code, 200)
        self.client.post(self.path(self.editor_feature))
        self.assertFalse(Feature.objects.filter(pk=self.editor_feature.pk).exists())

    def test_listed_on_one_of_two_reports_may_delete(self):
        self.login(self.dtu_own)
        self.assertEqual(self.client.get(self.path(self.both_feature)).status_code, 200)
        self.client.post(self.path(self.both_feature))
        self.assertFalse(Feature.objects.filter(pk=self.both_feature.pk).exists())

    def test_editor_deletes_any_feature(self):
        self.login(self.editor)
        for feature in (self.pub_feature, self.other_feature, self.orphan_feature):
            with self.subTest(feature=feature.name):
                self.client.post(self.path(feature))
                self.assertFalse(Feature.objects.filter(pk=feature.pk).exists())

    def test_unknown_feature_is_404_for_logged_in_user(self):
        self.login(self.editor)
        self.assertEqual(
            self.client.get(_path('delete_feature', pk=self.orphan_feature.pk + 1000)).status_code,
            404)

    def assertDeleteButtons(self, response, features, deletable):
        self.assertEqual(response.context['deletable_feature_ids'], deletable)
        for feature in features:
            url = reverse('publications:delete_feature', kwargs={'pk': feature.pk})
            if feature.pk in deletable:
                self.assertContains(response, url)
            else:
                self.assertNotContains(response, url)

    def test_report_page_shows_delete_buttons_per_user(self):
        on_pub = (self.pub_feature, self.editor_feature, self.both_feature)
        all_on_pub = {f.pk for f in on_pub}
        cases = (
            (self.dtu_own, all_on_pub),      # author of cls.pub
            (self.staff_own, all_on_pub),    # supervisor of cls.pub
            (self.editor, all_on_pub),
            (self.dtu_not_own, set()),       # created pub_feature, not listed
            (self.staff, set()),             # created both_feature, not listed
            (self.no_role, set()),
        )
        for user, deletable in cases:
            with self.subTest(user=user.username):
                self.login(user)
                response = self.client.get(_path('report', pk=self.pub.pk))
                self.assertDeleteButtons(response, on_pub, deletable)

    def test_other_report_page_shows_delete_buttons_per_user(self):
        on_other = (self.other_feature, self.both_feature)
        cases = (
            (None, set()),                   # anonymous (the report is verified, so visible)
            (self.dtu_own, {self.both_feature.pk}),   # created other_feature; listed on pub
            (self.editor, {f.pk for f in on_other}),
        )
        for user, deletable in cases:
            with self.subTest(user=getattr(user, 'username', 'anonymous')):
                self.client.logout()
                if user is not None:
                    self.login(user)
                response = self.client.get(_path('report', pk=self.other_pub.pk))
                self.assertEqual(response.status_code, 200)
                self.assertDeleteButtons(response, on_other, deletable)


class AddPersonAjaxAccessTests(WriteAccessTestBase):
    """add_person_ajax answers in JSON: 401 for anonymous users, 403 without add_person."""

    def post(self, name='New Person'):
        return self.client.post(_path('add_person_ajax'), {'name': name},
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_anonymous_gets_json_401(self):
        response = self.post()
        self.assertEqual(response.status_code, 401)
        self.assertIn('error', response.json())
        self.assertFalse(Person.objects.filter(last='Person').exists())

    def test_user_without_add_person_gets_json_403(self):
        self.login(self.no_role)
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertIn('error', response.json())
        self.assertFalse(Person.objects.filter(last='Person').exists())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(_path('add_person_ajax')).status_code, 405)

    def test_dtu_user_adds_person(self):
        self.login(self.dtu_not_own)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        person = Person.objects.get(pk=response.json()['person_id'])
        self.assertEqual(person.created_by, self.dtu_not_own)


class ExcelImportAccessTests(WriteAccessTestBase):

    def path(self):
        return _path('add_reports_from_file_upload')

    def upload(self, content=b'not really excel'):
        return self.client.post(self.path(), {
            'file_type': 'xlsx',
            'file': SimpleUploadedFile('reports.xlsx', content),
        })

    def test_anonymous_redirected_to_login(self):
        with mock.patch.object(views, 'xlsx_pubs') as parser:
            self.assertRedirectsToLogin(self.client.get(self.path()))
            self.assertRedirectsToLogin(self.upload())
        parser.assert_not_called()

    def test_only_editors_may_import(self):
        with mock.patch.object(views, 'xlsx_pubs') as parser:
            for user in (self.dtu_own, self.staff_own, self.staff):
                with self.subTest(user=user.username):
                    self.login(user)
                    self.assertDenied(self.client.get(self.path()))
                    self.assertDenied(self.upload())
        parser.assert_not_called()

    def test_editor_imports_and_the_file_is_removed_after_parsing(self):
        seen = {}

        def parser(file_path, user=None):
            seen['path'], seen['user'] = file_path, user
            with open(file_path, 'rb') as f:
                seen['content'] = f.read()
            return []

        self.login(self.editor)
        self.assertEqual(self.client.get(self.path()).status_code, 200)
        with mock.patch.object(views, 'xlsx_pubs', side_effect=parser):
            response = self.upload(b'xlsx bytes')
        self.assertRedirects(response, reverse('publications:add_reports_from_file_upload'),
                             fetch_redirect_response=False)
        self.assertEqual(seen['content'], b'xlsx bytes')
        self.assertEqual(seen['user'], self.editor)
        self.assertFalse(os.path.exists(seen['path']))

    def test_file_is_removed_when_parsing_fails(self):
        seen = {}
        real_parser = views.xlsx_pubs

        def parser(file_path, user=None):
            seen['path'] = file_path
            return real_parser(file_path, user=user)   # the bytes are no xlsx: raises

        self.login(self.editor)
        with mock.patch.object(views, 'xlsx_pubs', side_effect=parser):
            response = self.upload(b'not really excel')
        self.assertRedirects(response, reverse('publications:add_reports_from_file_upload'),
                             fetch_redirect_response=False)
        self.assertFalse(os.path.exists(seen['path']))
        self.assertEqual(Publication.objects.count(), 1)
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertTrue(any('could not be read' in m for m in messages), messages)


class BulkDeleteAccessTests(WriteAccessTestBase):

    def path(self):
        return _path('bulk_delete_publications')

    def confirm_delete(self):
        return self.client.post(self.path(), {
            'selected_publications': [str(self.pub.pk)], 'confirm': 'yes'})

    def test_anonymous_redirected_to_login(self):
        self.assertRedirectsToLogin(self.client.get(self.path()))
        self.assertRedirectsToLogin(self.confirm_delete())
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())

    def test_only_editors_may_bulk_delete(self):
        # staff_own may delete cls.pub on its own page, but not with the bulk tool
        for user in (self.dtu_own, self.staff_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(self.path()))
                self.assertDenied(self.confirm_delete())
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())

    def test_editor_bulk_deletes(self):
        self.login(self.editor)
        self.assertEqual(self.client.get(self.path()).status_code, 200)
        self.confirm_delete()
        self.assertFalse(Publication.objects.filter(pk=self.pub.pk).exists())
