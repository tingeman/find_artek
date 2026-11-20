"""Access control of the report write views (plan "registration" T4, roadmap FA-R53 S2).

Every view is checked for anonymous users (302 to LOGIN_URL with next), logged-in users
without the right (403) and users with it, following the permission matrix of the plan:

- add report:       add_publication              (artek_staff, artek_editor)
- edit report:      change_publication, or edit_own_publication and own
                    (form, review, finalize, appendix upload; dtu_user/artek_staff own, editor any)
- delete report:    delete_publication, or delete_own_publication and own (staff own, editor any)
- verify/unverify:  verify_publication (artek_editor), POST only

The users get their rights only from the role groups of migration 0003, as at a CAS login
(every user is in dtu_user, plus artek_staff or artek_editor). "Own" means the username is the
id_number or initials of an author, supervisor or editor of the report.
"""
from django.conf import settings
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from publications.models import Authorship, Person, Publication, Supervisorship
from publications.roles import ARTEK_EDITOR, ARTEK_STAFF
from publications.test_factories import make_user, page_path, report_type
from publications.views import report_form_target, store_report_form_data


class ReportAccessTestBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pubtype = report_type()
        cls.pub = Publication.objects.create(
            type=cls.pubtype, title='Own report', number='99-01', year=1999, verified=False)
        cls.student = Person.objects.create(first='Stu', last='Dent', id_number='s990001')
        cls.supervisor = Person.objects.create(first='Su', last='Pervisor', initials='supv')
        Authorship.objects.create(publication=cls.pub, person=cls.student, author_id=0)
        Supervisorship.objects.create(publication=cls.pub, person=cls.supervisor, supervisor_id=0)

        cls.dtu_not_own = make_user('s990999')
        cls.dtu_own = make_user('s990001')                     # author of cls.pub (id_number)
        cls.staff = make_user('stfo', ARTEK_STAFF)             # not listed on cls.pub
        cls.staff_own = make_user('supv', ARTEK_STAFF)         # supervisor of cls.pub (initials)
        cls.editor = make_user('edtr', ARTEK_EDITOR)           # not listed on cls.pub

    def assertRedirectsToLogin(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(resolve_url(settings.LOGIN_URL) + '?next='),
                        response['Location'])

    def assertDenied(self, response):
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'publications/access_denied.html')

    # Form whose session data login() stores: 'add' here, the edit form in EditReportAccessTests.
    form_target = 'add'

    def login(self, user, form_data=None):
        self.client.force_login(user)
        if form_data is not None:
            # As ReportFormView stores it: bound to the form it was entered in (T7).
            session = self.client.session
            store_report_form_data(session, self.form_target, form_data)
            session.save()

    def edit_form_data(self, title):
        """Session form data as ReportFormView stores it (lists from request.POST)."""
        return {
            'title': [title], 'type': [str(self.pubtype.pk)], 'year': ['1999'],
            'authors': [str(self.student.pk)], 'supervisors': [str(self.supervisor.pk)],
        }


