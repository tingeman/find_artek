"""Files and images on features (plan "features" T8, roadmap FA-R64).

- UploadFeatureMediaView (``edit_feature``: Feature.is_editable_by): files go to
  ``reports/<year>/<number>/features/<feature id>/``, images to ``.../img/`` of the report the
  upload starts from (``report``; else the feature's first visible report; refused without
  one). The storage never overwrites a file of the same name. Images get a JPEG thumbnail
  ``.../img/thumbs/<file name>_thumb.jpg``. Same limit per file as appendices.
- DeleteFeatureMediaView (``edit_feature``): GET confirmation page, POST unlinks the record
  from the feature; record, file and thumbnail go only when nothing else uses them (after the
  commit).
- Media access (publications.media_access): the uploaded files and thumbnails have the
  feature's visibility; nothing is widened.
- Feature page: list of files and images (thumbnails), upload and delete links only for
  users with ``edit_feature``.

Users from ReportAccessTestBase (roles of migration 0003): author ``dtu_own`` of ``pub``
(unvalidated), ``dtu_not_own`` not listed, artek_editor ``editor``. Every file is a tiny
fixture generated here (Pillow for images) in a temporary MEDIA_ROOT; never real media.
"""
import datetime
import io
import os
import shutil
import tempfile

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from publications.media_access import MediaIndex, RESTRICTED, PUBLIC, can_access_media
from publications.models import Feature, FileObject, ImageObject, ImageObjectship, Publication
from publications.test_factories import make_report, page_path
from publications.test_media_access import ACCEL_PREFIX, media_path
from publications.test_report_access import ReportAccessTestBase


def png_bytes(size=(600, 300), color=(200, 30, 30)):
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, 'PNG')
    return buffer.getvalue()


def text_upload(name='data.txt', content=b'made-up feature data\n'):
    return SimpleUploadedFile(name, content, content_type='text/plain')


def png_upload(name='photo.png', **kwargs):
    return SimpleUploadedFile(name, png_bytes(**kwargs), content_type='image/png')


def feature_url(feature, report):
    """The feature page with ``?report=`` as the views link and redirect to it (reverse(),
    with FORCE_SCRIPT_NAME under the production settings)."""
    return reverse('publications:feature', kwargs={'pk': feature.pk}) + f'?report={report.pk}'


