"""Excel import of features with a preview (plan "features" T10, roadmap FA-R63).

Three steps (views in views.py):

1. Upload: ``parse_workbook`` reads the sheet ``Features`` in memory (openpyxl, read-only; the
   upload is never written to MEDIA_ROOT) and checks every row. A sheet with more than
   ``MAX_VERTICES`` vertex rows is refused here (``ImportTooLarge``).
2. Preview: the parsed result is kept in the session (``store``), keyed by a random import
   id. The page shows every feature on the map, a table with the status per feature and the
   problems by sheet row. Errors block the import; warnings (outside Greenland, a feature
   that looks imported before, ...) don't.
3. Import: ``save_import`` creates all features in one transaction, after ``recheck`` has
   checked again that every report exists and the user may still add features to it.
   Nothing is saved before this step.

The sheet (template ``static/publications/docs/ARTEK_feature_list.xlsx``, made by
``manage.py make_feature_import_template`` from ``COLUMNS``):

- Columns by name, not by position; names are not case-sensitive, spaces count as ``_``;
  aliases in ``COLUMNS`` (``Report`` = ``Publication_ID``, ``UTMX/LON`` = ``X``, ...).
- One row per vertex. Rows with the same ``Feature#`` (per report) form one feature; its
  first row gives the attributes. ``Geometry_type`` point / line / polygon; several rows of
  a point feature make one MultiPoint, a polygon ring is closed automatically.
- ``SRID``: any EPSG code PROJ knows (``geometry.parse_srid``); empty on a later row of a
  feature = the feature's SRID; another SRID within one feature is an error.
- ``Date`` (required) and ``Observation_date`` (optional): a date cell or ISO text
  ``YYYY-MM-DD``; anything else is an error (no guessing).
- ``Report``: the report number (e.g. ``25-07``). Import from a report page: optional; when
  given it must be that report's number. Import from the Administration page: required; the
  user needs ``add_feature`` on every report (permissions.ADD_FEATURE); a report that does not
  exist or that the user may not edit is a row error (one message for both, so that the
  existence of a hidden report is not revealed).

A feature with the same report, name and geometry as an existing feature is a warning
("imported before?"), not an error: it is still imported.
"""
import datetime
import io
import json
import re
import secrets
import time
import zipfile
from dataclasses import dataclass, field

import openpyxl
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction

from publications.geometry import (
    FEATURE_COLUMNS, GeometryError, from_vertices, parse_srid, plausibility_warnings,
    same_geometry,
)
from publications.models import Feature, Publication
from publications.permissions import ADD_FEATURE, user_may

SHEET_NAME = 'Features'
HELP_SHEET = 'Help'
TEMPLATE_STATIC_PATH = 'publications/docs/ARTEK_feature_list.xlsx'

MAX_VERTICES = 2000          # vertex rows per upload; more is an error at step 1
MAX_FILE_MB = 5              # upload size; a sheet of MAX_VERTICES rows is far below
SESSION_KEY = 'feature_imports'
SESSION_MAX_AGE = 2 * 3600   # seconds an import waits in the session for "Import"
SESSION_MAX_IMPORTS = 3      # imports kept per session (the oldest is dropped)

TEXT_MAX_LENGTH = 100        # name, area, direction (model max_length)
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


@dataclass(frozen=True)
class Column:
    key: str
    header: str               # as in the template
    aliases: tuple            # other accepted names (lower case)
    required: str             # 'yes', 'no', or a note shown on the Help sheet
    help: str


