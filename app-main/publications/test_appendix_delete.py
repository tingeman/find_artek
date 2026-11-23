"""Delete one appendix of a report (roadmap FA-R104, plan features T9).

Rule (permissions.py ``edit``, as for the upload): Publication.is_editable_by. Anonymous users
are sent to the login, a logged-in user who may not edit the report gets 403. GET shows the
confirmation page and deletes nothing; POST removes the link, and the FileObject and its file
only when nothing else uses them. A missing file on disk is logged, not an error.

The users get their rights from the role groups of migration 0003 (ReportAccessTestBase:
author ``dtu_own``, supervisor ``staff_own``, not listed ``dtu_not_own``/``staff``, and the
artek_editor ``editor``). The files are tiny fixtures written to a temporary MEDIA_ROOT.
"""
import os
import shutil
import tempfile

from django.test import override_settings
from django.urls import reverse

from publications.models import Appendenciesship, Feature, FileObject, Publication
from publications.test_factories import page_path
from publications.test_report_access import ReportAccessTestBase


class AppendixDeleteTestBase(ReportAccessTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_pub = Publication.objects.create(
            type=cls.pubtype, title='Other report', number='99-02', year=1999, verified=True)

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='find_artek_appendix_delete_')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

    def make_appendix(self, publication, name='appendix.txt', write=True):
        """A FileObject at reports/1999/appendices/<name> linked as appendix of
        ``publication``; the file is written unless ``write`` is False."""
        relpath = f'reports/1999/appendices/{name}'
        if write:
            full = os.path.join(self.media_root, *relpath.split('/'))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'wb') as f:
                f.write(b'made-up appendix\n')
        fileobject = FileObject.objects.create(file=relpath)
        Appendenciesship.objects.create(publication=publication, fileobject=fileobject)
        return fileobject

    def full_path(self, fileobject):
        return os.path.join(self.media_root, *fileobject.file.name.split('/'))

    def path(self, fileobject, publication=None):
        return page_path('delete_appendix', pk=(publication or self.pub).pk, file_pk=fileobject.pk)

    def post_delete(self, fileobject, publication=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.path(fileobject, publication))

    def assertKept(self, fileobject, publication=None):
        self.assertTrue(Appendenciesship.objects.filter(
            publication=publication or self.pub, fileobject=fileobject).exists())
        self.assertTrue(FileObject.objects.filter(pk=fileobject.pk).exists())
        self.assertTrue(os.path.exists(self.full_path(fileobject)))

    def assertGone(self, fileobject):
        self.assertFalse(Appendenciesship.objects.filter(fileobject=fileobject).exists())
        self.assertFalse(FileObject.objects.filter(pk=fileobject.pk).exists())
        self.assertFalse(os.path.exists(self.full_path(fileobject)))


class AppendixDeleteAccessTests(AppendixDeleteTestBase):

    def test_anonymous_redirected_to_login(self):
        appendix = self.make_appendix(self.pub)
        self.assertRedirectsToLogin(self.client.get(self.path(appendix)))
        self.assertRedirectsToLogin(self.post_delete(appendix))
        self.assertKept(appendix)

    def test_users_who_may_not_edit_get_403(self):
        appendix = self.make_appendix(self.pub)
        for user in (self.dtu_not_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(self.path(appendix)))
                self.assertDenied(self.post_delete(appendix))
        self.assertKept(appendix)

    def test_author_supervisor_and_editor_may_delete(self):
        for user in (self.dtu_own, self.staff_own, self.editor):
            with self.subTest(user=user.username):
                appendix = self.make_appendix(self.pub, name=f'{user.username}.txt')
                self.login(user)
                response = self.post_delete(appendix)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response['Location'],
                                 reverse('publications:report', kwargs={'pk': self.pub.pk}))
                self.assertGone(appendix)

    def test_success_message_on_the_report_page(self):
        appendix = self.make_appendix(self.pub, name='msg.txt')
        self.login(self.editor)
        self.post_delete(appendix)
        # The redirect target with the test client's path (FORCE_SCRIPT_NAME, app_path).
        response = self.client.get(page_path('report', pk=self.pub.pk))
        self.assertContains(response, 'Appendix &quot;msg.txt&quot; was deleted from report 99-01')
        self.assertGone(appendix)

    def test_get_shows_confirmation_and_deletes_nothing(self):
        appendix = self.make_appendix(self.pub, name='confirm-me.txt')
        self.login(self.dtu_own)
        response = self.client.get(self.path(appendix))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'publications/appendix_confirm_delete.html')
        self.assertContains(response, 'confirm-me.txt')
        self.assertContains(response, '99-01')
        self.assertContains(response, 'Own report')
        self.assertContains(response, 'cannot be undone')
        self.assertContains(response, 'method="post"')
        self.assertKept(appendix)

    def test_appendix_of_another_report_is_404(self):
        other = self.make_appendix(self.other_pub, name='other.txt')
        self.login(self.editor)
        self.assertEqual(self.client.get(self.path(other, self.pub)).status_code, 404)
        self.assertEqual(self.post_delete(other, self.pub).status_code, 404)
        self.assertKept(other, self.other_pub)

    def test_unknown_file_or_report_is_404(self):
        appendix = self.make_appendix(self.pub)
        self.login(self.editor)
        self.assertEqual(self.client.get(
            page_path('delete_appendix', pk=self.pub.pk, file_pk=appendix.pk + 999)).status_code, 404)
        self.assertEqual(self.client.get(
            page_path('delete_appendix', pk=self.pub.pk + 999, file_pk=appendix.pk)).status_code, 404)
        self.assertKept(appendix)

    def test_other_methods_not_allowed(self):
        appendix = self.make_appendix(self.pub)
        self.login(self.editor)
        self.assertEqual(self.client.delete(self.path(appendix)).status_code, 405)
        self.assertKept(appendix)


