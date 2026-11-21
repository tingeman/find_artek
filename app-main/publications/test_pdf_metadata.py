"""Report metadata from the PDF text layer (roadmap FA-R98 step 1, plan PLAN_release-2026-7 T5).

The PDFs are built here: a minimal hand-written PDF with a text layer (Helvetica, a title in a
large font, smaller lines with made-up study numbers, a month and year, an institution line) and
an image-only PDF from Pillow. Never real media. The tests that run ``pdftotext`` are skipped
only if the binary is missing (it is in every image: poppler-utils).
"""
import datetime
import os
import shutil
import subprocess
import tempfile
import unittest
from io import BytesIO, StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from PIL import Image

from publications import pdf_metadata
from publications.models import FileObject, Person, Publication
from publications.pdf_metadata import (
    extract_pdf_metadata, is_skipped_title_line, normalize_text, title_groups, two_digit_year,
    year_candidates, year_from_file_name,
)
from publications.test_factories import make_person, make_report, report_type

HAS_PDFTOTEXT = shutil.which('pdftotext') is not None
_skip_without_pdftotext = unittest.skipUnless(
    HAS_PDFTOTEXT, 'pdftotext (poppler-utils) is not installed; it is in every find_artek image')


def _escape(text):
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def text_pdf(pages):
    """A PDF with a text layer. ``pages`` is a list of pages, each a list of
    ``(font size, y, text)`` lines in Helvetica (ASCII text), with a correct xref table."""
    n_pages = len(pages)
    page_ids = [4 + 2 * i for i in range(n_pages)]
    objects = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: (b'<< /Type /Pages /Kids [' + b' '.join(b'%d 0 R' % i for i in page_ids)
            + b'] /Count %d >>' % n_pages),
        3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
    }
    for page_id, lines in zip(page_ids, pages):
        stream = b'\n'.join(
            b'BT /F1 %d Tf 72 %d Td (%s) Tj ET' % (size, y, _escape(text).encode('latin-1'))
            for size, y, text in lines)
        objects[page_id] = (
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
            b'/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>' % (page_id + 1))
        objects[page_id + 1] = b'<< /Length %d >>\nstream\n%s\nendstream' % (len(stream), stream)

    out = bytearray(b'%PDF-1.4\n')
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b'%d 0 obj\n%s\nendobj\n' % (number, objects[number])
    xref = len(out)
    size = max(objects) + 1
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size
    for number in range(1, size):
        out += b'%010d 00000 n \n' % offsets[number]
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, xref)
    return bytes(out)


TITLE_1 = 'Permafrost under the runway'
TITLE_2 = 'in Ilulissat'

# Page 1: an institution line in the largest font (skipped), a two-line title, small lines
# with a study number, a month + year, an institution line and a frequent other year.
# Page 2: another study number.
REPORT_PAGES = [
    [
        (40, 780, 'DTU'),
        (28, 700, TITLE_1),
        (28, 664, TITLE_2),
        (11, 600, 'Student report by s123456'),
        (11, 580, 'June 2013'),
        (11, 560, 'Arctic Technology Centre, DTU Byg'),
        (11, 540, 'Field data from 2001, 2001 and 2001 compared'),
    ],
    [
        (11, 700, 'Second author: S654321 wrote the appendix'),
        (11, 680, 'More text on the second page so that it is not empty.'),
    ],
]


def image_pdf():
    """An image-only PDF (no text layer), as a scanner makes it."""
    buf = BytesIO()
    Image.new('RGB', (200, 280), 'white').save(buf, 'PDF')
    return buf.getvalue()


BROKEN = bytes(range(256)) * 8  # not a PDF


class MediaRootMixin:
    """A temporary MEDIA_ROOT, removed after each test, and ``write`` for files in it."""

    def setUp(self):
        super().setUp()
        base = tempfile.mkdtemp(prefix='find_artek_pdf_test_')
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        self.base = base
        self.media_root = os.path.join(base, 'media')
        os.makedirs(self.media_root)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

    def write(self, relpath, content):
        full = os.path.join(self.media_root, *relpath.split('/'))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(content)
        return full

    def run_command(self, *args):
        out = StringIO()
        call_command('extract_pdf_metadata', *args, stdout=out)
        return out.getvalue()