COLUMNS = (
    Column('report', 'Report', ('publication_id', 'report_number'),
           'from the Administration page',
           'Report number, e.g. 25-07 (format the column as Text, or Excel may turn it into '
           'a date). Import from a report page: may be empty; if given, it must be that '
           "report's number. Import from the Administration page: required on every row; "
           'you must be allowed to add features to each report named. Publication_ID is '
           'accepted as column name (it holds the report number too).'),
    Column('feature_no', 'Feature#', ('feature_no', 'feature_number', 'feature'), 'yes',
           'Feature number or label, e.g. 1, 2, 3 or A, B. All rows with the same Feature# '
           '(of the same report) form one feature: one row per vertex.'),
    Column('type', 'Feature_type', ('type',), 'yes (first row)',
           'Photo, Sample, Borehole, Geophysical data, Field measurement, Lab measurement, '
           'Resource or Other (case does not matter).'),
    Column('name', 'Name', (), 'yes (first row)', 'Name of the feature, at most 100 '
           'characters.'),
    Column('geometry_type', 'Geometry_type', ('geometry',), 'yes (first row)',
           'point, line or polygon. Several rows of a point feature make one multi-point '
           'feature; a line needs at least 2 rows, a polygon at least 3 (the ring is closed '
           'automatically). Later rows may leave it empty.'),
    Column('srid', 'SRID', ('epsg',), 'yes (first row)',
           'EPSG code of the coordinates, e.g. 4326 or EPSG:32622 (list below). Later rows '
           'of a feature may leave it empty; a different code within one feature is an '
           'error.'),
    Column('x', 'UTMX/LON', ('x',), 'yes',
           'Easting in metres (UTM) or longitude in decimal degrees (west is negative, e.g. '
           '-51.7). Use a decimal point.'),
    Column('y', 'UTMY/LAT', ('y',), 'yes',
           'Northing in metres (UTM) or latitude in decimal degrees (e.g. 64.2).'),
    Column('pos_quality', 'Pos_quality', ('position_quality',), 'no',
           'GPS (phase), GPS (code), Approximate or Unknown (default when empty).'),
    Column('date', 'Date', (), 'yes (first row)',
           'Date of the observation or measurement: a date cell, or text YYYY-MM-DD '
           '(e.g. 2025-07-14). Other formats are an error.'),
    Column('observation_date', 'Observation_date', ('gnss_observation_date',), 'no',
           'GNSS observation date (basis for epoch calculations), same format as Date. '
           'Empty: the feature date is used.'),
    Column('area', 'Area', (), 'no', 'General area or location, at most 100 characters.'),
    Column('direction', 'Direction', (), 'no', 'Direction or orientation, at most 100 '
           'characters.'),
    Column('description', 'Description', (), 'no', 'Description of the feature.'),
    Column('comment', 'Comment', (), 'no', 'Comment.'),
)
COLUMN_BY_KEY = {column.key: column for column in COLUMNS}
REQUIRED_KEYS = ('feature_no', 'type', 'name', 'geometry_type', 'srid', 'x', 'y', 'date')
ATTRIBUTE_KEYS = ('name', 'type', 'area', 'date', 'observation_date', 'direction',
                  'description', 'comment', 'pos_quality')


def _normalise_header(text):
    return re.sub(r'\s+', '_', text.strip().lower())


HEADER_ALIASES = {}
for _column in COLUMNS:
    for _name in (_column.header, _column.key, *_column.aliases):
        HEADER_ALIASES[_normalise_header(_name)] = _column.key


class ImportTooLarge(Exception):
    """The sheet has more than MAX_VERTICES vertex rows (refused at step 1)."""


class ImportFileError(Exception):
    """The file can't be read as an Excel workbook; the message is for the user."""


# --- Cells -----------------------------------------------------------------------------------

