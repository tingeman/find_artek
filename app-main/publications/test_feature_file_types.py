"""Any file type on features, safe download headers on media (plan "features" T8a).

- Feature files: any extension except the block-list of active content
  (forms.feature.FEATURE_FILE_BLOCKED_EXTENSIONS); only the last extension counts, case does not
  matter, files without extension are accepted. The upload page lists the blocked types and
  says they can go inside a zip archive; the file input does not restrict types.
- Feature images: raster types Pillow thumbnails, including WebP.
- Media responses (views_media.serve_media), for all media: ``X-Content-Type-Options: nosniff``
  always; PDF, plain text and raster images inline with their type; everything else as
  ``application/octet-stream`` with ``Content-Disposition: attachment``. Both with
  X-Accel-Redirect (production) and streamed (development). Who may see what is unchanged.

Every file is a tiny fixture generated here in a temporary MEDIA_ROOT; never real media.
"""
import io
import re
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image, features as pil_features

from publications.forms.feature import (
    FEATURE_FILE_BLOCKED_EXTENSIONS, FEATURE_IMAGE_EXTENSIONS, check_feature_file,
    upload_extension,
)
from publications.models import Feature, FileObject
from publications.test_feature_media import FeatureMediaTestBase, text_upload
from publications.test_media_access import (
    ACCEL_PREFIX, C, P, MediaFixtureMixin, media_path,
)
from publications.views_media import media_headers

EXPECTED_BLOCKED = {'.html', '.htm', '.xhtml', '.xht', '.shtml', '.mht', '.mhtml', '.svg',
                    '.svgz', '.js', '.mjs', '.hta', '.swf'}
OCTET = 'application/octet-stream'
NOSNIFF = 'nosniff'


def upload(name, size=10):
    return SimpleUploadedFile(name, b'x' * size, content_type='application/octet-stream')


class FeatureFileTypeCheckTests(SimpleTestCase):

    def test_block_list(self):
        self.assertEqual(FEATURE_FILE_BLOCKED_EXTENSIONS, EXPECTED_BLOCKED)

    def test_blocked_names_are_refused(self):
        for name in ('page.html', 'PAGE.HTML', 'a.Htm', 'figure.svg', 'figure.SVGZ', 'x.zip.svg',
                     'app.js', 'mod.MJS', 'x.xhtml', 'x.xht', 'x.shtml', 'a.hta', 'old.swf',
                     'saved.mhtml', 'saved.mht', 'figure.svg.', 'figure.svg ', 'a.b.c.html'):
            with self.subTest(name=name):
                with self.assertRaises(ValidationError) as cm:
                    check_feature_file(upload(name))
                message = ' '.join(cm.exception.messages)
                self.assertIn('blocked file type', message)
                self.assertIn('.svg', message)
                self.assertIn('.zip archive', message)

    def test_other_names_are_accepted(self):
        for name in ('figure.svg.zip', 'x.html.zip', 'data.dat', 'scan.las', 'logger.XML',
                     'style.xsl', 'style.xslt', 'tool.exe', 'notes.txt', 'report.pdf',
                     'archive.zip', 'README', '.hidden', 'grid.tif', 'data.json',
                     'målinger.csv'):
            with self.subTest(name=name):
                check_feature_file(upload(name))   # no ValidationError

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_size_limit_unchanged(self):
        check_feature_file(upload('ok.dat', 1024 * 1024))
        with self.assertRaisesMessage(ValidationError, 'Maximum file size is 1 MB per file'):
            check_feature_file(upload('big.dat', 1024 * 1024 + 1))

    def test_upload_extension(self):
        self.assertEqual(upload_extension('x.SVG. '), '.svg')
        self.assertEqual(upload_extension('x.svg.zip'), '.zip')
        self.assertEqual(upload_extension('README'), '')
        self.assertEqual(upload_extension('dir.html/file'), '')

    def test_image_types_include_webp_and_pillow_supports_it(self):
        self.assertEqual(FEATURE_IMAGE_EXTENSIONS,
                         {'.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.webp'})
        # WebP is on the list because Pillow in the image is built with it.
        self.assertTrue(pil_features.check('webp'))