class FeatureMediaTestBase(ReportAccessTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_pub = Publication.objects.create(
            type=cls.pubtype, title='Other report', number='99-02', year=1999, verified=True)

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='find_artek_feature_media_')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

    def feature(self, name, *pubs):
        feature = Feature.objects.create(name=name, date=datetime.date(1999, 7, 1))
        feature.publications.add(*pubs)
        return feature

    def full(self, relpath):
        return os.path.join(self.media_root, *str(relpath).split('/'))

    def feature_dir(self, feature, number='99-01'):
        return f'reports/1999/{number}/features/{feature.pk}'

    def upload_path(self, feature, report=None):
        url = page_path('upload_feature_media', pk=feature.pk)
        return f'{url}?report={report.pk}' if report else url

    def upload(self, feature, kind, files, report=None, text=''):
        field, text_field = (('feature_images', 'caption') if kind == 'image'
                             else ('feature_files', 'description'))
        data = {'kind': kind, field: files, text_field: text}
        if report is not None:
            data['report'] = report.pk
        return self.client.post(page_path('upload_feature_media', pk=feature.pk), data)

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class UploadFeatureMediaTests(FeatureMediaTestBase):

    def test_file_is_stored_under_the_report_folder_of_the_feature(self):
        feature = self.feature('Borehole', self.pub)
        self.login(self.dtu_own)
        response = self.upload(feature, 'file', [text_upload()], self.pub, 'Log sheet')
        self.assertRedirects(response, feature_url(feature, self.pub),
                             fetch_redirect_response=False)
        fileobject = feature.files.get()
        self.assertEqual(fileobject.file.name, f'{self.feature_dir(feature)}/data.txt')
        self.assertEqual(fileobject.description, 'Log sheet')
        self.assertEqual(fileobject.created_by, self.dtu_own)
        with open(self.full(fileobject.file.name), 'rb') as f:
            self.assertEqual(f.read(), b'made-up feature data\n')

    def test_image_is_stored_in_img_with_a_thumbnail(self):
        feature = self.feature('Photo point', self.pub)
        self.login(self.editor)
        response = self.upload(feature, 'image', [png_upload()], self.pub, 'View north')
        self.assertEqual(response.status_code, 302)
        image = feature.images.get()
        self.assertTrue(ImageObjectship.objects.filter(feature=feature, imageobject=image).exists())
        self.assertEqual(image.image.name, f'{self.feature_dir(feature)}/img/photo.png')
        self.assertEqual(image.caption, 'View north')
        self.assertTrue(os.path.isfile(self.full(image.image.name)))
        thumbnail = self.full(f'{self.feature_dir(feature)}/img/thumbs/photo.png_thumb.jpg')
        self.assertTrue(os.path.isfile(thumbnail))
        with Image.open(thumbnail) as thumb:
            self.assertEqual(thumb.format, 'JPEG')
            self.assertLessEqual(max(thumb.size), 400)
            self.assertEqual(thumb.size, (400, 200))   # aspect ratio kept

    def test_several_files_in_one_upload(self):
        feature = self.feature('Samples', self.pub)
        self.login(self.editor)
        self.upload(feature, 'file', [text_upload('a.txt'), text_upload('b.csv')], self.pub)
        self.assertEqual(sorted(f.filename() for f in feature.files.all()), ['a.txt', 'b.csv'])

    def test_same_name_does_not_overwrite_the_existing_file(self):
        feature = self.feature('Twice', self.pub)
        self.login(self.editor)
        self.upload(feature, 'file', [text_upload(content=b'first\n')], self.pub)
        self.upload(feature, 'file', [text_upload(content=b'second\n')], self.pub)
        first, second = feature.files.order_by('pk')
        self.assertNotEqual(first.file.name, second.file.name)
        self.assertTrue(second.file.name.startswith(f'{self.feature_dir(feature)}/data'))
        with open(self.full(first.file.name), 'rb') as f:
            self.assertEqual(f.read(), b'first\n')
        with open(self.full(second.file.name), 'rb') as f:
            self.assertEqual(f.read(), b'second\n')

    def test_without_report_the_first_visible_report_is_used(self):
        feature = self.feature('Two reports', self.other_pub, self.pub)
        self.login(self.editor)
        self.upload(feature, 'file', [text_upload()])
        # Reports ordered by number: 99-01 before 99-02.
        self.assertEqual(feature.files.get().file.name, f'{self.feature_dir(feature)}/data.txt')

    def test_report_param_chooses_the_folder(self):
        feature = self.feature('Two reports', self.pub, self.other_pub)
        self.login(self.editor)
        self.upload(feature, 'file', [text_upload()], self.other_pub)
        self.assertEqual(feature.files.get().file.name,
                         f'{self.feature_dir(feature, "99-02")}/data.txt')

    def test_report_not_of_the_feature_is_ignored(self):
        feature = self.feature('One report', self.pub)
        self.login(self.editor)
        self.upload(feature, 'file', [text_upload()], self.other_pub)
        self.assertEqual(feature.files.get().file.name, f'{self.feature_dir(feature)}/data.txt')

    def test_feature_without_report_gets_no_upload(self):
        feature = self.feature('Orphan')
        self.login(self.editor)
        page = self.client.get(self.upload_path(feature))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="feature-upload-refused"')
        self.assertNotContains(page, 'id="feature-file-upload-form"')
        response = self.upload(feature, 'file', [text_upload()])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FileObject.objects.exists())
        self.assertFalse(os.path.exists(self.full('reports')))

    def test_report_without_number_gets_no_upload(self):
        report = make_report(self.pubtype, '', verified=True, confidential=False)
        feature = self.feature('No number', report)
        self.login(self.editor)
        response = self.upload(feature, 'file', [text_upload()], report)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FileObject.objects.exists())

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_oversize_file_is_refused(self):
        feature = self.feature('Big', self.pub)
        self.login(self.editor)
        big = text_upload('big.txt', b'x' * (1024 * 1024 + 1))
        response = self.upload(feature, 'file', [big], self.pub)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Maximum file size is 1 MB per file', status_code=400)
        self.assertFalse(FileObject.objects.exists())
        self.assertFalse(os.path.exists(self.full(self.feature_dir(feature))))

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_file_of_exactly_the_limit_is_accepted(self):
        feature = self.feature('Limit', self.pub)
        self.login(self.editor)
        response = self.upload(feature, 'file', [text_upload('ok.txt', b'x' * 1024 * 1024)],
                               self.pub)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(feature.files.count(), 1)

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_oversize_image_is_refused(self):
        feature = self.feature('Big image', self.pub)
        self.login(self.editor)
        big = SimpleUploadedFile('big.png', png_bytes() + b'\0' * (1024 * 1024),
                                 content_type='image/png')
        response = self.upload(feature, 'image', [big], self.pub)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Maximum file size is 1 MB per file', status_code=400)
        self.assertFalse(ImageObject.objects.exists())

    def test_unsupported_file_type_is_refused(self):
        # T8a: any type except active content (test_feature_file_types has the details).
        feature = self.feature('Web page', self.pub)
        self.login(self.editor)
        response = self.upload(feature, 'file', [text_upload('page.html')], self.pub)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FileObject.objects.exists())

    def test_non_image_is_refused_as_image(self):
        feature = self.feature('Fake image', self.pub)
        self.login(self.editor)
        fake = SimpleUploadedFile('photo.png', b'not an image', content_type='image/png')
        response = self.upload(feature, 'image', [fake], self.pub)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ImageObject.objects.exists())
        self.assertFalse(os.path.exists(self.full(self.feature_dir(feature))))

    def test_page_has_the_limit_and_the_submit_guard(self):
        feature = self.feature('Page', self.pub)
        self.login(self.dtu_own)
        with self.settings(MAX_UPLOAD_SIZE_MB=7):
            response = self.client.get(self.upload_path(feature, self.pub))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'publications/js/submit-guard.js')
        self.assertContains(response, 'data-submit-guard=', count=2)
        self.assertContains(response, 'data-max-size-mb="7"', count=2)
        self.assertContains(response, f'name="report" value="{self.pub.pk}"', count=2)