def _cell_text(value):
    """The text of a cell (None gives ''); whole floats lose their '.0'."""
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def parse_date(value):
    """A date from a date cell or ISO text; None for an empty cell; ValueError otherwise."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = _cell_text(value)
    if not text:
        return None
    if DATE_RE.match(text):
        try:
            return datetime.date.fromisoformat(text)
        except ValueError:
            pass
    raise ValueError(f'"{text}" is not a date; use a date cell or YYYY-MM-DD.')


def _choice(text, choices):
    """The stored value of ``choices`` matching ``text`` (value or label, any case, '_' as
    space), or None."""
    wanted = text.replace('_', ' ').strip().lower()
    for value, label in choices:
        if wanted in (value.lower(), label.lower()):
            return value
    return None


# --- Parsed result ---------------------------------------------------------------------------

@dataclass
class ParsedFeature:
    """One feature of the sheet: its rows, attributes, geometry and problems."""
    feature_no: str
    report_key: str
    rows: list = field(default_factory=list)              # sheet row numbers
    report: Publication = None
    report_number: str = ''
    attrs: dict = field(default_factory=dict)
    kind: str = ''
    srid: int = None
    vertices: list = field(default_factory=list)
    result: object = None                                 # GeometryResult
    errors: list = field(default_factory=list)            # (row, text)
    warnings: list = field(default_factory=list)          # (row, text)

    @property
    def first_row(self):
        return self.rows[0]

    def error(self, row, text):
        self.errors.append((row, text))

    def warning(self, row, text):
        if (row, text) not in self.warnings:
            self.warnings.append((row, text))


@dataclass
class ParseResult:
    features: list = field(default_factory=list)
    errors: list = field(default_factory=list)            # file-level (row, text); row 0 = sheet
    warnings: list = field(default_factory=list)
    vertex_count: int = 0


class _Parser:

    def __init__(self, user, report=None):
        self.user = user
        self.report = report                  # import from this report's page, else None
        self.result = ParseResult()
        self._reports = {}                    # number -> (Publication or None, problem)

    # ---- reports

    def lookup_report(self, number):
        """(report, problem) for a report number of the sheet (administration import)."""
        if number not in self._reports:
            reports = list(Publication.objects.filter(number=number)[:2])
            if len(reports) == 1 and user_may(self.user, ADD_FEATURE, reports[0]):
                self._reports[number] = (reports[0], None)
            else:
                self._reports[number] = (None, f"report '{number}' does not exist or you may "
                                               f"not add features to it.")
        return self._reports[number]

    # ---- sheet

    def read(self, workbook):
        sheet = next((ws for ws in workbook.worksheets
                      if ws.title.strip().lower() == SHEET_NAME.lower()), None)
        if sheet is None:
            self.result.errors.append((0, f"The file has no sheet named '{SHEET_NAME}'."))
            return self.result
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)
        columns = self.read_header(header or ())
        if columns is None:
            return self.result

        features = {}
        for row_number, cells in enumerate(rows, start=2):
            values = {}
            for key, value in zip(columns, cells):
                if key is not None:
                    values[key] = value
            if all(_cell_text(value) == '' for value in values.values()):
                continue   # blank row
            self.result.vertex_count += 1
            if self.result.vertex_count > MAX_VERTICES:
                raise ImportTooLarge(
                    f'The sheet has more than {MAX_VERTICES} vertex rows; split it into '
                    f'several files.')
            self.read_row(row_number, values, features)

        if not features and not self.result.errors:
            self.result.errors.append((0, f"Sheet '{SHEET_NAME}' has no features."))
        for feature in features.values():
            self.build(feature)
        self.result.features = sorted(features.values(), key=lambda f: f.first_row)
        return self.result

    def read_header(self, header):
        columns, unknown, missing = [], [], []
        for value in header:
            text = _cell_text(value)
            key = HEADER_ALIASES.get(_normalise_header(text)) if text else None
            if text and key is None:
                unknown.append(text)
            if key is not None and key in columns:
                self.result.errors.append((1, f"column '{COLUMN_BY_KEY[key].header}' is given "
                                              f"twice."))
            columns.append(key)
        if unknown:
            self.result.warnings.append((1, f"unknown columns ignored: {', '.join(unknown)}."))
        required = REQUIRED_KEYS if self.report is not None else ('report',) + REQUIRED_KEYS
        missing = [COLUMN_BY_KEY[key].header for key in required if key not in columns]
        if missing:
            self.result.errors.append((1, f"required columns missing: {', '.join(missing)}."))
        if missing or any(row == 1 for row, _text in self.result.errors):
            return None
        return columns

    def read_row(self, row_number, values, features):
        """Add the row to its feature (new feature: the row's attributes too)."""
        report_cell = values.get('report')
        if isinstance(report_cell, (datetime.date, datetime.datetime)):
            self.result.errors.append((row_number, 'the report number was read as a date by '
                                                   'Excel; format the column as Text.'))
            return
        report_number = _cell_text(report_cell)
        feature_no = _cell_text(values.get('feature_no'))
        if not feature_no:
            self.result.errors.append((row_number, 'Feature# is empty.'))
            return

        if self.report is not None:
            if report_number and report_number != self.report.number:
                self.result.errors.append(
                    (row_number, f"report '{report_number}' is not this report "
                                 f"({self.report.number}); leave the column empty or remove "
                                 f"the row."))
                return
            report_key, report, problem = self.report.number, self.report, None
        else:
            if not report_number:
                self.result.errors.append((row_number, 'the report number is empty.'))
                return
            report, problem = self.lookup_report(report_number)
            report_key = report_number

        key = (report_key, feature_no)
        feature = features.get(key)
        if feature is None:
            feature = ParsedFeature(feature_no=feature_no, report_key=report_key,
                                    report=report, report_number=report_key)
            features[key] = feature
            feature.rows.append(row_number)
            if problem:
                feature.error(row_number, problem)
            self.read_attributes(feature, row_number, values)
        else:
            feature.rows.append(row_number)
            self.read_continuation(feature, row_number, values)
        self.read_vertex(feature, row_number, values)

    def read_attributes(self, feature, row, values):
        attrs = feature.attrs
        name = _cell_text(values.get('name'))
        if not name:
            feature.error(row, 'Name is empty.')
        attrs['name'] = name

        type_text = _cell_text(values.get('type'))
        attrs['type'] = _choice(type_text, Feature.feature_types) if type_text else None
        if attrs['type'] is None:
            valid = ', '.join(label for _value, label in Feature.feature_types)
            feature.error(row, f"Feature_type '{type_text}' is not valid; use one of: {valid}."
                          if type_text else f'Feature_type is empty; use one of: {valid}.')

        quality_text = _cell_text(values.get('pos_quality'))
        attrs['pos_quality'] = (_choice(quality_text, Feature.pos_qualities)
                                if quality_text else 'Unknown')
        if attrs['pos_quality'] is None:
            valid = ', '.join(label for _value, label in Feature.pos_qualities)
            feature.error(row, f"Pos_quality '{quality_text}' is not valid; use one of: "
                               f"{valid}.")

        for key in ('area', 'direction', 'description', 'comment'):
            attrs[key] = _cell_text(values.get(key))
        for key in ('name', 'area', 'direction'):
            if len(attrs[key]) > TEXT_MAX_LENGTH:
                feature.error(row, f'{COLUMN_BY_KEY[key].header} is longer than '
                                   f'{TEXT_MAX_LENGTH} characters.')

        for key, required in (('date', True), ('observation_date', False)):
            header = COLUMN_BY_KEY[key].header
            try:
                attrs[key] = parse_date(values.get(key))
            except ValueError as error:
                attrs[key] = None
                feature.error(row, f'{header}: {error}')
                continue
            if attrs[key] is None and required:
                feature.error(row, f'{header} is empty (required).')

        kind = _cell_text(values.get('geometry_type')).lower()
        if kind not in ('point', 'line', 'polygon'):
            feature.error(row, f"Geometry_type '{kind}' is not valid; use point, line or "
                               f"polygon." if kind else
                               'Geometry_type is empty; use point, line or polygon.')
            kind = ''
        feature.kind = kind

        srid_text = _cell_text(values.get('srid'))
        if not srid_text:
            feature.error(row, 'SRID is empty.')
        else:
            try:
                feature.srid = parse_srid(srid_text)
            except GeometryError as error:
                feature.error(row, f'SRID: {error}')

    def read_continuation(self, feature, row, values):
        """A later row of a feature: geometry type and SRID must agree (or be empty)."""
        kind = _cell_text(values.get('geometry_type')).lower()
        if kind and feature.kind and kind != feature.kind:
            feature.error(row, f"Geometry_type '{kind}' differs from '{feature.kind}' in row "
                               f"{feature.first_row} (same Feature#).")
        srid_text = _cell_text(values.get('srid'))
        if srid_text and feature.srid is not None:
            try:
                srid = parse_srid(srid_text)
            except GeometryError as error:
                feature.error(row, f'SRID: {error}')
                return
            if srid != feature.srid:
                feature.error(row, f'SRID {srid} differs from {feature.srid} in row '
                                   f'{feature.first_row}: all rows of a feature need the same '
                                   f'SRID.')

    def read_vertex(self, feature, row, values):
        coords = []
        for key in ('x', 'y'):
            value = values.get(key)
            header = COLUMN_BY_KEY[key].header
            text = _cell_text(value)
            if not text:
                feature.error(row, f'{header} is empty.')
                return
            if isinstance(value, bool):
                feature.error(row, f'{header} "{text}" is not a number.')
                return
            try:
                coords.append(float(value) if isinstance(value, (int, float)) else float(text))
            except ValueError:
                feature.error(row, f'{header} "{text}" is not a number (use a decimal point).')
                return
        feature.vertices.append((row, tuple(coords)))

    # ---- geometry

    def build(self, feature):
        """The geometry (when the rows have no errors), plausibility and duplicate warnings."""
        if feature.errors or not feature.kind or feature.srid is None:
            return
        try:
            feature.result = from_vertices(feature.kind, [v for _row, v in feature.vertices],
                                           feature.srid)
        except GeometryError as error:
            feature.error(feature.first_row, f'Feature# {feature.feature_no}: {error}')
            return
        for row, (x, y) in feature.vertices:
            for text in plausibility_warnings(feature.srid, x, y):
                feature.warning(row, text)
        for text in feature.result.warnings:
            feature.warning(feature.first_row, text)
        if feature.report is not None and find_duplicate(feature.report, feature.attrs['name'],
                                                         feature.result) is not None:
            feature.warning(feature.first_row,
                            f"report {feature.report.number} already has a feature "
                            f"'{feature.attrs['name']}' with the same geometry (imported "
                            f"before?). It will be imported again.")


def find_duplicate(report, name, result):
    """An existing feature of ``report`` with ``name`` and the geometry of ``result``."""
    for existing in Feature.objects.filter(publications=report, name=name):
        if same_geometry(result, existing):
            return existing
    return None


def load_workbook(uploaded_file):
    """The workbook of an uploaded file, read in memory (read-only)."""
    try:
        data = uploaded_file.read()
        return openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError, TypeError) as error:
        raise ImportFileError('The file could not be read as an Excel (.xlsx) file.') from error