class AppendixDeleteRulesTests(AppendixDeleteTestBase):

    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def test_report_unchanged_otherwise(self):
        deleted = self.make_appendix(self.pub, name='gone.txt')
        kept = self.make_appendix(self.pub, name='stays.txt')
        before = Publication.objects.filter(pk=self.pub.pk).values().get()
        self.post_delete(deleted)
        self.assertGone(deleted)
        self.assertKept(kept)
        self.assertEqual(Publication.objects.filter(pk=self.pub.pk).values().get(), before)
        self.assertEqual(list(self.pub.authors.all()), [self.student])

    def test_file_shared_with_a_feature_is_unlinked_but_kept(self):
        appendix = self.make_appendix(self.pub, name='feature-file.txt')
        feature = Feature.objects.create(name='F', date='1999-07-01')
        feature.files.add(appendix)
        self.post_delete(appendix)
        self.assertFalse(Appendenciesship.objects.filter(fileobject=appendix).exists())
        self.assertTrue(FileObject.objects.filter(pk=appendix.pk).exists())
        self.assertTrue(os.path.exists(self.full_path(appendix)))
        self.assertEqual(list(feature.files.all()), [appendix])

    def test_file_that_is_also_appendix_of_another_report_is_kept(self):
        appendix = self.make_appendix(self.pub, name='two-reports.txt')
        Appendenciesship.objects.create(publication=self.other_pub, fileobject=appendix)
        self.post_delete(appendix)
        self.assertFalse(Appendenciesship.objects.filter(
            publication=self.pub, fileobject=appendix).exists())
        self.assertKept(appendix, self.other_pub)

    def test_file_name_used_by_another_record_stays_on_disk(self):
        appendix = self.make_appendix(self.pub, name='same-name.txt')
        twin = FileObject.objects.create(file=appendix.file.name)
        self.post_delete(appendix)
        self.assertFalse(FileObject.objects.filter(pk=appendix.pk).exists())
        self.assertTrue(FileObject.objects.filter(pk=twin.pk).exists())
        self.assertTrue(os.path.exists(self.full_path(twin)))

    def test_missing_file_on_disk_still_deletes_the_record(self):
        appendix = self.make_appendix(self.pub, name='never-written.txt', write=False)
        with self.assertLogs('publications.views', level='WARNING') as logs:
            response = self.post_delete(appendix)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(FileObject.objects.filter(pk=appendix.pk).exists())
        self.assertFalse(Appendenciesship.objects.filter(fileobject=appendix).exists())
        self.assertIn('already missing', '\n'.join(logs.output))


class AppendixDeleteButtonTests(AppendixDeleteTestBase):

    def test_button_only_for_users_who_may_edit(self):
        appendix = self.make_appendix(self.pub, name='button.txt')
        # The report is unverified: anonymous users can't open it, so make it public.
        Publication.objects.filter(pk=self.pub.pk).update(verified=True)
        delete_url = self.path(appendix)
        report = page_path('report', pk=self.pub.pk)

        response = self.client.get(report)
        self.assertContains(response, 'button.txt')
        self.assertNotContains(response, delete_url)
        for user in (self.dtu_not_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                response = self.client.get(report)
                self.assertContains(response, 'button.txt')
                self.assertNotContains(response, delete_url)
        for user in (self.dtu_own, self.staff_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertContains(self.client.get(report), delete_url)
