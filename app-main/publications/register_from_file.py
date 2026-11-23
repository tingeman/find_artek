# -*- coding: utf-8 -*-
"""Excel import of reports (the upload page add_reports_from_file_upload).

The whole file is imported in one transaction: if any row has an error, nothing is saved
(no reports, persons, topics or keywords, also no persons taken from the directory), and every
problem is reported as "Sheet '<name>', row <n>: <problem>". The template with the columns is
static/publications/docs/ARTEK_report_list.xlsx (its "Help" sheet explains them).
"""

import openpyxl
import os.path
import datetime
import dateutil.parser
import string
import re
import latexcodec  # noqa: F401  (registers the 'latex' codec)
import codecs

from pybtex.database import Person as pybtexPerson

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.contrib import messages
from django.db import transaction

from publications import models, utils_person

from publications.utils_models import get_or_create_keywords

# from django.shortcuts import get_object_or_404  # Not used
# import pdb  # Not used
# import chardet  # Not used
# import simplejson as json  # Not used


import logging
logger = logging.getLogger(__name__)


# Publication types the import accepts (all are numbered reports).
REPORT_TYPES = ['STUDENTREPORT', 'MASTERSTHESIS', 'PHDTHESIS', 'DIPLOMPROJEKT', 'BACHELORTHESIS']
DEFAULT_TYPE = 'STUDENTREPORT'

# Column names (lower case) and the singular/plural spellings accepted for them.
COLUMN_ALIASES = {
    'number': 'number', 'year': 'year', 'title': 'title', 'type': 'type',
    'topic': 'topic', 'topics': 'topic',
    'author': 'authors', 'authors': 'authors',
    'supervisor': 'supervisors', 'supervisors': 'supervisors',
    'editor': 'editors', 'editors': 'editors',
    'abstract': 'abstract',
    'keyword': 'keywords', 'keywords': 'keywords',
    'comment': 'comment', 'comments': 'comment',
}
# Columns of the template, in its order ('editors' is accepted too, but not in the template).
# Persons columns, linked in this order.
TEMPLATE_COLUMNS = ['number', 'year', 'title', 'type', 'topic', 'authors', 'supervisors',
                    'abstract', 'keywords', 'comment']
PERSON_COLUMNS = ['authors', 'supervisors', 'editors']
# Columns that must be present. Cells: authors must be filled; title may be empty.
REQUIRED_COLUMNS = ['title', 'authors']   # and 'number' or 'year'
# A sheet with this name (any case) is not imported: the template's explanations.
HELP_SHEET = 'help'

re_list_sep = re.compile(r'\s*[,;]\s*')
re_number_prefix = re.compile(r'^(\d{2})-')


class _Rollback(Exception):
    """Raised inside the import transaction when a row had an error."""


def year_from_number(number):
    """The year of a report number 'YY-NN': 90-99 is 19YY, below 90 is 20YY (there are no
    reports before 1996). None if the number has no two-digit prefix."""
    match = re_number_prefix.match(number)
    if not match:
        return None
    yy = int(match.group(1))
    return (1900 if yy >= 90 else 2000) + yy


def split_list(value):
    """Items of a comma- or semicolon-separated cell, stripped, empty ones dropped."""
    return [item for item in re_list_sep.split((value or '').strip()) if item.strip()]


def _cell_text(value):
    """The text of a cell (None and blank give ''). Whole floats lose their '.0'."""
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


class _Row:
    """One data row of a sheet, checked (pass 1) and then saved (pass 2)."""

    def __init__(self, sheet, sheet_index, row_number, values):
        self.sheet = sheet
        self.sheet_index = sheet_index
        self.row_number = row_number
        self.values = values      # column name -> raw cell value
        self.number = ''
        self.year = None
        self.pubtype = None
        self.topics = []
        self.skip = False         # number already in the database
        self.failed = False       # has a problem; not saved

    def text(self, column):
        return _cell_text(self.values.get(column))

    def where(self):
        return f"Sheet '{self.sheet}', row {self.row_number}"


