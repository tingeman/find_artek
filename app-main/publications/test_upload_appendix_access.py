"""Access control of the appendix upload view (roadmap FA-R52).

The view must not be usable without a login, nor by a logged-in user who may not edit the
publication. No file is written by these tests: uploads are kept in the session until
"submit", and the denied requests never get that far.
"""
import os
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import get_script_prefix, reverse

from publications.models import Appendenciesship, FileObject, Publication, PubType


def _app_path(url):
    """The path the test client must request for a reversed URL.

    With FORCE_SCRIPT_NAME ('/find' in the production settings the release gate uses),
    reverse() includes the prefix, but the test client sends its path as PATH_INFO, so the
    prefix has to be removed. Without a prefix (development settings) the URL is unchanged.
    """
    prefix = get_script_prefix()
    return '/' + url[len(prefix):] if url.startswith(prefix) else url


class UploadAppendixAccessTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')
        cls.publication = Publication.objects.create(
            type=pubtype, title='Test report', number='99-01', year=1999, verified=True)
        cls.url = reverse('publications:upload_appendix', kwargs={'pk': cls.publication.pk})
        cls.path = _app_path(cls.url)
        cls.plain_user = User.objects.create_user('s990001', password='x')
        cls.editor = User.objects.create_user('editor', password='x')
        cls.editor.user_permissions.add(
            Permission.objects.get(codename='change_publication',
                                   content_type__app_label='publications'))

    def _upload(self):
        return self.client.post(self.path, {
            'action': 'upload',
            'appendix_files': SimpleUploadedFile('appendix.txt', b'test', content_type='text/plain'),
        })

    def _session_files(self):
        return self.client.session.get(f'appendix_upload_{self.publication.pk}', [])

    def _remove_temp_files(self):
        for info in self._session_files():
            if os.path.exists(info['temp_path']):
                os.unlink(info['temp_path'])

    def assertNothingStored(self):
        self.assertEqual(self._session_files(), [])
        self.assertEqual(FileObject.objects.count(), 0)
        self.assertEqual(Appendenciesship.objects.count(), 0)

    def assertRedirectsToLogin(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(resolve_url(settings.LOGIN_URL) + '?next='),
                        response['Location'])

    def test_anonymous_get_redirects_to_login(self):
        self.assertRedirectsToLogin(self.client.get(self.path))

    def test_anonymous_upload_redirects_to_login_and_stores_nothing(self):
        self.assertRedirectsToLogin(self._upload())
        self.assertNothingStored()

    def test_anonymous_submit_redirects_to_login(self):
        self.assertRedirectsToLogin(self.client.post(self.path, {'action': 'submit'}))
        self.assertNothingStored()

    def test_user_without_edit_permission_is_denied(self):
        self.client.force_login(self.plain_user)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self._upload().status_code, 403)
        self.assertEqual(self.client.post(self.path, {'action': 'submit'}).status_code, 403)
        self.assertNothingStored()

    def test_unknown_publication_is_404_for_logged_in_user(self):
        self.client.force_login(self.editor)
        url = reverse('publications:upload_appendix', kwargs={'pk': self.publication.pk + 1000})
        self.assertEqual(self.client.get(_app_path(url)).status_code, 404)

    def test_editor_can_open_page_and_add_file_to_session(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(self.path).status_code, 200)
        self.addCleanup(self._remove_temp_files)
        response = self._upload()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], self.url)
        self.assertEqual([f['filename'] for f in self._session_files()], ['appendix.txt'])

    def test_submit_records_the_uploading_user_on_the_appendix(self):
        """The appendix FileObject gets created_by/modified_by (FA-R68). MEDIA_ROOT is a
        temporary directory, so no file lands in the real media folder."""
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        self.client.force_login(self.editor)
        self.addCleanup(self._remove_temp_files)
        self._upload()
        with override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(self.path, {'action': 'submit'})
        self.assertRedirects(
            response, reverse('publications:report', kwargs={'pk': self.publication.pk}),
            fetch_redirect_response=False)
        appendix = Appendenciesship.objects.get(publication=self.publication).fileobject
        self.assertEqual(appendix.created_by, self.editor)
        self.assertEqual(appendix.modified_by, self.editor)
        self.assertTrue(appendix.file.name.startswith('reports/1999/99-01/'))