class AddReportAccessTests(ReportAccessTestBase):
    """ReportFormView, ReportReviewView and ReportFinalizeView without pk (add)."""

    def test_anonymous_redirected_to_login(self):
        for name in ('add_report', 'add_report_review', 'add_report_finalize'):
            with self.subTest(name=name):
                self.assertRedirectsToLogin(self.client.get(page_path(name)))
                self.assertRedirectsToLogin(self.client.post(page_path(name), {'title': 'x'}))

    def test_dtu_users_may_not_add(self):
        for user in (self.dtu_not_own, self.dtu_own):
            with self.subTest(user=user.username):
                self.login(user, self.edit_form_data('Sneaked in'))
                for name in ('add_report', 'add_report_review', 'add_report_finalize'):
                    self.assertDenied(self.client.get(page_path(name)))
                    self.assertDenied(self.client.post(page_path(name), {'title': 'x'}))

    def test_finalize_without_permission_creates_nothing(self):
        self.login(self.dtu_own, self.edit_form_data('Sneaked in'))
        self.assertDenied(self.client.post(page_path('add_report_finalize')))
        self.assertEqual(Publication.objects.count(), 1)
        self.assertFalse(Publication.objects.filter(title='Sneaked in').exists())

    def test_staff_and_editor_may_open_the_add_form(self):
        for user in (self.staff, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertEqual(self.client.get(page_path('add_report')).status_code, 200)

    def test_review_and_finalize_without_form_data_go_back_to_the_form(self):
        self.login(self.staff)
        response = self.client.get(page_path('add_report_review'))
        self.assertRedirects(response, reverse('publications:add_report'),
                             fetch_redirect_response=False)
        response = self.client.post(page_path('add_report_finalize'))
        self.assertRedirects(response, reverse('publications:add_report'),
                             fetch_redirect_response=False)

    def test_finalize_get_saves_nothing_and_goes_to_review(self):
        self.login(self.editor, self.edit_form_data('New report'))
        response = self.client.get(page_path('add_report_finalize'))
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)
        self.assertEqual(Publication.objects.count(), 1)

    def test_review_post_passes_on_to_finalize_with_307(self):
        self.login(self.staff, self.edit_form_data('New report'))
        response = self.client.post(page_path('add_report_review'))
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response['Location'], reverse('publications:add_report_finalize'))
        self.assertEqual(Publication.objects.count(), 1)

    def test_staff_adds_report_which_stays_hidden_from_anonymous_users(self):
        self.login(self.staff, self.edit_form_data('New report'))
        response = self.client.post(page_path('add_report_finalize'))
        new = Publication.objects.get(title='New report')
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': new.pk}),
                             fetch_redirect_response=False)
        self.assertFalse(new.verified)
        self.assertEqual(new.created_by, self.staff)

        # Hidden from anonymous users (unverified): the report page sends them to the login
        # (PLAN_confidential T3; before, an access-denied page with status 200).
        self.client.logout()
        response = self.client.get(page_path('report', pk=new.pk))
        self.assertRedirectsToLogin(response)
        self.assertNotContains(response, 'New report', status_code=302)


class EditReportAccessTests(ReportAccessTestBase):
    """ReportFormView, ReportReviewView and ReportFinalizeView with pk (edit)."""

    NAMES = ('edit_report', 'edit_report_review', 'edit_report_finalize')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.form_target = report_form_target(cls.pub.pk)

    def test_anonymous_redirected_to_login(self):
        for name in self.NAMES:
            with self.subTest(name=name):
                self.assertRedirectsToLogin(self.client.get(page_path(name, pk=self.pub.pk)))
                self.assertRedirectsToLogin(self.client.post(page_path(name, pk=self.pub.pk)))

    def test_users_who_may_not_edit_are_denied(self):
        for user in (self.dtu_not_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user, self.edit_form_data('Changed'))
                for name in self.NAMES:
                    self.assertDenied(self.client.get(page_path(name, pk=self.pub.pk)))
                    self.assertDenied(self.client.post(page_path(name, pk=self.pub.pk)))

    def test_finalize_without_permission_changes_nothing(self):
        self.login(self.dtu_not_own, self.edit_form_data('Changed'))
        self.assertDenied(self.client.post(page_path('edit_report_finalize', pk=self.pub.pk)))
        self.pub.refresh_from_db()
        self.assertEqual(self.pub.title, 'Own report')

    def test_creator_who_is_not_listed_may_not_edit(self):
        self.pub.created_by = self.dtu_not_own
        self.pub.save()
        self.login(self.dtu_not_own)
        self.assertDenied(self.client.get(page_path('edit_report', pk=self.pub.pk)))

    def test_own_users_and_editor_may_open_the_edit_form(self):
        for user in (self.dtu_own, self.staff_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertEqual(self.client.get(page_path('edit_report', pk=self.pub.pk)).status_code, 200)

    def test_editor_sees_the_review_page(self):
        self.login(self.editor, self.edit_form_data('Changed'))
        response = self.client.get(page_path('edit_report_review', pk=self.pub.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'publications/add_edit_report_review.html')

    def test_review_post_passes_on_to_finalize_with_307(self):
        self.login(self.dtu_own, self.edit_form_data('Changed'))
        response = self.client.post(page_path('edit_report_review', pk=self.pub.pk))
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response['Location'],
                         reverse('publications:edit_report_finalize', kwargs={'pk': self.pub.pk}))

    def test_own_user_and_editor_save_the_edit(self):
        for user in (self.dtu_own, self.editor):
            with self.subTest(user=user.username):
                title = f'Changed by {user.username}'
                self.login(user, self.edit_form_data(title))
                response = self.client.post(page_path('edit_report_finalize', pk=self.pub.pk))
                self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                                     fetch_redirect_response=False)
                self.pub.refresh_from_db()
                self.assertEqual(self.pub.title, title)
                self.assertFalse(self.pub.verified)

    def test_unknown_publication_is_404_for_logged_in_user(self):
        self.login(self.editor)
        self.assertEqual(self.client.get(page_path('edit_report', pk=self.pub.pk + 1000)).status_code, 404)


