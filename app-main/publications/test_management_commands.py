"""Management commands that write or delete files under MEDIA_ROOT: generate_thumbnails (run by
the thumbnail cron job) and cleanup_temp_files.

Each test runs on its own temporary MEDIA_ROOT with a one-page PDF drawn in the test
(Pillow); poppler (pdftoppm, used by pdf2image) is in the image. The tests check which files
the commands create or delete, and that other files stay as they were.
"""

import os
import shutil
import tempfile
import time
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from PIL import Image

from publications.models import FileObject
from publications.test_factories import make_report, report_type


def write_file(path, content=b'keep me'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(content)


def write_pdf(path, size=(300, 600)):
    """A one-page PDF (portrait, aspect 1:2)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new('RGB', size, 'white').save(path, 'PDF')


class _MediaRootCase(TestCase):

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='fa-test-media-')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        settings_override = override_settings(MEDIA_ROOT=self.media_root)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def media(self, *parts):
        return os.path.join(self.media_root, *parts)

    def files(self):
        """All files under MEDIA_ROOT, as relative paths."""
        found = set()
        for root, _dirs, names in os.walk(self.media_root):
            for name in names:
                found.add(os.path.relpath(os.path.join(root, name), self.media_root)
                          .replace(os.sep, '/'))
        return found

    def run_command(self, *args, **kwargs):
        out = StringIO()
        call_command(*args, stdout=out, **kwargs)
        return out.getvalue()


class GenerateThumbnailsTests(_MediaRootCase):

    THUMB = 'reports/1999/thumbs/1999-01_thumb.jpg'

    def setUp(self):
        super().setUp()
        pubtype = report_type()
        write_pdf(self.media('reports', '1999', '1999-01.pdf'))
        self.pub = make_report(pubtype, '1999-01', verified=True, confidential=False, year=1999,
                               file=FileObject.objects.create(file='reports/1999/1999-01.pdf'))
        self.no_file = make_report(pubtype, '1999-02', verified=True, confidential=False,
                                   year=1999)
        # Unrelated files that must stay as they are.
        write_file(self.media('reports', '1999', 'thumbs', 'other_thumb.jpg'))
        write_file(self.media('reports', '1999', 'notes.txt'))
        self.before = self.files()

    def thumb_size(self):
        with Image.open(self.media(self.THUMB)) as image:
            return image.format, image.size

    def test_creates_missing_thumbnail_from_first_page(self):
        out = self.run_command('generate_thumbnails')
        self.assertEqual(self.files(), self.before | {self.THUMB})
        # Default height 400, aspect ratio of the page (1:2) kept.
        self.assertEqual(self.thumb_size(), ('JPEG', (200, 400)))
        self.assertIn('Successful: 1', out)

    def test_custom_height(self):
        self.run_command('generate_thumbnails', '--height', '120')
        self.assertEqual(self.thumb_size(), ('JPEG', (60, 120)))

    def test_existing_thumbnail_is_kept_without_force(self):
        write_file(self.media(self.THUMB), b'old thumbnail')
        out = self.run_command('generate_thumbnails')
        with open(self.media(self.THUMB), 'rb') as f:
            self.assertEqual(f.read(), b'old thumbnail')
        self.assertIn('Skipped: 1', out)

    def test_force_regenerates_existing_thumbnail(self):
        write_file(self.media(self.THUMB), b'old thumbnail')
        self.run_command('generate_thumbnails', '--force')
        self.assertEqual(self.thumb_size(), ('JPEG', (200, 400)))

    def test_dry_run_creates_nothing(self):
        out = self.run_command('generate_thumbnails', '--dry-run')
        self.assertEqual(self.files(), self.before)
        self.assertIn('Would generate', out)

    def test_missing_pdf_is_an_error_and_creates_nothing(self):
        os.remove(self.media('reports', '1999', '1999-01.pdf'))
        out = self.run_command('generate_thumbnails')
        self.assertEqual(self.files(), self.before - {'reports/1999/1999-01.pdf'})
        self.assertIn('Errors: 1', out)

    def test_unreadable_pdf_is_an_error_and_leaves_no_thumbnail(self):
        write_file(self.media('reports', '1999', '1999-01.pdf'), b'not a pdf')
        out = self.run_command('generate_thumbnails')
        self.assertEqual(self.files(), self.before)
        self.assertIn('Errors: 1', out)

    def test_single_publication(self):
        self.run_command('generate_thumbnails', '--publication-id', str(self.pub.pk))
        self.assertEqual(self.files(), self.before | {self.THUMB})

    def test_single_publication_without_file_is_skipped(self):
        out = self.run_command('generate_thumbnails', '--publication-id', str(self.no_file.pk))
        self.assertEqual(self.files(), self.before)
        self.assertIn('Skipped: 1', out)

    def test_unknown_publication(self):
        with self.assertRaises(CommandError):
            self.run_command('generate_thumbnails', '--publication-id', '999999')

    def test_height_out_of_range(self):
        with self.assertRaises(CommandError):
            self.run_command('generate_thumbnails', '--height', '10')
        self.assertEqual(self.files(), self.before)


class CleanupTempFilesTests(_MediaRootCase):
    """Files under MEDIA_ROOT/temp/ older than --max-age (default 1 h) are deleted, then empty
    directories below temp/. The clock is moved forward (time.time in the command) instead of
    backdating the files, since the command uses the change time (ctime)."""

    OLD = 'temp/20261101-120000/upload.pdf'
    OTHER = 'reports/1999/1999-01.pdf'

    def setUp(self):
        super().setUp()
        write_file(self.media(*self.OLD.split('/')))
        write_file(self.media(*self.OTHER.split('/')))

    def run_later(self, seconds, *args):
        """Run the command as if ``seconds`` had passed since the files were written."""
        later = time.time() + seconds
        with mock.patch('publications.management.commands.cleanup_temp_files.time') as clock:
            clock.time.return_value = later
            return self.run_command('cleanup_temp_files', *args)

    def test_old_temp_file_and_its_empty_directory_are_removed(self):
        out = self.run_later(2 * 3600)
        self.assertEqual(self.files(), {self.OTHER})
        self.assertFalse(os.path.exists(self.media('temp', '20261101-120000')))
        self.assertTrue(os.path.isdir(self.media('temp')))   # temp/ itself stays
        self.assertIn('Deleted 1 files', out)

    def test_young_temp_file_is_kept(self):
        out = self.run_later(60)
        self.assertEqual(self.files(), {self.OLD, self.OTHER})
        self.assertIn('Deleted 0 files', out)

    def test_max_age_option(self):
        self.run_later(120, '--max-age', '60')
        self.assertEqual(self.files(), {self.OTHER})

    def test_dry_run_deletes_nothing(self):
        out = self.run_later(2 * 3600, '--dry-run')
        self.assertEqual(self.files(), {self.OLD, self.OTHER})
        self.assertIn('Would delete', out)

    def test_files_outside_temp_are_never_touched(self):
        self.run_later(365 * 24 * 3600)
        self.assertIn(self.OTHER, self.files())

    def test_without_temp_directory(self):
        shutil.rmtree(self.media('temp'))
        out = self.run_command('cleanup_temp_files')
        self.assertEqual(self.files(), {self.OTHER})
        self.assertIn('Nothing to clean', out)