class FeatureFileUploadTests(FeatureMediaTestBase):

    def test_unusual_types_are_stored(self):
        feature = self.feature('Instruments', self.pub)
        self.login(self.editor)
        names = ['scan.las', 'logger.dat', 'export.xml', 'figure.svg.zip', 'RAWDUMP']
        response = self.upload(feature, 'file', [text_upload(n) for n in names], self.pub)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            sorted(f.file.name.rsplit('/', 1)[1] for f in feature.files.all()), sorted(names))

    def test_blocked_type_is_refused_with_the_zip_hint(self):
        feature = self.feature('Figures', self.pub)
        self.login(self.editor)
        response = self.upload(feature, 'file', [text_upload('ok.dat'), text_upload('fig.SVG')],
                               self.pub)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'is of a blocked file type', status_code=400)
        self.assertContains(response, 'inside a .zip archive', status_code=400)
        self.assertFalse(FileObject.objects.exists())   # nothing of the upload is stored

    def test_page_lists_blocked_types_and_zip_hint_and_does_not_restrict_types(self):
        feature = self.feature('Page', self.pub)
        self.login(self.dtu_own)
        response = self.client.get(self.upload_path(feature, self.pub))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        types_text = re.search(r'id="feature-file-types">(.*?)</p>', content, re.S).group(1)
        for ext in EXPECTED_BLOCKED:
            self.assertIn(ext, types_text)
        self.assertIn('inside a .zip archive', types_text)
        file_input = re.search(r'<input[^>]*name="feature_files"[^>]*>', content).group(0)
        self.assertNotIn('accept', file_input)
        image_text = re.search(r'id="feature-image-types">(.*?)</p>', content, re.S).group(1)
        self.assertIn('WebP', image_text)
        self.assertIn('Other formats can be uploaded as files', image_text)

    def test_webp_image_gets_a_thumbnail(self):
        feature = self.feature('WebP', self.pub)
        self.login(self.editor)
        buffer = io.BytesIO()
        Image.new('RGB', (300, 150), (10, 120, 10)).save(buffer, 'WEBP')
        image = SimpleUploadedFile('photo.webp', buffer.getvalue(), content_type='image/webp')
        response = self.upload(feature, 'image', [image], self.pub)
        self.assertEqual(response.status_code, 302)
        name = feature.images.get().image.name
        self.assertTrue(name.endswith('/img/photo.webp'))
        thumbnail = self.full(name.replace('img/photo.webp', 'img/thumbs/photo.webp_thumb.jpg'))
        with Image.open(thumbnail) as thumb:
            self.assertEqual(thumb.format, 'JPEG')

    def test_other_image_format_is_refused_as_image(self):
        feature = self.feature('BMP', self.pub)
        self.login(self.editor)
        response = self.upload(feature, 'image', [text_upload('photo.bmp')], self.pub)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Other formats can be uploaded as files', status_code=400)


class MediaHeadersTests(SimpleTestCase):

    def test_inline_types(self):
        for name, content_type in (('a/r.pdf', 'application/pdf'), ('a/R.PDF', 'application/pdf'),
                                   ('a/n.txt', 'text/plain'), ('a/p.png', 'image/png'),
                                   ('a/p.jpg', 'image/jpeg'), ('a/p.JPEG', 'image/jpeg'),
                                   ('a/p.gif', 'image/gif'), ('a/p.webp', 'image/webp')):
            with self.subTest(name=name):
                self.assertEqual(media_headers(name), (content_type, None))

    def test_everything_else_is_a_download(self):
        for name in ('a/x.xml', 'a/x.xsl', 'a/x.html', 'a/x.svg', 'a/x.dat', 'a/x.docx',
                     'a/x.zip', 'a/x.tif', 'a/README', 'a/r.pdf.old', 'a/n.txt.gz', 'a/x.json',
                     'a/x.pdf.'):
            with self.subTest(name=name):
                content_type, disposition = media_headers(name)
                self.assertEqual(content_type, OCTET)
                self.assertEqual(disposition, f'attachment; filename="{name[2:]}"')

    def test_non_ascii_name(self):
        self.assertEqual(media_headers('a/målinger æ.dat'),
                         (OCTET, "attachment; filename*=utf-8''m%C3%A5linger%20%C3%A6.dat"))

    def test_quote_in_name(self):
        self.assertEqual(media_headers('a/say "hi".dat')[1],
                         'attachment; filename="say \\"hi\\".dat"')