class UploadFeatureMediaAccessTests(FeatureMediaTestBase):

    def test_anonymous_is_sent_to_login_and_nothing_is_stored(self):
        feature = self.feature('Feature', self.pub)
        for response in (self.client.get(self.upload_path(feature)),
                         self.upload(feature, 'file', [text_upload()], self.pub)):
            self.assertRedirectsToLogin(response)
        self.assertFalse(FileObject.objects.exists())

    def test_dtu_user_not_listed_is_denied(self):
        feature = self.feature('Feature', self.pub)
        self.login(self.dtu_not_own)
        self.assertDenied(self.client.get(self.upload_path(feature)))
        self.assertDenied(self.upload(feature, 'file', [text_upload()], self.pub))
        self.assertDenied(self.upload(feature, 'image', [png_upload()], self.pub))
        self.assertFalse(FileObject.objects.exists())
        self.assertFalse(ImageObject.objects.exists())

    def test_listed_dtu_user_and_editor_may_upload(self):
        for user in (self.dtu_own, self.editor):
            with self.subTest(user=user.username):
                feature = self.feature(f'Feature {user.username}', self.pub)
                self.login(user)
                self.assertEqual(self.client.get(self.upload_path(feature)).status_code, 200)
                self.assertEqual(self.upload(feature, 'file', [text_upload()]).status_code, 302)
                self.assertEqual(feature.files.count(), 1)

    def test_unknown_feature_is_404(self):
        self.login(self.editor)
        response = self.client.get(page_path('upload_feature_media', pk=999999))
        self.assertEqual(response.status_code, 404)