def parse_workbook(workbook, user, report=None):
    """Read and check the ``Features`` sheet of ``workbook``. ``report``: import from that
    report's page. Raises ImportTooLarge; problems are in the ParseResult."""
    try:
        return _Parser(user, report).read(workbook)
    finally:
        close = getattr(workbook, 'close', None)
        if close is not None:
            close()


# --- Session ---------------------------------------------------------------------------------

def _geojson(geom):
    def as_lists(coords):
        if isinstance(coords, (tuple, list)):
            return [as_lists(part) for part in coords]
        return coords
    # Exact coordinates (not GDAL's rounded GeoJSON), as geometry.feature_geojson.
    return {'type': geom.geom_type, 'coordinates': as_lists(geom.coords)}


def _feature_data(feature):
    result = feature.result
    attrs = dict(feature.attrs)
    for key in ('date', 'observation_date'):
        value = attrs.get(key)
        attrs[key] = value.isoformat() if value else None
    data = {
        'feature_no': feature.feature_no,
        'rows': feature.rows,
        'report_pk': feature.report.pk if feature.report is not None else None,
        'report_number': feature.report_number,
        'attrs': attrs,
        'kind': feature.kind,
        'srid': feature.srid,
        'vertex_count': len(feature.vertices),
        'geometry': None,
        'source_srid': None,
        'source_geometry': None,
        'transform_note': '',
        'errors': [list(item) for item in feature.errors],
        'warnings': [list(item) for item in feature.warnings],
    }
    if result is not None and not feature.errors:
        data['geometry'] = {column: _geojson(getattr(result, column))
                            if getattr(result, column) is not None else None
                            for column in FEATURE_COLUMNS}
        data.update(source_srid=result.source_srid, source_geometry=result.source_geometry,
                    transform_note=result.transform_note)
    return data