class _Import:
    """State of one import: problems, notes for the page, report numbers in use."""

    def __init__(self, user):
        self.user = user
        self.errors = []      # problems that stop the import: (sheet index, row, seq, text)
        self.notes = []       # (level, message) shown with the result
        self.numbers = {}     # report number given in the file -> its first row
        self.taken = set()    # numbers given in the file or assigned during the import

    def error(self, row, problem):
        row.failed = True
        self._add_error(row.sheet_index, row.row_number, f'{row.where()}: {problem}')

    def _add_error(self, sheet_index, row_number, text):
        """Row number 0: a problem of the whole sheet (listed first for its sheet)."""
        self.errors.append((sheet_index, row_number, len(self.errors), text))

    def problems(self):
        """The problems by sheet, then row, then the order they were found in."""
        return [text for *_key, text in sorted(self.errors)]

    # ---- pass 1: read and check the sheets ------------------------------------------------

    def read_sheet(self, ws, index):
        """The checked rows of a sheet (``index``: its position in the file), or [] (with a
        warning or error) if it can't be used."""
        name = ws.title
        if ws.max_row < 2 or ws.max_column == 0:
            self.notes.append((messages.WARNING, f"Sheet '{name}' is empty, nothing imported."))
            return []

        columns, unknown = [], []
        for cell in ws[1]:
            header = _cell_text(cell.value)
            column = COLUMN_ALIASES.get(header.lower())
            if header and not column:
                unknown.append(header)
            columns.append(column)
        if unknown:
            self.notes.append((messages.WARNING,
                               f"Sheet '{name}': unknown columns ignored: {', '.join(unknown)}."))
        missing = [c for c in REQUIRED_COLUMNS if c not in columns]
        if 'number' not in columns and 'year' not in columns:
            missing.append('number or year')
        if missing:
            self._add_error(index, 0,
                            f"Sheet '{name}': required columns missing: {', '.join(missing)}.")
            return []

        rows = []
        for row_number, cells in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            values = {}
            for column, value in zip(columns, cells):
                if column and column not in values:
                    values[column] = value
            if all(_cell_text(v) == '' for v in values.values()):
                continue   # blank row
            row = _Row(name, index, row_number, values)
            self.check_row(row)
            rows.append(row)
        return rows

    def check_row(self, row):
        """Problems that need no saving: authors, number, year, type, topics, numbers in use.
        The title may be empty (entries prepared before the reports are written)."""
        if not any(n.strip() for n in utils_person.parse_name_list(row.text('authors'))):
            self.error(row, 'at least one author is required.')

        raw_number = row.values.get('number')
        if isinstance(raw_number, (datetime.date, datetime.datetime)):
            self.error(row, 'the number was read as a date by Excel; format the number column '
                            'as text and type the number again (e.g. 99-01).')
            return
        row.number = row.text('number')

        year = row.text('year')
        if year:
            try:
                row.year = int(year)
            except ValueError:
                self.error(row, f"year '{year}' is not a number.")
        elif row.number:
            row.year = year_from_number(row.number)
            if row.year is None:
                self.error(row, f"no year, and the number '{row.number}' does not start with "
                                f"a two-digit year (e.g. 99-01).")
        else:
            self.error(row, 'a number or a year is required.')

        type_name = row.text('type') or DEFAULT_TYPE
        row.pubtype = models.PubType.objects.filter(type__iexact=type_name).first()
        if row.pubtype is None or row.pubtype.type not in REPORT_TYPES:
            self.error(row, f"type '{type_name}' is not accepted; accepted types: "
                            f"{', '.join(REPORT_TYPES)}.")

        for name in split_list(row.text('topic')):
            topic = models.Topic.objects.filter(topic__iexact=name).first()
            if topic is None:
                valid = ', '.join(sorted(models.Topic.objects.values_list('topic', flat=True)))
                self.error(row, f"unknown topic '{name}'; valid topics: {valid}.")
            elif topic not in row.topics:
                row.topics.append(topic)

        if row.number:
            first = self.numbers.get(row.number)
            if first is not None:
                self.error(row, f"number '{row.number}' is also in {first.where()}.")
                return
            self.numbers[row.number] = row
            self.taken.add(row.number)
            existing = models.Publication.objects.filter(number=row.number).first()
            if existing is not None:
                row.skip = True
                report = (f"'{existing.title}' [id:{existing.pk}]" if existing.title
                          else f"[id:{existing.pk}]")
                self.notes.append((messages.WARNING,
                                   f"{row.where()}: report number '{row.number}' already exists "
                                   f"(report {report}); row skipped, the existing report was "
                                   f"not changed."))

    # ---- pass 2: save ---------------------------------------------------------------------

    def next_number(self, year):
        """The next free number 'YY-NN' for ``year``: not in the database and not given or
        assigned anywhere in the file."""
        suffix = str(year)[-2:]
        used = set(models.Publication.objects.filter(number__startswith=f'{suffix}-')
                   .values_list('number', flat=True)) | self.taken
        for increment in range(1, 1000):
            candidate = f'{suffix}-{increment:02d}'
            if candidate not in used:
                self.taken.add(candidate)
                return candidate
        raise ValueError(f'No free report number for {year}.')

    def save_row(self, row):
        """Create the report of a checked row. Returns True if it was created."""
        if row.skip or row.failed:
            return False
        if not row.number:
            row.number = self.next_number(row.year)
            self.notes.append((messages.INFO,
                               f"{row.where()}: report number '{row.number}' assigned."))
        pub = models.Publication.objects.create(
            type=row.pubtype, number=row.number, year=row.year, title=row.text('title'),
            abstract=row.text('abstract'), comment=row.text('comment'),
            created_by=self.user, modified_by=self.user)
        logger.debug('Excel import: %s: report %s [id:%s] created', row.where(), pub.number,
                     pub.pk)
        for field in PERSON_COLUMNS:
            for _level, problem in add_persons_to_publication(row.text(field), pub, field,
                                                              self.user):
                self.error(row, problem)
        for topic in row.topics:
            pub.publication_topics.add(topic)
        for keyword in get_or_create_keywords(split_list(row.text('keywords'))):
            pub.publication_keywords.add(keyword)
        return True


