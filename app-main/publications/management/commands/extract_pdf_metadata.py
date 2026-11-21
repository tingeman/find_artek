"""Suggest year, study numbers (with matching persons) and title from report PDFs' text layer
(roadmap FA-R98 step 1, plan PLAN_release-2026-7 T5). Heuristics: publications.pdf_metadata.

Read-only: no database writes, no files written. Prints plain text to stdout and logs
nothing. The output can contain names and study numbers: it is for the operator's terminal
only; don't redirect it into shared files or tickets.

    python manage.py extract_pdf_metadata PATH [PATH ...]   # relative to MEDIA_ROOT
    python manage.py extract_pdf_metadata --unowned          # the PDFs nothing owns
    python manage.py extract_pdf_metadata --evaluate N       # compare with the database
    options: --pages N (default 3), --timeout S (default 30, per pdftotext call)

``--unowned`` takes the unowned files of ``check_media_access --list-unowned`` whose name
contains ``.pdf`` (so ``x.pdf.old`` too). ``--evaluate N`` takes N reports (spread evenly over
the reports in pk order) that have a PDF on disk, and compares the suggestions with
``Publication.title`` (normalized: case, whitespace, punctuation), ``Publication.year`` and the
study numbers among the authors' ``id_number``. It prints a hit rate per field and lists the
misses by report number only.

A broken PDF or a timeout is reported for that file and the command goes on. Exit code 0
unless the arguments are wrong (or a PATH is outside MEDIA_ROOT).
"""
import argparse
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Prefetch

from publications.media_access import media_file_path, resolve_media_path, unowned_media_files
from publications.models import STUDY_NUMBER_RE as ID_STUDY_NUMBER_RE
from publications.models import Authorship, Publication
from publications.pdf_metadata import (
    DEFAULT_PAGES, DEFAULT_TIMEOUT, extract_pdf_metadata, normalize_text,
)


def _positive_int(value):
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(f'must be a positive whole number, not {value!r}')
    return number