class VerifyReportAccessTests(ReportAccessTestBase):

    def _set(self, verified):
        Publication.objects.filter(pk=self.pub.pk).update(verified=verified)

    def _verified(self):
        return Publication.objects.get(pk=self.pub.pk).verified

    def test_get_is_refused_for_everyone_and_changes_nothing(self):
        for name, start in (('verify_report', False), ('unverify_report', True)):
            self._set(start)
            path = page_path(name, pub_id=self.pub.pk)
            with self.subTest(name=name, user='anonymous'):
                self.assertEqual(self.client.get(path).status_code, 405)
            with self.subTest(name=name, user='editor'):
                self.login(self.editor)
                self.assertEqual(self.client.get(path).status_code, 405)
                self.client.logout()
            self.assertEqual(self._verified(), start)

    def test_anonymous_post_redirected_to_login(self):
        self.assertRedirectsToLogin(self.client.post(page_path('verify_report', pub_id=self.pub.pk)))
        self.assertRedirectsToLogin(self.client.post(page_path('unverify_report', pub_id=self.pub.pk)))
        self.assertFalse(self._verified())

    def test_users_without_verify_permission_are_denied(self):
        for user in (self.dtu_not_own, self.dtu_own, self.staff, self.staff_own):
            with self.subTest(user=user.username):
                self.login(user)
                self._set(False)
                self.assertDenied(self.client.post(page_path('verify_report', pub_id=self.pub.pk)))
                self.assertFalse(self._verified())
                self._set(True)
                self.assertDenied(self.client.post(page_path('unverify_report', pub_id=self.pub.pk)))
                self.assertTrue(self._verified())

    def test_editor_verifies_and_unverifies_by_post(self):
        self.login(self.editor)
        report_url = reverse('publications:report', kwargs={'pk': self.pub.pk})
        response = self.client.post(page_path('verify_report', pub_id=self.pub.pk))
        self.assertRedirects(response, report_url, fetch_redirect_response=False)
        self.assertTrue(self._verified())
        response = self.client.post(page_path('unverify_report', pub_id=self.pub.pk))
        self.assertRedirects(response, report_url, fetch_redirect_response=False)
        self.assertFalse(self._verified())

    def test_unknown_publication_is_404_for_logged_in_user(self):
        self.login(self.editor)
        self.assertEqual(
            self.client.post(page_path('verify_report', pub_id=self.pub.pk + 1000)).status_code, 404)


