"""Access control of the appendix upload view (roadmap FA-R52).

The view must not be usable without a login, nor by a logged-in user who may not edit the
publication. No file is written by these tests: uploads are kept in the session until
"submit", and the denied requests never get that far.
"""
import os

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from publications.models import Appendenciesship, FileObject, Publication, PubType


class UploadAppendixAccessTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')
        cls.publication = Publication.objects.create(
            type=pubtype, title='Test report', number='99-01', year=1999, verified=True)
        cls.url = reverse('publications:upload_appendix', kwargs={'pk': cls.publication.pk})
        cls.plain_user = User.objects.create_user('s990001', password='x')
        cls.editor = User.objects.create_user('editor', password='x')
        cls.editor.user_permissions.add(
            Permission.objects.get(codename='change_publication',
                                   content_type__app_label='publications'))

    def _upload(self):
        return self.client.post(self.url, {
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
        self.assertTrue(response['Location'].startswith('/login?next='), response['Location'])

    def test_anonymous_get_redirects_to_login(self):
        self.assertRedirectsToLogin(self.client.get(self.url))

    def test_anonymous_upload_redirects_to_login_and_stores_nothing(self):
        self.assertRedirectsToLogin(self._upload())
        self.assertNothingStored()

    def test_anonymous_submit_redirects_to_login(self):
        self.assertRedirectsToLogin(self.client.post(self.url, {'action': 'submit'}))
        self.assertNothingStored()

    def test_user_without_edit_permission_is_denied(self):
        self.client.force_login(self.plain_user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self._upload().status_code, 403)
        self.assertEqual(self.client.post(self.url, {'action': 'submit'}).status_code, 403)
        self.assertNothingStored()

    def test_unknown_publication_is_404_for_logged_in_user(self):
        self.client.force_login(self.editor)
        url = reverse('publications:upload_appendix', kwargs={'pk': self.publication.pk + 1000})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_editor_can_open_page_and_add_file_to_session(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.addCleanup(self._remove_temp_files)
        response = self._upload()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], self.url)
        self.assertEqual([f['filename'] for f in self._session_files()], ['appendix.txt'])