class Command(BaseCommand):
    help = ('Suggest year, study numbers (with matching persons) and title from the text layer '
            'of report PDFs (pdftotext). Read-only. Output may contain personal data: '
            'terminal only.')

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='*', metavar='PATH',
                            help='PDF paths relative to MEDIA_ROOT.')
        parser.add_argument('--unowned', action='store_true',
                            help='Read the unowned PDFs (check_media_access --list-unowned).')
        parser.add_argument('--evaluate', type=_positive_int, metavar='N',
                            help='Compare the suggestions for N reports with the database and '
                                 'print hit rates per field.')
        parser.add_argument('--pages', type=_positive_int, default=DEFAULT_PAGES,
                            help=f'Pages to read from the start (default {DEFAULT_PAGES}).')
        parser.add_argument('--timeout', type=_positive_int, default=DEFAULT_TIMEOUT,
                            help=f'Seconds per pdftotext call (default {DEFAULT_TIMEOUT}).')

    def handle(self, *args, **options):
        modes = sum([bool(options['paths']), options['unowned'], options['evaluate'] is not None])
        if modes != 1:
            raise CommandError('Give PATH ..., --unowned or --evaluate N (exactly one of them).')
        self.pages = options['pages']
        self.timeout = options['timeout']

        if options['evaluate'] is not None:
            self.evaluate(options['evaluate'])
            return
        if options['unowned']:
            relpaths = [p for p in unowned_media_files() if '.pdf' in p.lower()]
            self.stdout.write(f'Unowned PDFs: {len(relpaths)}')
        else:
            relpaths = []
            for path in options['paths']:
                relpath = resolve_media_path(path)
                if relpath is None:
                    raise CommandError(
                        f'Not a path relative to MEDIA_ROOT (absolute, or leaving it): {path!r}')
                relpaths.append(relpath)
        for relpath in relpaths:
            self.show(relpath)

    def read(self, relpath):
        full = media_file_path(relpath)
        if not os.path.isfile(full):
            return None
        return extract_pdf_metadata(full, pages=self.pages, file_name=relpath,
                                    timeout=self.timeout)

    def show(self, relpath):
        out = self.stdout.write
        out('')
        out(f'== {relpath}')
        result = self.read(relpath)
        if result is None:
            out('  error: file not found')
            return
        if result.error and not result.has_text_layer:
            out(f'  error: {result.error}')
            return
        if not result.has_text_layer:
            out(f'  no text layer (scanned, needs OCR) in the first {self.pages} page(s)')
            return
        out(f'  title: {result.title or "-"}')
        for other in result.title_candidates[1:]:
            out(f'    other candidate: {other}')
        if result.year is None:
            out('  year: -')
        else:
            out(f'  year: {result.year} ({result.year_source})')
            others = ', '.join(f'{y} ({s})' for y, s in result.year_candidates[1:])
            if others:
                out(f'    other candidates: {others}')
        if not result.study_numbers:
            out(f'  study numbers: none in the first {self.pages} page(s)')
        else:
            out('  study numbers:')
            for sn in result.study_numbers:
                persons = '; '.join(f'{name} [pk:{pk}]' for pk, name in sn.persons)
                out(f'    {sn.number}: {persons or "no person with this id_number"}')
        if result.error:
            out(f'  error: {result.error}')

    def evaluate(self, n):
        out = self.stdout.write
        authors = Prefetch('authorship_set',
                           queryset=Authorship.objects.select_related('person').order_by('author_id'))
        candidates = []
        for pub in (Publication.objects.filter(file__isnull=False).select_related('file')
                    .order_by('pk')):
            name = pub.file.file.name if pub.file else ''
            relpath = resolve_media_path(name) if name else None
            if relpath and relpath.lower().endswith('.pdf') and os.path.isfile(
                    media_file_path(relpath)):
                candidates.append((pub.pk, relpath))
        if not candidates:
            out(f'No reports with a PDF on disk under {settings.MEDIA_ROOT}.')
            return
        if len(candidates) > n:  # spread evenly over the whole list
            step = len(candidates) / n
            candidates = [candidates[int(i * step)] for i in range(n)]
        pubs = Publication.objects.prefetch_related(authors).in_bulk([pk for pk, _ in candidates])

        stats = {key: [0, 0] for key in ('title', 'title_contained', 'year', 'year_text',
                                         'study_numbers')}
        numbers_total = numbers_found = 0
        misses = {key: [] for key in ('no_text', 'error', 'title', 'year', 'year_text',
                                      'study_numbers')}
        for pk, relpath in candidates:
            pub = pubs[pk]
            label = pub.number or f'pk {pub.pk}'
            result = self.read(relpath)
            if result is None or (result.error and not result.has_text_layer):
                misses['error'].append(label)
                continue
            if not result.has_text_layer:
                misses['no_text'].append(label)
                continue

            def count(key, hit, miss_key=None):
                stats[key][1] += 1
                if hit:
                    stats[key][0] += 1
                elif miss_key:
                    misses[miss_key].append(label)

            db_title, pdf_title = normalize_text(pub.title), normalize_text(result.title)
            count('title', bool(db_title) and db_title == pdf_title, 'title')
            count('title_contained', bool(db_title) and bool(pdf_title)
                  and (db_title in pdf_title or pdf_title in db_title))
            count('year', result.year == pub.year, 'year')
            text_year = next((y for y, s in result.year_candidates if s != 'file name'), None)
            count('year_text', text_year == pub.year, 'year_text')

            db_numbers = {(a.person.id_number or '').strip().lower()
                          for a in pub.authorship_set.all()
                          if ID_STUDY_NUMBER_RE.match((a.person.id_number or '').strip())}
            if db_numbers:
                found = {sn.number for sn in result.study_numbers}
                numbers_total += len(db_numbers)
                numbers_found += len(db_numbers & found)
                count('study_numbers', db_numbers <= found, 'study_numbers')

        def rate(key):
            hits, total = stats[key]
            return f'{hits}/{total}' + (f' ({100 * hits / total:.0f} %)' if total else '')

        out(f'Evaluated {len(candidates)} report(s), first {self.pages} page(s) each.')
        out(f'  no text layer: {len(misses["no_text"])}, unreadable: {len(misses["error"])}')
        out(f'  title (normalized, equal):        {rate("title")}')
        out(f'  title (one contains the other):   {rate("title_contained")}')
        out(f'  year (best suggestion):           {rate("year")}')
        out(f'  year (from the text only):        {rate("year_text")}')
        out(f'  study numbers (all authors found): {rate("study_numbers")}'
            f'  [reports with study numbers in the DB; numbers found {numbers_found}/{numbers_total}]')
        out('Misses (report numbers):')
        for key, title in (('no_text', 'no text layer'), ('error', 'unreadable'),
                           ('title', 'title'), ('year', 'year'),
                           ('year_text', 'year from the text'),
                           ('study_numbers', 'study numbers')):
            out(f'  {title}: {", ".join(misses[key]) or "-"}')