# Extra files: orphans (editors only) and feature files with an unusual type.
ORPHAN_XML = 'reports/1999/extra/logger.xml'
ORPHAN_DAT = 'reports/1999/extra/målinger æ.dat'
ORPHAN_TXT = 'reports/1999/extra/notes.txt'
PUBLIC_FEATURE_DAT = 'features/f-public/log.dat'
HIDDEN_FEATURE_DAT = 'features/f-hidden/log.dat'


class MediaResponseHeaderTests(MediaFixtureMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for name, relpath in (('f-public', PUBLIC_FEATURE_DAT), ('f-hidden', HIDDEN_FEATURE_DAT)):
            Feature.objects.get(name=name).files.add(FileObject.objects.create(file=relpath))

    def setUp(self):
        super().setUp()
        for relpath in (ORPHAN_XML, ORPHAN_DAT, ORPHAN_TXT, PUBLIC_FEATURE_DAT,
                        HIDDEN_FEATURE_DAT):
            self.write_media(relpath)

    def assertDownload(self, response, filename_expr):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], OCTET)
        self.assertEqual(response['Content-Disposition'], f'attachment; {filename_expr}')
        self.assertEqual(response['X-Content-Type-Options'], NOSNIFF)

    def check_downloads(self, accel):
        self.login('superuser')
        for relpath, filename_expr in (
                (ORPHAN_XML, 'filename="logger.xml"'),
                (ORPHAN_DAT, "filename*=utf-8''m%C3%A5linger%20%C3%A6.dat"),
                (PUBLIC_FEATURE_DAT, 'filename="log.dat"')):
            for method in ('get', 'head'):
                with self.subTest(file=relpath, method=method):
                    response = self.fetch(media_path(relpath), method=method)
                    self.assertDownload(response, filename_expr)
                    if accel:
                        self.assertEqual(response['X-Accel-Redirect'],
                                         ACCEL_PREFIX + quote(relpath))
                        self.assertEqual(response.body, b'')
                    else:
                        self.assertNotIn('X-Accel-Redirect', response)
                        if method == 'get':
                            self.assertEqual(response.body, f'content of {relpath}\n'.encode())

    def check_inline(self, accel):
        self.login('superuser')
        for relpath, content_type in (
                (f'reports/1999/{P}_v.pdf', 'application/pdf'),
                (ORPHAN_TXT, 'text/plain'),
                ('reports/1999/thumbs/99-01_thumb.jpg', 'image/jpeg')):
            with self.subTest(file=relpath):
                response = self.fetch(media_path(relpath))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'], content_type)
                self.assertEqual(response['X-Content-Type-Options'], NOSNIFF)
                disposition = response.get('Content-Disposition', '')
                self.assertFalse(disposition.startswith('attachment'), disposition)
                self.assertEqual('X-Accel-Redirect' in response, accel)

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX=ACCEL_PREFIX)
    def test_accel_mode_downloads(self):
        self.check_downloads(accel=True)

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX='')
    def test_stream_mode_downloads(self):
        self.check_downloads(accel=False)

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX=ACCEL_PREFIX)
    def test_accel_mode_inline(self):
        self.check_inline(accel=True)

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX='')
    def test_stream_mode_inline(self):
        self.check_inline(accel=False)

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX=ACCEL_PREFIX)
    def test_access_unchanged(self):
        # A feature file of a public report: anonymous may download it (as a download).
        self.login('anonymous')
        response = self.fetch(media_path(PUBLIC_FEATURE_DAT))
        self.assertDownload(response, 'filename="log.dat"')
        self.assertEqual(response['Cache-Control'], 'public, max-age=3600')
        # Hidden feature (confidential report) and orphans: still 404, without file headers.
        for key, relpath in (('anonymous', HIDDEN_FEATURE_DAT), ('dtu', HIDDEN_FEATURE_DAT),
                             ('anonymous', ORPHAN_XML), ('author', ORPHAN_XML),
                             ('anonymous', f'reports/1999/{C}_v.pdf')):
            with self.subTest(user=key, file=relpath):
                self.login(key)
                response = self.fetch(media_path(relpath))
                self.assertEqual(response.status_code, 404)
                self.assertNotIn('X-Accel-Redirect', response)
                self.assertNotIn('Content-Disposition', response)
        # The author of the confidential report sees the hidden feature's file, privately.
        self.login('author')
        response = self.fetch(media_path(HIDDEN_FEATURE_DAT))
        self.assertDownload(response, 'filename="log.dat"')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