class HeuristicsTests(SimpleTestCase):
    """The pure helpers, without pdftotext."""

    TODAY = datetime.date(2026, 11, 21)

    def test_two_digit_year_century_rule(self):
        for yy, year in ((96, 1996), (14, 2014), (0, 2000), (26, 2026), (27, 1927), (99, 1999)):
            with self.subTest(yy=yy):
                self.assertEqual(two_digit_year(yy, self.TODAY), year)

    def test_year_from_file_name(self):
        cases = (
            ('reports/1996/96-02.pdf', 1996),
            ('reports/14-28_Some_title.pdf', 2014),
            ('14-128.pdf', 2014),
            ('reports/2014-05-12_scan.pdf', None),  # a date, not a report number
            ('report.pdf', None),
            ('123-45.pdf', None),
        )
        for name, year in cases:
            with self.subTest(name=name):
                self.assertEqual(year_from_file_name(name, self.TODAY), year)

    def test_year_ranking(self):
        front = 'Data 2001 2001 2001\nArctic Technology Centre 2010\nJuni 2013\n'
        self.assertEqual(year_candidates(front, '', self.TODAY),
                         [(2013, 'month'), (2010, 'institution'), (2001, 'frequent')])
        self.assertEqual(year_candidates(front, '96-02.pdf', self.TODAY)[0], (1996, 'file name'))
        self.assertEqual(year_candidates('Printed 2099 and 1890', '', self.TODAY), [])

    def test_skipped_title_lines(self):
        for line in ('DTU', 'Danmarks Tekniske Universitet', 'Arctic Technology Centre, DTU Byg',
                     'ARTEK', '2014', '14-28', 'Report no. 96-02', 'DTU - 1996'):
            with self.subTest(line=line):
                self.assertTrue(is_skipped_title_line(line))
        for line in ('Permafrost under the runway', 'Arctic roads in Sisimiut'):
            with self.subTest(line=line):
                self.assertFalse(is_skipped_title_line(line))

    def test_title_groups(self):
        lines = [(40, 'DTU'), (28, 'A long title'), (27.5, 'on two lines'), (11, 's123456'),
                 (11, 'June 2013'), (18, 'A subtitle')]
        self.assertEqual(title_groups(lines), ['A long title on two lines', 'A subtitle',
                                               'June 2013'])

    def test_normalize_text(self):
        self.assertEqual(normalize_text('  Permafrost: under the  RUNWAY! '),
                         'permafrost under the runway')