def session_data(parsed, user, report=None, file_name=''):
    """The JSON-serialisable form of a ParseResult kept between the steps."""
    return {
        'created': time.time(),
        'user_pk': user.pk,
        'report_pk': report.pk if report is not None else None,
        'file_name': file_name,
        'errors': [list(item) for item in parsed.errors],
        'warnings': [list(item) for item in parsed.warnings],
        'features': [_feature_data(feature) for feature in parsed.features],
    }


def store(session, data):
    """Keep ``data`` in the session; returns its new import id. Expired imports and all but
    the newest SESSION_MAX_IMPORTS are dropped."""
    imports = _live_imports(session)
    import_id = secrets.token_urlsafe(12)
    imports[import_id] = data
    for old in sorted(imports, key=lambda key: imports[key]['created'])[:-SESSION_MAX_IMPORTS]:
        del imports[old]
    session[SESSION_KEY] = imports
    return import_id


def _live_imports(session):
    imports = session.get(SESSION_KEY)
    if not isinstance(imports, dict):
        return {}
    now = time.time()
    return {key: value for key, value in imports.items()
            if isinstance(value, dict) and now - value.get('created', 0) <= SESSION_MAX_AGE}


def load(session, import_id, user):
    """The stored import ``import_id`` of ``user``, or None (unknown, expired, other user)."""
    data = _live_imports(session).get(import_id)
    if data is None or data.get('user_pk') != user.pk:
        return None
    return data


