"""Suggest a report's year, study numbers and title from its PDF text layer (roadmap FA-R98
step 1, plan PLAN_release-2026-7 T5).

``extract_pdf_metadata(path)`` runs poppler's ``pdftotext`` (in every image: ``poppler-utils``)
on the first ``pages`` pages and returns a ``PdfSuggestions``. It reads the file and the
``Person`` table, and writes nothing. No OCR: a scanned PDF without a text layer is reported as
``has_text_layer=False``. Used by the management command ``extract_pdf_metadata``; not exposed
on the web.

Heuristics:

- **Text layer**: the pages read contain fewer than ``MIN_TEXT_CHARS`` letters and digits ->
  no text layer (scanned, needs OCR). Scans often carry a few stray characters (a page number,
  a stamp), so "near-empty" counts as empty.
- **Study numbers**: ``s`` + 6 digits (``\\bs\\d{6}\\b``, any case) on all pages read, in
  order of appearance, lower case, each looked up in ``Person.id_number`` (case-insensitive).
- **Year**, ranked:

  1. ``file name``: a report number ``YY-NN`` in the file name (``96-02`` -> 1996). Two-digit
     years up to the current year's two digits are 20YY, the others 19YY (in 2026: ``00``-``26``
     -> 2000-2026, ``27``-``99`` -> 1927-1999). ARTEK reports start in the 1960s, so the rule
     only fails for reports older than 100 years or dated in the future.
  2. ``month``: a 19xx/20xx year on a front-page line with a month name (English or Danish).
  3. ``institution``: a year on a front-page line naming DTU, BYG, ARTEK or Arctic
     Technology.
  4. ``frequent``: the most frequent year on the front page (ties: the latest).

  Years outside ``MIN_YEAR`` .. next year are ignored.
- **Title**: from page 1's ``pdftotext -bbox-layout``: the line(s) with the largest height
  (font size). Consecutive lines of nearly the same height (``TITLE_HEIGHT_TOLERANCE``) are
  joined. Lines that are only an institution name (DTU, Danmarks Tekniske Universitet, BYG,
  ARTEK, Arctic Technology Centre, ...), only a year or number, or a report number line are
  skipped, and so are lines with only study numbers. ``title_candidates`` holds the
  next-largest groups too.
"""
import datetime
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field

from django.db.models.functions import Lower

PDFTOTEXT = 'pdftotext'
DEFAULT_PAGES = 3
DEFAULT_TIMEOUT = 30  # seconds per pdftotext call
MIN_TEXT_CHARS = 40
MIN_YEAR = 1950
TITLE_HEIGHT_TOLERANCE = 0.1  # lines within 10 % of the group's height join the title
TITLE_CANDIDATES = 3

STUDY_NUMBER_RE = re.compile(r'\bs\d{6}\b', re.IGNORECASE)
YEAR_RE = re.compile(r'(?<!\d)((?:19|20)\d{2})(?!\d)')
# A report number "YY-NN" (or YY-NNN) not inside a longer number or a date like 2014-05-12.
FILE_NAME_NUMBER_RE = re.compile(r'(?<![\d-])(\d{2})-\d{2,3}(?![\d-])')

MONTHS = (
    # English
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
    'october', 'november', 'december',
    # Danish (april, august, september, november, december as in English)
    'januar', 'februar', 'marts', 'maj', 'juni', 'juli', 'oktober',
)
MONTH_RE = re.compile(r'\b(?:' + '|'.join(MONTHS) + r')\b', re.IGNORECASE)
INSTITUTION_LINE_RE = re.compile(r'\b(?:dtu|byg|artek|arctic\s+technology)\b', re.IGNORECASE)

# Phrases that make up an institution line (normalized: lower case, words only). Longest
# first, so "dtu byg" goes before "dtu".
INSTITUTION_PHRASES = sorted((
    'danmarks tekniske universitet', 'technical university of denmark', 'dtu', 'byg',
    'dtu byg', 'artek', 'arctic technology centre', 'arctic technology center',
    'arctic technology', 'center for arktisk teknologi', 'arktisk teknologi', 'sustain',
    'dtu sustain', 'department of civil engineering', 'department of civil and mechanical engineering',
    'department of environmental and resource engineering', 'institut for byggeri og anlæg',
    'byg dtu', 'kgs lyngby', 'lyngby', 'denmark', 'danmark', 'sisimiut', 'greenland',
    'grønland',
), key=len, reverse=True)
FILLER_WORDS = {'of', 'the', 'and', 'og', 'for', 'i', 'at', 'ved'}
REPORT_NUMBER_LINE_RE = re.compile(r'^(?:report|rapport|r|no|nr|number)?[\s.]*(?:no|nr)?[\s.:]*[\d\s\-/.]+$',
                                   re.IGNORECASE)