@_skip_without_pdftotext
class ExtractTests(MediaRootMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.report = self.write('reports/report.pdf', text_pdf(REPORT_PAGES))

    def test_title_from_the_largest_text(self):
        result = extract_pdf_metadata(self.report)
        self.assertTrue(result.has_text_layer)
        self.assertEqual(result.error, '')
        self.assertEqual(result.title, f'{TITLE_1} {TITLE_2}')

    def test_study_number_on_page_two_needs_two_pages(self):
        one = extract_pdf_metadata(self.report, pages=1)
        self.assertEqual([sn.number for sn in one.study_numbers], ['s123456'])
        two = extract_pdf_metadata(self.report, pages=2)
        self.assertEqual([sn.number for sn in two.study_numbers], ['s123456', 's654321'])

    def test_study_number_matched_to_person(self):
        person = make_person('Ane', 'Testesen', id_number='S123456')
        result = extract_pdf_metadata(self.report, pages=2)
        matches = {sn.number: sn.persons for sn in result.study_numbers}
        self.assertEqual(matches['s123456'], [(person.pk, 'Ane Testesen')])
        self.assertEqual(matches['s654321'], [])

    def test_year_from_front_page(self):
        result = extract_pdf_metadata(self.report)
        self.assertEqual((result.year, result.year_source), (2013, 'month'))

    def test_year_from_file_name(self):
        path = self.write('reports/14-28.pdf', text_pdf(REPORT_PAGES))
        result = extract_pdf_metadata(path)
        self.assertEqual((result.year, result.year_source), (2014, 'file name'))
        self.assertEqual(result.year_candidates[1], (2013, 'month'))

    def test_image_only_pdf_has_no_text_layer(self):
        path = self.write('reports/scan.pdf', image_pdf())
        result = extract_pdf_metadata(path)
        self.assertFalse(result.has_text_layer)
        self.assertEqual(result.error, '')
        self.assertEqual(result.title, '')

    def test_broken_file_is_reported(self):
        path = self.write('reports/broken.pdf', BROKEN)
        result = extract_pdf_metadata(path)
        self.assertFalse(result.has_text_layer)
        self.assertIn('pdftotext failed', result.error)

    def test_timeout_is_reported(self):
        with mock.patch.object(pdf_metadata.subprocess, 'run',
                               side_effect=subprocess.TimeoutExpired('pdftotext', 5)):
            result = extract_pdf_metadata(self.report, timeout=5)
        self.assertIn('timed out after 5 s', result.error)


@_skip_without_pdftotext
class CommandTests(MediaRootMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.write('reports/14-28.pdf', text_pdf(REPORT_PAGES))
        self.write('reports/scan.pdf', image_pdf())
        self.write('reports/broken.pdf', BROKEN)

    def test_paths(self):
        make_person('Ane', 'Testesen', id_number='s123456')
        output = self.run_command('reports/14-28.pdf', 'reports/scan.pdf', 'reports/broken.pdf',
                                  'reports/missing.pdf', '--pages', '2')
        report = output.split('== reports/14-28.pdf', 1)[1].split('==', 1)[0]
        self.assertIn(f'title: {TITLE_1} {TITLE_2}', report)
        self.assertIn('year: 2014 (file name)', report)
        self.assertIn('2013 (month)', report)
        self.assertIn('s123456: Ane Testesen [pk:', report)
        self.assertIn('s654321: no person with this id_number', report)
        scan = output.split('== reports/scan.pdf', 1)[1].split('==', 1)[0]
        self.assertIn('no text layer (scanned, needs OCR)', scan)
        broken = output.split('== reports/broken.pdf', 1)[1].split('==', 1)[0]
        self.assertIn('error: pdftotext failed', broken)
        self.assertIn('error: file not found', output.split('== reports/missing.pdf', 1)[1])

    def test_pages_option(self):
        self.assertNotIn('s654321', self.run_command('reports/14-28.pdf', '--pages', '1'))
        self.assertIn('s654321', self.run_command('reports/14-28.pdf', '--pages', '2'))

    def test_timeout_reported_and_command_goes_on(self):
        with mock.patch.object(pdf_metadata.subprocess, 'run',
                               side_effect=subprocess.TimeoutExpired('pdftotext', 1)):
            output = self.run_command('reports/14-28.pdf', 'reports/scan.pdf', '--timeout', '1')
        self.assertEqual(output.count('error: pdftotext timed out after 1 s'), 2)

    def test_path_outside_media_root_is_refused(self):
        outside = os.path.join(self.base, 'outside.pdf')
        with open(outside, 'wb') as f:
            f.write(text_pdf(REPORT_PAGES))
        for path in ('../outside.pdf', outside, 'reports/../../outside.pdf'):
            with self.subTest(path=path):
                with self.assertRaises(CommandError):
                    self.run_command(path)

    def test_wrong_arguments(self):
        for args in ((), ('reports/14-28.pdf', '--unowned'), ('--unowned', '--evaluate', '2')):
            with self.subTest(args=args):
                with self.assertRaises(CommandError):
                    self.run_command(*args)
        with self.assertRaises(CommandError):
            self.run_command('reports/14-28.pdf', '--pages', '0')

    def test_unowned_lists_only_unowned_pdfs(self):
        Publication.objects.create(
            type=report_type(), number='14-28', title='Owned', year=2014, verified=True,
            confidential=False, file=FileObject.objects.create(file='reports/14-28.pdf'))
        self.write('reports/orphan.pdf.old', text_pdf(REPORT_PAGES))
        self.write('reports/notes.txt', b'not a pdf')
        output = self.run_command('--unowned')
        listed = [line[3:] for line in output.splitlines() if line.startswith('== ')]
        self.assertEqual(listed, ['reports/broken.pdf', 'reports/orphan.pdf.old',
                                  'reports/scan.pdf'])

    def test_no_database_writes(self):
        make_person('Ane', 'Testesen', id_number='s123456')
        make_report(report_type(), '14-28', verified=True, confidential=False, year=2014,
                    file=FileObject.objects.create(file='reports/14-28.pdf'))
        counts = (Person.objects.count(), Publication.objects.count(),
                  FileObject.objects.count())
        with CaptureQueriesContext(connection) as ctx:
            self.run_command('reports/14-28.pdf', 'reports/scan.pdf', 'reports/broken.pdf')
            self.run_command('--unowned')
            self.run_command('--evaluate', '5')
        self.assertTrue(ctx.captured_queries)
        for query in ctx.captured_queries:
            self.assertTrue(query['sql'].lstrip().upper().startswith('SELECT'), query['sql'])
        self.assertEqual((Person.objects.count(), Publication.objects.count(),
                          FileObject.objects.count()), counts)
        self.assertEqual(sorted(os.listdir(os.path.join(self.media_root, 'reports'))),
                         ['14-28.pdf', 'broken.pdf', 'scan.pdf'])


@_skip_without_pdftotext
class EvaluateTests(MediaRootMixin, TestCase):

    def setUp(self):
        super().setUp()
        pubtype = report_type()
        hit_author = make_person('Ane', 'Testesen', id_number='S123456')
        missed_author = make_person('Bo', 'Prøvesen', id_number='s777777')
        # 14-28: title, year and study number all match.
        self.write('reports/2014/14-28.pdf', text_pdf(REPORT_PAGES))
        make_report(pubtype, '14-28', verified=True, confidential=False,
                    title=f'{TITLE_1}: {TITLE_2.upper()}', year=2014, authors=[hit_author],
                    file=FileObject.objects.create(file='reports/2014/14-28.pdf'))
        # 96-02: other title, the author's study number isn't in the PDF; year from the name.
        self.write('reports/1996/96-02.pdf', text_pdf(REPORT_PAGES))
        make_report(pubtype, '96-02', verified=False, confidential=True,
                    title='Something else entirely', year=1996, authors=[missed_author],
                    file=FileObject.objects.create(file='reports/1996/96-02.pdf'))
        # A report whose PDF isn't on disk is not evaluated.
        make_report(pubtype, '99-01', verified=True, confidential=False, year=1999,
                    file=FileObject.objects.create(file='reports/1999/99-01.pdf'))

    def test_hit_rates(self):
        output = self.run_command('--evaluate', '10')
        self.assertIn('Evaluated 2 report(s), first 3 page(s) each.', output)
        self.assertIn('title (normalized, equal):        1/2 (50 %)', output)
        self.assertIn('year (best suggestion):           2/2 (100 %)', output)
        self.assertIn('year (from the text only):        0/2 (0 %)', output)
        self.assertIn('study numbers (all authors found): 1/2 (50 %)', output)
        self.assertIn('numbers found 1/2', output)
        misses = output.split('Misses (report numbers):', 1)[1]
        self.assertIn('  title: 96-02\n', misses)
        self.assertIn('  year: -\n', misses)
        self.assertIn('  study numbers: 96-02\n', misses)
        self.assertNotIn('99-01', output)
        # Misses by report number only: no names, no study numbers.
        for private in ('Testesen', 'Prøvesen', 's123456', 's777777', 'S123456'):
            self.assertNotIn(private, output)

    def test_evaluate_takes_n_reports(self):
        output = self.run_command('--evaluate', '1')
        self.assertIn('Evaluated 1 report(s)', output)