def discard(session, import_id):
    imports = _live_imports(session)
    imports.pop(import_id, None)
    session[SESSION_KEY] = imports


# --- Preview helpers and the import ----------------------------------------------------------

def problems(data):
    """Every problem as (row, level, text), sorted by sheet row (row 0/1: the sheet and its
    header)."""
    items = [(row, 'error', text) for row, text in data['errors']]
    items += [(row, 'warning', text) for row, text in data['warnings']]
    for feature in data['features']:
        items += [(row, 'error', text) for row, text in feature['errors']]
        items += [(row, 'warning', text) for row, text in feature['warnings']]
    return sorted(items, key=lambda item: (item[0], item[1] != 'error'))


def has_errors(data):
    return bool(data['errors']) or any(feature['errors'] for feature in data['features'])


def recheck(data, user):
    """Problems that block the import now: a report that was deleted, or that the user may
    no longer add features to. Returns a list of texts."""
    found = []
    pks = {feature['report_pk'] for feature in data['features']
           if feature['report_pk'] is not None}
    if data.get('report_pk') is not None:
        pks.add(data['report_pk'])
    reports = Publication.objects.in_bulk(pks)
    numbers = {feature['report_pk']: feature['report_number'] for feature in data['features']}
    for pk in sorted(pks):
        report = reports.get(pk)
        if report is None:
            found.append(f"Report {numbers.get(pk, pk)} no longer exists.")
        elif not user_may(user, ADD_FEATURE, report):
            found.append(f"You may no longer add features to report {report.number}.")
    return found


def preview_geojson(data):
    """The importable features as one GeoJSON FeatureCollection (WGS84) for the map."""
    collection = []
    for index, feature in enumerate(data['features']):
        if not feature['geometry']:
            continue
        for column, geometry in feature['geometry'].items():
            if geometry is None:
                continue
            collection.append({
                'type': 'Feature',
                'geometry': geometry,
                'properties': {'index': index, 'feature_no': feature['feature_no'],
                               'name': feature['attrs'].get('name', ''),
                               'type': feature['attrs'].get('type') or '',
                               'report': feature['report_number'],
                               'warning': bool(feature['warnings'])},
            })
    return {'type': 'FeatureCollection', 'features': collection}


def save_import(data, user):
    """Create every feature of ``data`` in one transaction; returns the new features. The
    caller has checked ``has_errors`` and ``recheck``."""
    reports = Publication.objects.in_bulk(
        {feature['report_pk'] for feature in data['features']})
    created = []
    with transaction.atomic():
        for item in data['features']:
            attrs = dict(item['attrs'])
            for key in ('date', 'observation_date'):
                attrs[key] = datetime.date.fromisoformat(attrs[key]) if attrs[key] else None
            feature = Feature(**attrs, created_by=user, modified_by=user)
            for column in FEATURE_COLUMNS:
                geometry = item['geometry'].get(column)
                setattr(feature, column,
                        GEOSGeometry(json.dumps(geometry), srid=4326) if geometry else None)
            feature.source_srid = item['source_srid']
            feature.source_geometry = item['source_geometry']
            feature.transform_note = item['transform_note']
            feature.save()
            feature.publications.add(reports[item['report_pk']])
            created.append(feature)
    return created


# --- Template --------------------------------------------------------------------------------

TEMPLATE_EXAMPLES = (
    # Report, Feature#, Feature_type, Name, Geometry_type, SRID, X, Y, Pos_quality, Date,
    # Observation_date, Area, Direction, Description, Comment (all made up)
    ('25-07', '1', 'Sample', 'Sample S1', 'point', 4326, -51.7210, 64.1830, 'GPS (code)',
     '2025-07-14', None, 'Example area', None, 'A point in WGS84 longitude/latitude.', None),
    ('25-07', '2', 'Field measurement', 'Profile P1', 'line', 32622, 465200.0, 7118500.0,
     'GPS (phase)', '2025-07-15', '2025-07-15', 'Example area', 'NE', 'A line in WGS84 / UTM '
     'zone 22N: one row per vertex.', None),
    ('25-07', '2', None, None, None, None, 465350.0, 7118640.0, None, None, None, None, None,
     None, None),
    ('25-07', '2', None, None, None, None, 465510.0, 7118700.0, None, None, None, None, None,
     None, None),
    ('25-07', '3', 'Other', 'Survey area A', 'polygon', 4326, -51.7300, 64.1800, 'Approximate',
     '2025-07-16', None, 'Example area', None, 'A polygon; the ring is closed automatically.',
     'Made-up example'),
    ('25-07', '3', None, None, None, None, -51.7200, 64.1800, None, None, None, None, None,
     None, None),
    ('25-07', '3', None, None, None, None, -51.7200, 64.1850, None, None, None, None, None,
     None, None),
    ('25-07', '3', None, None, None, None, -51.7300, 64.1850, None, None, None, None, None,
     None, None),
)