class DeleteReportAccessTests(ReportAccessTestBase):

    def _path(self):
        return page_path('delete_report', pk=self.pub.pk)

    def test_anonymous_redirected_to_login(self):
        self.assertRedirectsToLogin(self.client.get(self._path()))
        self.assertRedirectsToLogin(self.client.post(self._path(), {'action': 'delete'}))
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())

    def test_users_who_may_not_delete_are_denied(self):
        # dtu_user has no delete right, not even for own reports; staff only for own ones.
        for user in (self.dtu_not_own, self.dtu_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(self._path()))
                self.assertDenied(self.client.post(self._path(), {'action': 'delete'}))
                self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())

    def test_creator_who_may_not_delete_is_denied(self):
        # Deliberate change (plan registration, matrix): "the creator may delete" is gone.
        self.pub.created_by = self.dtu_not_own
        self.pub.save()
        self.login(self.dtu_not_own)
        self.assertDenied(self.client.post(self._path(), {'action': 'delete'}))
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())

    def test_own_staff_and_editor_see_the_confirmation_page(self):
        for user in (self.staff_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                response = self.client.get(self._path())
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'publications/delete_report_form.html')

    def test_own_staff_deletes(self):
        self.login(self.staff_own)
        response = self.client.post(self._path(), {'action': 'delete'})
        self.assertRedirects(response, reverse('publications:reports'), fetch_redirect_response=False)
        self.assertFalse(Publication.objects.filter(pk=self.pub.pk).exists())

    def test_editor_deletes(self):
        self.login(self.editor)
        response = self.client.post(self._path(), {'action': 'delete'})
        self.assertRedirects(response, reverse('publications:reports'), fetch_redirect_response=False)
        self.assertFalse(Publication.objects.filter(pk=self.pub.pk).exists())


class UploadAppendixRoleTests(ReportAccessTestBase):
    """The appendix upload page by role (the view itself: test_upload_appendix_access)."""

    def _path(self):
        return page_path('upload_appendix', pk=self.pub.pk)

    def test_anonymous_redirected_to_login(self):
        self.assertRedirectsToLogin(self.client.get(self._path()))

    def test_users_who_may_not_edit_are_denied(self):
        for user in (self.dtu_not_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(self._path()))
                self.assertDenied(self.client.post(self._path(), {'action': 'submit'}))

    def test_own_users_and_editor_may_open_the_page(self):
        for user in (self.dtu_own, self.staff_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertEqual(self.client.get(self._path()).status_code, 200)


class ReportPageActionsTests(ReportAccessTestBase):
    """report.html: verify/unverify as POST forms, change-number pencil for editors only."""

    def test_editor_gets_post_form_for_verify_and_pencil(self):
        self.login(self.editor)
        response = self.client.get(page_path('report', pk=self.pub.pk))
        verify_url = reverse('publications:verify_report', kwargs={'pub_id': self.pub.pk})
        self.assertContains(response, f'<form method="post" action="{verify_url}"')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertNotContains(response, f'href="{verify_url}"')
        self.assertContains(
            response, reverse('publications:change_report_number', kwargs={'pk': self.pub.pk}))

    def test_editor_gets_post_form_for_unverify(self):
        Publication.objects.filter(pk=self.pub.pk).update(verified=True)
        self.login(self.editor)
        response = self.client.get(page_path('report', pk=self.pub.pk))
        unverify_url = reverse('publications:unverify_report', kwargs={'pub_id': self.pub.pk})
        self.assertContains(response, f'<form method="post" action="{unverify_url}"')
        self.assertNotContains(response, f'href="{unverify_url}"')

    def test_others_get_neither_verify_nor_pencil(self):
        verify_url = reverse('publications:verify_report', kwargs={'pub_id': self.pub.pk})
        number_url = reverse('publications:change_report_number', kwargs={'pk': self.pub.pk})
        for user in (self.dtu_not_own, self.dtu_own, self.staff, self.staff_own):
            with self.subTest(user=user.username):
                self.login(user)
                response = self.client.get(page_path('report', pk=self.pub.pk))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, verify_url)
                self.assertNotContains(response, number_url)