class DeleteFeatureMediaTests(FeatureMediaTestBase):

    def uploaded(self, feature, kind, upload):
        self.login(self.editor)
        self.upload(feature, kind, [upload], self.pub)
        return (feature.images if kind == 'image' else feature.files).get()

    def delete_path(self, feature, kind, record):
        return page_path(f'delete_feature_{kind}', pk=feature.pk, record_pk=record.pk)

    def post_delete(self, feature, kind, record):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.delete_path(feature, kind, record),
                                    {'report': self.pub.pk})

    def test_get_is_a_confirmation_page_and_changes_nothing(self):
        feature = self.feature('Feature', self.pub)
        fileobject = self.uploaded(feature, 'file', text_upload())
        response = self.client.get(self.delete_path(feature, 'file', fileobject))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data.txt')
        self.assertContains(response, 'id="feature-media-deleted"')
        self.assertTrue(feature.files.filter(pk=fileobject.pk).exists())
        self.assertTrue(os.path.isfile(self.full(fileobject.file.name)))

    def test_delete_file_removes_record_and_file(self):
        feature = self.feature('Feature', self.pub)
        fileobject = self.uploaded(feature, 'file', text_upload())
        response = self.post_delete(feature, 'file', fileobject)
        self.assertRedirects(response, feature_url(feature, self.pub),
                             fetch_redirect_response=False)
        self.assertFalse(FileObject.objects.filter(pk=fileobject.pk).exists())
        self.assertFalse(os.path.exists(self.full(fileobject.file.name)))

    def test_delete_image_removes_record_file_and_thumbnail(self):
        feature = self.feature('Feature', self.pub)
        image = self.uploaded(feature, 'image', png_upload())
        thumbnail = self.full(f'{self.feature_dir(feature)}/img/thumbs/photo.png_thumb.jpg')
        self.assertTrue(os.path.isfile(thumbnail))
        self.post_delete(feature, 'image', image)
        self.assertFalse(ImageObject.objects.filter(pk=image.pk).exists())
        self.assertFalse(ImageObjectship.objects.filter(imageobject_id=image.pk).exists())
        self.assertFalse(os.path.exists(self.full(image.image.name)))
        self.assertFalse(os.path.exists(thumbnail))

    def test_file_shared_with_another_feature_is_only_unlinked(self):
        feature = self.feature('Feature', self.pub)
        other = self.feature('Other', self.pub)
        fileobject = self.uploaded(feature, 'file', text_upload())
        other.files.add(fileobject)
        page = self.client.get(self.delete_path(feature, 'file', fileobject))
        self.assertContains(page, 'id="feature-media-kept"')
        self.post_delete(feature, 'file', fileobject)
        self.assertFalse(feature.files.filter(pk=fileobject.pk).exists())
        self.assertTrue(other.files.filter(pk=fileobject.pk).exists())
        self.assertTrue(os.path.isfile(self.full(fileobject.file.name)))

    def test_image_shared_with_another_feature_is_only_unlinked(self):
        feature = self.feature('Feature', self.pub)
        other = self.feature('Other', self.pub)
        image = self.uploaded(feature, 'image', png_upload())
        ImageObjectship.objects.create(imageobject=image, feature=other)
        self.post_delete(feature, 'image', image)
        self.assertFalse(feature.images.filter(pk=image.pk).exists())
        self.assertTrue(other.images.filter(pk=image.pk).exists())
        self.assertTrue(os.path.isfile(self.full(image.image.name)))
        self.assertTrue(os.path.isfile(
            self.full(f'{self.feature_dir(feature)}/img/thumbs/photo.png_thumb.jpg')))

    def test_file_also_used_as_appendix_is_only_unlinked(self):
        feature = self.feature('Feature', self.pub)
        fileobject = self.uploaded(feature, 'file', text_upload())
        self.pub.appendices.add(fileobject)
        self.post_delete(feature, 'file', fileobject)
        self.assertTrue(FileObject.objects.filter(pk=fileobject.pk).exists())
        self.assertTrue(os.path.isfile(self.full(fileobject.file.name)))

    def test_access(self):
        feature = self.feature('Feature', self.pub)
        fileobject = self.uploaded(feature, 'file', text_upload())
        image = self.uploaded(feature, 'image', png_upload())
        self.client.logout()
        for kind, record in (('file', fileobject), ('image', image)):
            with self.subTest(kind=kind, user='anonymous'):
                self.assertRedirectsToLogin(self.client.get(self.delete_path(feature, kind, record)))
                self.assertRedirectsToLogin(self.client.post(self.delete_path(feature, kind, record)))
        self.login(self.dtu_not_own)
        for kind, record in (('file', fileobject), ('image', image)):
            with self.subTest(kind=kind, user='dtu_not_own'):
                self.assertDenied(self.client.get(self.delete_path(feature, kind, record)))
                self.assertDenied(self.client.post(self.delete_path(feature, kind, record)))
        self.assertTrue(feature.files.filter(pk=fileobject.pk).exists())
        self.assertTrue(feature.images.filter(pk=image.pk).exists())
        self.login(self.dtu_own)
        for kind, record in (('file', fileobject), ('image', image)):
            with self.subTest(kind=kind, user='dtu_own'):
                self.assertEqual(self.client.get(
                    self.delete_path(feature, kind, record)).status_code, 200)
                self.assertEqual(self.post_delete(feature, kind, record).status_code, 302)
        self.assertFalse(feature.files.exists())
        self.assertFalse(feature.images.exists())

    def test_record_of_another_feature_is_404(self):
        feature = self.feature('Feature', self.pub)
        other = self.feature('Other', self.pub)
        fileobject = self.uploaded(other, 'file', text_upload())
        image = self.uploaded(other, 'image', png_upload())
        for kind, record in (('file', fileobject), ('image', image)):
            with self.subTest(kind=kind):
                self.assertEqual(self.client.get(
                    self.delete_path(feature, kind, record)).status_code, 404)
                self.assertEqual(self.client.post(
                    self.delete_path(feature, kind, record)).status_code, 404)
        self.assertTrue(other.files.filter(pk=fileobject.pk).exists())
        self.assertTrue(other.images.filter(pk=image.pk).exists())

    def test_unknown_feature_is_404(self):
        self.login(self.editor)
        response = self.client.get(page_path('delete_feature_file', pk=999999, record_pk=1))
        self.assertEqual(response.status_code, 404)