# Characters that aren't allowed in XML 1.0 (pdftotext copies them from broken PDFs).
_XML_INVALID_RE = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f]')


@dataclass
class StudyNumber:
    number: str  # lower case
    persons: list = field(default_factory=list)  # [(pk, full name)] of Persons with this id_number


@dataclass
class PdfSuggestions:
    path: str
    has_text_layer: bool = False
    title: str = ''
    title_candidates: list = field(default_factory=list)  # [title, ...], best first
    year: int | None = None
    year_source: str = ''  # 'file name', 'month', 'institution', 'frequent'
    year_candidates: list = field(default_factory=list)  # [(year, source), ...], best first
    study_numbers: list = field(default_factory=list)  # [StudyNumber, ...]
    error: str = ''  # what went wrong with this file ('' if nothing)


class PdfTextError(Exception):
    """pdftotext failed for a file (message for the operator)."""


def run_pdftotext(path, args, timeout=DEFAULT_TIMEOUT):
    """stdout of ``pdftotext <args> <path> -`` as text. Raises ``PdfTextError``."""
    try:
        result = subprocess.run(
            [PDFTOTEXT, *args, '-enc', 'UTF-8', path, '-'],
            capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError:
        raise PdfTextError(f'{PDFTOTEXT} not found (poppler-utils)')
    except subprocess.TimeoutExpired:
        raise PdfTextError(f'{PDFTOTEXT} timed out after {timeout} s')
    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', 'replace').strip().splitlines()
        detail = stderr[-1] if stderr else 'no message'
        raise PdfTextError(f'{PDFTOTEXT} failed (exit {result.returncode}): {detail}')
    return result.stdout.decode('utf-8', 'replace')


def normalize_text(text):
    """Lower case, words only (punctuation and underscores as spaces), single spaces."""
    return ' '.join(re.sub(r'[\W_]+', ' ', text or '').lower().split())


def two_digit_year(yy, today=None):
    """``yy`` (0-99) as a four-digit year: up to the current year's two digits 20YY, else
    19YY."""
    current = (today or datetime.date.today()).year
    return 2000 + yy if yy <= current % 100 else 1900 + yy


def year_from_file_name(name, today=None):
    """The year of the first report number ``YY-NN`` in the base name of ``name``, or None."""
    base = name.replace('\\', '/').rsplit('/', 1)[-1]
    match = FILE_NAME_NUMBER_RE.search(base)
    return two_digit_year(int(match.group(1)), today) if match else None


def _valid_year(year, today=None):
    return MIN_YEAR <= year <= (today or datetime.date.today()).year + 1


def year_candidates(front_page, file_name='', today=None):
    """``[(year, source), ...]``, best first, each year once (see the module docstring)."""
    found = []

    def add(year, source):
        if year is not None and _valid_year(year, today) and year not in [y for y, _ in found]:
            found.append((year, source))

    add(year_from_file_name(file_name, today) if file_name else None, 'file name')
    lines = front_page.splitlines()
    for regex, source in ((MONTH_RE, 'month'), (INSTITUTION_LINE_RE, 'institution')):
        for line in lines:
            if regex.search(line):
                for match in YEAR_RE.finditer(line):
                    add(int(match.group(1)), source)
    counts = Counter(int(y) for y in YEAR_RE.findall(front_page) if _valid_year(int(y), today))
    for year, _ in sorted(counts.items(), key=lambda item: (-item[1], -item[0])):
        add(year, 'frequent')
    return found


def find_study_numbers(text):
    """The study numbers in ``text``, lower case, each once, in order of appearance."""
    seen = []
    for match in STUDY_NUMBER_RE.finditer(text):
        number = match.group(0).lower()
        if number not in seen:
            seen.append(number)
    return seen


def match_persons(numbers):
    """``{number: [(pk, full name), ...]}`` for the study numbers (lower case): the Persons
    whose ``id_number`` equals the number, ignoring case. One query; read-only."""
    from publications.models import Person

    matches = {number: [] for number in numbers}
    if not numbers:
        return matches
    persons = (Person.objects.annotate(id_lower=Lower('id_number'))
               .filter(id_lower__in=list(numbers)).order_by('pk'))
    for person in persons:
        matches[person.id_lower].append((person.pk, person.get_full_name()))
    return matches


def is_skipped_title_line(text):
    """True for a line that can't be a title: only an institution name, only a year, a
    number or a study number, or a report-number line."""
    words = normalize_text(STUDY_NUMBER_RE.sub(' ', text))
    if not re.search(r'[^\W\d_]', words):  # no letter at all
        return True
    if REPORT_NUMBER_LINE_RE.match(text.strip()):
        return True
    rest = f' {words} '
    for phrase in INSTITUTION_PHRASES:
        rest = rest.replace(f' {phrase} ', ' ')
    remaining = [w for w in rest.split() if w not in FILLER_WORDS and not w.isdigit()]
    return not remaining


def bbox_lines(xhtml):
    """``[(height, text), ...]`` of the first page in pdftotext's ``-bbox-layout`` output,
    in its reading order."""
    root = ET.fromstring(_XML_INVALID_RE.sub('', xhtml))
    lines = []
    page = next((el for el in root.iter() if el.tag.rsplit('}', 1)[-1] == 'page'), None)
    if page is None:
        return lines
    for el in page.iter():
        if el.tag.rsplit('}', 1)[-1] != 'line':
            continue
        words = [(w.text or '').strip() for w in el
                 if w.tag.rsplit('}', 1)[-1] == 'word']
        text = ' '.join(w for w in words if w)
        if not text:
            continue
        height = float(el.get('yMax', 0)) - float(el.get('yMin', 0))
        lines.append((height, text))
    return lines


def title_groups(lines):
    """Titles from ``[(height, text), ...]``: runs of consecutive (not skipped) lines of
    nearly the same height, joined, ordered by height (largest first)."""
    groups = []  # [height, [texts]]
    for height, text in lines:
        if height <= 0 or is_skipped_title_line(text):
            if groups:
                groups.append(None)  # a skipped line ends the run
            continue
        last = groups[-1] if groups else None
        if last is not None and abs(height - last[0]) <= TITLE_HEIGHT_TOLERANCE * last[0]:
            last[1].append(text)
        else:
            groups.append([height, [text]])
    groups = [g for g in groups if g is not None]
    groups.sort(key=lambda g: -g[0])  # stable: same height keeps reading order
    titles = []
    for _, texts in groups:
        title = ' '.join(' '.join(texts).split())
        if title not in titles:
            titles.append(title)
    return titles


def extract_pdf_metadata(path, pages=DEFAULT_PAGES, file_name=None, timeout=DEFAULT_TIMEOUT,
                         lookup_persons=True):
    """Suggestions for the PDF at ``path`` (absolute path) from its first ``pages`` pages.

    ``file_name`` (default: ``path``) is the name the year is read from. Problems with the file
    (broken PDF, timeout, pdftotext missing) are reported in ``error``; this function doesn't
    raise for them. ``lookup_persons=False`` skips the Person lookup (no queries).
    """
    result = PdfSuggestions(path=path)
    pages = max(1, int(pages))
    try:
        text = run_pdftotext(path, ['-f', '1', '-l', str(pages), '-layout'], timeout)
    except PdfTextError as exc:
        result.error = str(exc)
        return result

    if sum(ch.isalnum() for ch in text) < MIN_TEXT_CHARS:
        result.has_text_layer = False
        return result
    result.has_text_layer = True
    front_page = text.split('\f', 1)[0]

    numbers = find_study_numbers(text)
    matches = match_persons(numbers) if lookup_persons else {n: [] for n in numbers}
    result.study_numbers = [StudyNumber(n, matches[n]) for n in numbers]

    result.year_candidates = year_candidates(front_page, path if file_name is None else file_name)
    if result.year_candidates:
        result.year, result.year_source = result.year_candidates[0]

    try:
        xhtml = run_pdftotext(path, ['-f', '1', '-l', '1', '-bbox-layout'], timeout)
        titles = title_groups(bbox_lines(xhtml))
    except PdfTextError as exc:
        result.error = f'title: {exc}'
        titles = []
    except ET.ParseError as exc:
        result.error = f'title: unreadable pdftotext layout output ({exc})'
        titles = []
    result.title_candidates = titles[:TITLE_CANDIDATES]
    result.title = titles[0] if titles else ''
    return result