def xlsx_pubs(filepath, user=None):
    """Import the reports of the Excel file ``filepath`` (relative to MEDIA_ROOT, or absolute)
    in one transaction. Returns the messages for the page as (level, text) tuples. If any row
    has an error, nothing is saved and the messages list every problem."""
    wb = openpyxl.load_workbook(os.path.join(settings.MEDIA_ROOT, filepath), data_only=True)
    job = _Import(user)
    sheets, created = [], {}
    try:
        with transaction.atomic():
            sheets = [(ws.title, job.read_sheet(ws, index))
                      for index, ws in enumerate(wb.worksheets)
                      if ws.title.strip().lower() != HELP_SHEET]
            # Rows without problems are saved also when others have some, so that the
            # problems of persons are found too; everything is rolled back then.
            for name, rows in sheets:
                created[name] = sum(job.save_row(row) for row in rows)
            if job.errors:
                raise _Rollback()
    except _Rollback:
        count = len(job.errors)
        result = [(messages.ERROR,
                   f"Nothing was imported: the file has {count} problem{'s' if count != 1 else ''}."
                   f" Correct the file and upload it again.")]
        result += [(messages.ERROR, problem) for problem in job.problems()]
        result += [note for note in job.notes if note[0] == messages.WARNING]
        return result

    result = list(job.notes)
    for name, rows in sheets:
        if not rows:
            continue
        skipped = sum(1 for row in rows if row.skip)
        level = messages.SUCCESS if not skipped else messages.INFO
        result.append((level, f"Sheet '{name}': {created[name]} report"
                              f"{'s' if created[name] != 1 else ''} created, {skipped} "
                              f"row{'s' if skipped != 1 else ''} skipped."))
    return result


def add_persons_to_publication(names, pub, field, user):
    """Link the persons in ``names`` (one cell of the column ``field``: 'authors',
    'supervisors' or 'editors') to ``pub``, in order. Returns the problems as
    (messages.ERROR, text) tuples; xlsx_pubs reports them as row errors.

    - A study number or initials: the person in the database, else (USE_LDAP on) the one in the
      DTU directory, created here. Not found: a problem.
    - A name 'Given Surname' (or 'Surname, Given'): always a new person; the link is flagged
      exact_match / relaxed_match / multiple_match if persons with that name exist. A name
      without a given name: a problem.
    """
    problems = []

    if not names or not names.strip():
        return problems

    # Through-table, e.g. 'authors' -> Authorship
    through_tbl = getattr(models, field[0].upper() + field[1:-1] + 'ship')
    role = field[:-1].lower()
    use_ldap = bool(getattr(settings, 'USE_LDAP', False))
    where = 'the database or the DTU directory' if use_ldap else 'the database'

    person_entity_list = [s for s in utils_person.parse_name_list(names) if s]

    for id, s in enumerate(person_entity_list):
        logger.debug('Excel import: %s %d: %s', role, id, s)
        exact_match = False
        multiple_match = False
        relaxed_match = False

        if re.search('[a-zA-Z]{1}[0-9]{6}', s) or len(re.split('[^A-Za-z]', s)) == 1:
            # A study number, or only consecutive letters: initials
            if re.search('[a-zA-Z]{1}[0-9]{6}', s):
                p, match = utils_person.get_person(id_number=s, exact=True)
                ldap_query = {'name': s}
            else:
                p, match = utils_person.get_person(initials=s, exact=True)
                ldap_query = {'initials': s}
            if not p and use_ldap:
                result = utils_person.find_ldap_person(**ldap_query)
                if result:
                    p = utils_person.get_or_create_person_from_ldap(ldap_object=result[0],
                                                                    user=user)
                    exact_match = True
                    logger.debug('Excel import:    directory match')
            if not p:
                problems.append((messages.ERROR, f"{role} '{s}' was not found in {where}."))
                continue
        else:
            # A name
            pybtex_person = pybtexPerson(s)

            if not (pybtex_person.first() and pybtex_person.last()):
                problems.append((messages.ERROR,
                                 f"{role} name '{s}' needs a given name and a surname "
                                 f"('Given Surname'), or give a study number or initials."))
                continue

            # Existing persons with this name (exact, else relaxed) only flag the link.
            p, match = utils_person.get_person(pybtex_person=pybtex_person)

            if len(p) > 1:
                multiple_match = True
            if match == 'db_exact' and len(p) > 0:
                exact_match = True
            elif match == 'db_relaxed' and len(p) > 0:
                relaxed_match = True

            # Create new person, also if matched
            p = utils_person.create_person_from_pybtex(pybtex_person=pybtex_person, user=user)

        through_tbl.objects.create(person=p[0],
                                   publication=pub,
                                   exact_match=exact_match,
                                   multiple_match=multiple_match,
                                   relaxed_match=relaxed_match,
                                   **{field[:-1] + '_id': id})

    return problems