class FeatureMediaAccessTests(FeatureMediaTestBase):
    """Uploaded files and thumbnails through the checked media view."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.confidential = make_report(cls.pubtype, '99-03', verified=True, confidential=True,
                                       authors=[cls.student])
        cls.public = make_report(cls.pubtype, '99-04', verified=True, confidential=False)

    def upload_both(self, feature, report):
        self.login(self.editor)
        self.upload(feature, 'file', [text_upload()], report)
        self.upload(feature, 'image', [png_upload()], report)
        self.client.logout()
        image = feature.images.get()
        thumbnail = image.image.name.replace('img/photo.png', 'img/thumbs/photo.png_thumb.jpg')
        self.assertTrue(os.path.isfile(self.full(thumbnail)))
        return [feature.files.get().file.name, image.image.name, thumbnail]

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX=ACCEL_PREFIX)
    def test_feature_of_a_confidential_report(self):
        feature = self.feature('Hidden', self.confidential)
        names = self.upload_both(feature, self.confidential)
        for name in names:
            with self.subTest(name=name, user='anonymous'):
                response = self.client.get(media_path(name))
                self.assertEqual(response.status_code, 404)
                self.assertFalse(response.has_header('X-Accel-Redirect'))
        for user in (self.dtu_not_own,):
            self.client.force_login(user)
            for name in names:
                with self.subTest(name=name, user=user.username):
                    self.assertEqual(self.client.get(media_path(name)).status_code, 404)
        for user in (self.dtu_own, self.editor):   # author of the report, editor
            self.client.force_login(user)
            for name in names:
                with self.subTest(name=name, user=user.username):
                    response = self.client.get(media_path(name))
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response['X-Accel-Redirect'], ACCEL_PREFIX + name)
                    self.assertEqual(response['Cache-Control'], 'private, no-store')

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX=ACCEL_PREFIX)
    def test_feature_of_a_public_report_is_public(self):
        feature = self.feature('Public', self.public)
        for name in self.upload_both(feature, self.public):
            with self.subTest(name=name):
                response = self.client.get(media_path(name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['X-Accel-Redirect'], ACCEL_PREFIX + name)

    def test_index_agrees_with_the_view_for_thumbnails(self):
        hidden = self.feature('Hidden', self.confidential)
        public = self.feature('Public', self.public)
        hidden_names = self.upload_both(hidden, self.confidential)
        public_names = self.upload_both(public, self.public)
        index = MediaIndex()
        self.assertEqual(index.classify(hidden_names[2]), ('thumbnail', RESTRICTED))
        self.assertEqual(index.classify(public_names[2]), ('thumbnail', PUBLIC))
        self.assertEqual(can_access_media(None, hidden_names[2]), (False, False))
        self.assertEqual(can_access_media(None, public_names[2]), (True, True))

    def test_thumbnail_of_an_unknown_image_is_editors_only(self):
        name = 'reports/1999/99-04/features/1/img/thumbs/nothing.png_thumb.jpg'
        self.assertEqual(MediaIndex().classify(name), ('unowned', 'editors_only'))
        self.assertEqual(can_access_media(self.dtu_own, name), (False, False))


class FeaturePageMediaTests(FeatureMediaTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.public = make_report(cls.pubtype, '99-04', verified=True, confidential=False,
                                 authors=[cls.student])

    def test_lists_files_and_images_with_thumbnail(self):
        feature = self.feature('Listed', self.public)
        self.login(self.editor)
        self.upload(feature, 'file', [text_upload()], self.public, 'Log sheet')
        self.upload(feature, 'image', [png_upload()], self.public, 'View north')
        self.client.logout()
        image = feature.images.get()
        response = self.client.get(page_path('feature', pk=feature.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data.txt')
        self.assertContains(response, 'Log sheet')
        self.assertContains(response, f'href="{image.image.url}"')
        self.assertContains(response, 'photo.png_thumb.jpg')
        self.assertContains(response, 'View north')
        # Anonymous users may see the feature but not change it.
        self.assertNotContains(response, 'id="feature-upload-link"')
        self.assertNotContains(response, 'feature-media-delete')

    def test_upload_and_delete_links_only_with_edit_feature(self):
        feature = self.feature('Links', self.public)
        feature.files.add(FileObject.objects.create(file='reports/1999/99-04/x.txt'))
        cases = ((self.dtu_not_own, False), (self.dtu_own, True), (self.editor, True))
        for user, allowed in cases:
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(
                    page_path('feature', pk=feature.pk) + f'?report={self.public.pk}')
                self.assertEqual(response.status_code, 200)
                if allowed:
                    upload = reverse('publications:upload_feature_media', kwargs={'pk': feature.pk})
                    self.assertContains(response, f'href="{upload}?report={self.public.pk}"')
                    self.assertContains(response, 'feature-media-delete')
                else:
                    self.assertNotContains(response, 'id="feature-upload-link"')
                    self.assertNotContains(response, 'feature-media-delete')

    def test_report_param_of_a_hidden_report_is_not_passed_on(self):
        hidden = make_report(self.pubtype, '99-05', verified=True, confidential=True)
        feature = self.feature('Mixed', self.public, hidden)
        self.client.force_login(self.dtu_own)
        response = self.client.get(page_path('feature', pk=feature.pk) + f'?report={hidden.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'?report={hidden.pk}')

    def test_report_page_links_features_with_the_report(self):
        feature = self.feature('Linked', self.public)
        response = self.client.get(page_path('report', pk=self.public.pk))
        self.assertContains(
            response, f'href="{feature_url(feature, self.public)}"')