TEMPLATE_WIDTHS = (10, 10, 18, 22, 14, 10, 14, 14, 14, 12, 16, 18, 10, 40, 30)

HELP_RULES = (
    ('All or nothing', 'Nothing is saved when you upload the file: the next page shows every '
     'feature on a map, a table with its status and every problem with its row number. Only '
     '"Import" saves, all features at once. If any row has an error, nothing can be imported: '
     'correct the file and upload it again.'),
    ('One row per vertex', 'Rows with the same Feature# (and report) form one feature, in '
     'row order. The first row gives the name, type, dates and other attributes; later rows '
     'only need Feature# (and Report), UTMX/LON and UTMY/LAT.'),
    ('Coordinates', 'x is the easting or longitude, y the northing or latitude, in the '
     'reference system of the SRID column. They are stored as entered (with the SRID) and as '
     'WGS84 longitude/latitude for the maps. GR96 to WGS84 is approximate (~1 m).'),
    ('Warnings', 'Coordinates outside Greenland, values that look swapped and a feature that '
     'looks imported before (same report, name and geometry) are shown as warnings; they do '
     'not stop the import.'),
    ('Column names', f"Not case-sensitive, by name (any order). The sheet must be named "
     f"'{SHEET_NAME}'. Aliases: Publication_ID for Report, X for UTMX/LON, Y for UTMY/LAT. "
     f"Unknown columns are ignored with a warning."),
    ('Size', f'At most {MAX_VERTICES} vertex rows and {MAX_FILE_MB} MB per file.'),
)


def build_template_workbook():
    """The template workbook: sheet Features (headers and made-up examples) and Help."""
    from openpyxl.styles import Alignment, Font

    from publications.forms.feature import GREENLAND_SRIDS

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME
    sheet.append([column.header for column in COLUMNS])
    for example in TEMPLATE_EXAMPLES:
        sheet.append(list(example))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for index, width in enumerate(TEMPLATE_WIDTHS, start=1):
        sheet.column_dimensions[openpyxl.utils.get_column_letter(index)].width = width
    for row in sheet.iter_rows(min_row=2, min_col=1, max_col=2):
        for cell in row:
            cell.number_format = '@'   # report number and Feature# as text
    sheet.freeze_panes = 'A2'

    help_sheet = workbook.create_sheet(HELP_SHEET)
    help_sheet.append(['Column', 'Required?', 'What to write'])
    for column in COLUMNS:
        names = ', '.join(alias for alias in column.aliases if alias != column.key)
        text = column.help + (f' Also accepted as column name: {names}.'
                              if names and column.key != 'report' else '')
        help_sheet.append([column.header, column.required, text])
    help_sheet.append([])
    help_sheet.append(['Rules'])
    for title, text in HELP_RULES:
        help_sheet.append([title, None, text])
    help_sheet.append([])
    help_sheet.append(['SRID', None, 'Reference systems used in Greenland (any other EPSG code '
                                     'works too). UTM zone by longitude: zone = floor((lon + '
                                     '180) / 6) + 1, e.g. -51.7 is zone 22.'])
    for code, name in GREENLAND_SRIDS:
        help_sheet.append([code, None, name])
    for row in help_sheet.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical='top')
    help_sheet['A1'].font = help_sheet['B1'].font = help_sheet['C1'].font = Font(bold=True)
    for cell in help_sheet['A']:
        if cell.value in ('Rules', 'SRID'):
            cell.font = Font(bold=True)
    for letter, width in (('A', 18), ('B', 18), ('C', 100)):
        help_sheet.column_dimensions[letter].width = width
    return workbook
