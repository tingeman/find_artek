"""Excel import of features with a preview (plan "features" T10, roadmap FA-R63).

- Parsing (publications.feature_import): column aliases, case-insensitive headers, missing
  columns, dates (date cell or ISO text only), SRIDs (unknown, mixed within a feature), too
  few vertices, polygon closed automatically, several point rows -> MultiPoint, optional
  Observation_date, feature type and position quality, warnings outside Greenland.
- Steps: upload -> preview saves nothing; "Import" saves every feature in one transaction
  (a failure saves nothing; a sheet with an error has no import button and the confirm step
  refuses); cancel; unknown, expired or another user's import id; size limit; a second
  import of the same sheet is a warning per feature; the confirm step checks the reports
  again.
- Entry points: the report page (Report column optional, must match) and the Administration
  page (add_feature on every report of the sheet).
- Access matrix of the four views; the report page button; the Administration tile.
- The template workbook: both sheets, headers the parser accepts, examples import cleanly.

Sheets are built in memory with openpyxl; every value is made up.
"""
import datetime
import io
import re
from unittest import mock

import openpyxl
from django.contrib.messages import get_messages
from django.contrib.staticfiles import finders
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from publications import feature_import
from publications.forms.feature import GREENLAND_SRIDS
from publications.geometry import from_vertices
from publications.models import Authorship, Feature, Publication
from publications.test_factories import app_path, page_path
from publications.test_feature_source_fields import stored_wkt
from publications.test_write_access import WriteAccessTestBase
from publications.views_feature_import import EXPIRED_MESSAGE

HEADERS = ['Report', 'Feature#', 'Feature_type', 'Name', 'Geometry_type', 'SRID', 'UTMX/LON',
           'UTMY/LAT', 'Pos_quality', 'Date']
DAY = '2025-07-14'


def row(report, no, x, y, *, type='Sample', name=None, kind='point', srid=4326,
        quality='GPS (code)', date=DAY):
    """A row in HEADERS order; ``name`` defaults to 'F<no>'."""
    return [report, no, type, f'F{no}' if name is None else name, kind, srid, x, y, quality,
            date]


def cont(report, no, x, y, srid=None):
    """A continuation row: only report, Feature#, (SRID) and coordinates."""
    return [report, no, None, None, None, srid, x, y, None, None]


def xlsx(rows, headers=HEADERS, sheet='Features'):
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.title = sheet
    ws.append(headers)
    for values in rows:
        ws.append(values)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def upload_file(rows, headers=HEADERS, name='features.xlsx', **kwargs):
    return SimpleUploadedFile(
        name, xlsx(rows, headers, **kwargs),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def parse(rows, user, headers=HEADERS, report=None, sheet='Features'):
    workbook = openpyxl.load_workbook(io.BytesIO(xlsx(rows, headers, sheet)), read_only=True,
                                      data_only=True)
    return feature_import.parse_workbook(workbook, user, report=report)


def all_errors(parsed):
    found = list(parsed.errors)
    for feature in parsed.features:
        found += feature.errors
    return found


def all_warnings(parsed):
    found = list(parsed.warnings)
    for feature in parsed.features:
        found += feature.warnings
    return found


# A line in WGS84 / UTM zone 22N and a polygon ring near Nuuk (made up).
LINE_UTM = [(465200.0, 7118500.0), (465350.0, 7118640.0), (465510.0, 7118700.0)]
RING = [(-51.73, 64.18), (-51.72, 64.18), (-51.72, 64.185), (-51.73, 64.185)]


class FeatureImportTestBase(WriteAccessTestBase):
    """cls.pub 99-01 (author cls.dtu_own), cls.other_pub 99-02 (verified, nobody listed)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_pub = Publication.objects.create(
            type=cls.pubtype, title='Other report', number='99-02', year=1999, verified=True)

    def messages_of(self, response):
        return [str(message) for message in get_messages(response.wsgi_request)]

    def report_import_path(self, pub=None):
        return page_path('import_report_features', pk=(pub or self.pub).pk)

    def admin_import_path(self):
        return page_path('import_features')

    def upload(self, path, rows, headers=HEADERS, **kwargs):
        return self.client.post(path, {'file': upload_file(rows, headers, **kwargs)})

    def import_id_of(self, response):
        self.assertEqual(response.status_code, 302, getattr(response, 'content', b'')[:2000])
        match = re.search(r'/features/import/([A-Za-z0-9_-]+)/$', response['Location'])
        self.assertIsNotNone(match, response['Location'])
        return match[1]

    def preview_path(self, import_id):
        return page_path('import_features_preview', import_id=import_id)

    def confirm_path(self, import_id):
        return page_path('import_features_confirm', import_id=import_id)

    def stored_imports(self):
        return self.client.session.get(feature_import.SESSION_KEY, {})


# --- Parsing ---------------------------------------------------------------------------------

class ParseTests(FeatureImportTestBase):

    def test_point_line_polygon(self):
        rows = [row('99-01', 1, -51.7, 64.18),
                row('99-01', 2, *LINE_UTM[0], kind='line', srid=32622),
                cont('99-01', 2, *LINE_UTM[1]), cont('99-01', 2, *LINE_UTM[2], srid=32622),
                row('99-01', 3, *RING[0], kind='polygon')]
        rows += [cont('99-01', 3, *vertex) for vertex in RING[1:]]
        parsed = parse(rows, self.editor)
        self.assertEqual(all_errors(parsed), [])
        self.assertEqual(all_warnings(parsed), [])
        point, line, polygon = parsed.features
        self.assertEqual((point.feature_no, point.rows, point.kind), ('1', [2], 'point'))
        self.assertEqual(line.rows, [3, 4, 5])
        self.assertEqual(line.result.source_srid, 32622)
        self.assertEqual(len(line.result.lines[0]), 3)
        self.assertEqual(polygon.report, self.pub)
        self.assertEqual(point.attrs['type'], Feature.SAMPLE)
        self.assertEqual(point.attrs['date'], datetime.date(2025, 7, 14))
        self.assertIsNone(point.attrs['observation_date'])

    def test_aliases_and_case_insensitive_headers_in_any_order(self):
        headers = ['y', 'X', 'publication_id', 'FEATURE#', 'feature type', 'NAME',
                   'geometry_type', 'Epsg', 'date']
        rows = [[64.18, -51.7, '99-01', 'A', 'field_measurement', 'Pt', 'Point', 'EPSG:4326',
                 DAY]]
        parsed = parse(rows, self.editor, headers=headers)
        self.assertEqual(all_errors(parsed), [])
        feature, = parsed.features
        self.assertEqual(feature.attrs['type'], Feature.FIELD_MEASUREMENT)
        self.assertEqual(feature.attrs['pos_quality'], 'Unknown')   # column absent
        self.assertAlmostEqual(feature.result.points[0].x, -51.7)
        self.assertAlmostEqual(feature.result.points[0].y, 64.18)

    def test_sheet_name_is_not_case_sensitive_and_required(self):
        parsed = parse([row('99-01', 1, -51.7, 64.18)], self.editor, sheet='features')
        self.assertEqual(all_errors(parsed), [])
        parsed = parse([row('99-01', 1, -51.7, 64.18)], self.editor, sheet='Sheet1')
        self.assertEqual(parsed.features, [])
        self.assertIn("no sheet named 'Features'", parsed.errors[0][1])

    def test_missing_required_columns(self):
        headers = [h for h in HEADERS if h not in ('Date', 'SRID')]
        parsed = parse([['99-01', 1, 'Sample', 'F', 'point', -51.7, 64.18, 'Unknown']],
                       self.editor, headers=headers)
        self.assertEqual(parsed.features, [])
        (row_number, text), = parsed.errors
        self.assertEqual(row_number, 1)
        self.assertIn('required columns missing: SRID, Date', text)

    def test_report_column_required_only_in_the_administration_import(self):
        headers = HEADERS[1:]
        rows = [row('99-01', 1, -51.7, 64.18)[1:]]
        parsed = parse(rows, self.editor, headers=headers)
        self.assertIn('Report', parsed.errors[0][1])
        parsed = parse(rows, self.editor, headers=headers, report=self.pub)
        self.assertEqual(all_errors(parsed), [])

    def test_unknown_columns_are_a_warning(self):
        parsed = parse([row('99-01', 1, -51.7, 64.18) + ['x']], self.editor,
                       headers=HEADERS + ['Colour'])
        self.assertEqual(all_errors(parsed), [])
        self.assertIn('unknown columns ignored: Colour', parsed.warnings[0][1])

    def test_dates(self):
        cases = [
            (datetime.datetime(2025, 7, 14), datetime.date(2025, 7, 14)),   # date cell
            ('2025-07-14', datetime.date(2025, 7, 14)),
            (' 2025-07-14 ', datetime.date(2025, 7, 14)),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                parsed = parse([row('99-01', 1, -51.7, 64.18, date=value)], self.editor)
                self.assertEqual(all_errors(parsed), [])
                self.assertEqual(parsed.features[0].attrs['date'], expected)

    def test_bad_or_missing_date_is_an_error(self):
        for value in ('14/07/2025', '14 July 2025', '2025-13-01', 'yesterday', 45852, None):
            with self.subTest(value=value):
                parsed = parse([row('99-01', 1, -51.7, 64.18, date=value)], self.editor)
                errors = all_errors(parsed)
                self.assertEqual(len(errors), 1, errors)
                self.assertEqual(errors[0][0], 2)
                self.assertIn('Date', errors[0][1])

    def test_observation_date_optional(self):
        headers = HEADERS + ['Observation_date']
        parsed = parse([row('99-01', 1, -51.7, 64.18) + ['2025-07-10'],
                        row('99-01', 2, -51.7, 64.19) + [None]], self.editor, headers=headers)
        self.assertEqual(all_errors(parsed), [])
        self.assertEqual(parsed.features[0].attrs['observation_date'], datetime.date(2025, 7, 10))
        self.assertIsNone(parsed.features[1].attrs['observation_date'])
        parsed = parse([row('99-01', 1, -51.7, 64.18) + ['10.07.2025']], self.editor,
                       headers=headers)
        self.assertIn('Observation_date', all_errors(parsed)[0][1])

    def test_bad_srid(self):
        for value in ('abc', 999999, None):
            with self.subTest(value=value):
                parsed = parse([row('99-01', 1, -51.7, 64.18, srid=value)], self.editor)
                errors = all_errors(parsed)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn('SRID', errors[0][1])

    def test_mixed_srids_in_one_feature(self):
        parsed = parse([row('99-01', 1, *LINE_UTM[0], kind='line', srid=32622),
                        cont('99-01', 1, -51.7, 64.18, srid=4326)], self.editor)
        errors = all_errors(parsed)
        self.assertEqual(len(errors), 1, errors)
        self.assertEqual(errors[0][0], 3)
        self.assertIn('SRID 4326 differs from 32622', errors[0][1])
        self.assertIsNone(parsed.features[0].result)

    def test_too_few_vertices(self):
        cases = [
            ('line', [row('99-01', 1, -51.7, 64.18, kind='line')], 'at least 2'),
            ('polygon', [row('99-01', 1, *RING[0], kind='polygon'), cont('99-01', 1, *RING[1])],
             'at least 3'),
        ]
        for name, rows, text in cases:
            with self.subTest(kind=name):
                errors = all_errors(parse(rows, self.editor))
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(text, errors[0][1])

    def test_polygon_is_closed_automatically(self):
        rows = [row('99-01', 1, *RING[0], kind='polygon')]
        rows += [cont('99-01', 1, *vertex) for vertex in RING[1:]]
        feature, = parse(rows, self.editor).features
        ring = feature.result.polys[0][0]
        self.assertEqual(len(ring), 5)
        self.assertEqual(ring[0], ring[-1])

    def test_several_point_rows_make_a_multipoint(self):
        rows = [row('99-01', 7, -51.7, 64.18), cont('99-01', 7, -51.71, 64.18),
                cont('99-01', 7, -51.72, 64.18)]
        feature, = parse(rows, self.editor).features
        self.assertEqual(feature.result.points.geom_type, 'MultiPoint')
        self.assertEqual(len(feature.result.points), 3)
        self.assertIsNone(feature.result.lines)

    def test_same_feature_number_in_two_reports_are_two_features(self):
        parsed = parse([row('99-01', 1, -51.7, 64.18), row('99-02', 1, -51.7, 64.18)],
                       self.editor)
        self.assertEqual(all_errors(parsed), [])
        self.assertEqual([f.report for f in parsed.features], [self.pub, self.other_pub])

    def test_attribute_errors(self):
        cases = [
            (dict(type='Rock'), "Feature_type 'Rock' is not valid"),
            (dict(type=None), 'Feature_type is empty'),
            (dict(name=''), 'Name is empty'),
            (dict(name='x' * 101), 'Name is longer than 100'),
            (dict(kind='circle'), "Geometry_type 'circle' is not valid"),
            (dict(quality='Excellent'), "Pos_quality 'Excellent' is not valid"),
        ]
        for kwargs, text in cases:
            with self.subTest(**{k: str(v)[:10] for k, v in kwargs.items()}):
                errors = all_errors(parse([row('99-01', 1, -51.7, 64.18, **kwargs)],
                                          self.editor))
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(text, errors[0][1])

    def test_coordinate_errors(self):
        for x, text in ((None, 'UTMX/LON is empty'), ('51,7', 'not a number'),
                        ('abc', 'not a number')):
            with self.subTest(x=x):
                errors = all_errors(parse([row('99-01', 1, x, 64.18)], self.editor))
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(text, errors[0][1])

    def test_geometry_type_change_within_a_feature_is_an_error(self):
        rows = [row('99-01', 1, -51.7, 64.18, kind='line'),
                cont('99-01', 1, -51.71, 64.18)[:4] + ['polygon', None, -51.71, 64.18, None,
                                                        None]]
        errors = all_errors(parse(rows, self.editor))
        self.assertEqual(errors[0][0], 3)
        self.assertIn("Geometry_type 'polygon' differs from 'line'", errors[0][1])

    def test_empty_feature_number_and_blank_rows(self):
        rows = [row('99-01', None, -51.7, 64.18), [None] * len(HEADERS),
                row('99-01', 2, -51.7, 64.18)]
        parsed = parse(rows, self.editor)
        self.assertEqual(parsed.errors, [(2, 'Feature# is empty.')])
        self.assertEqual(len(parsed.features), 1)
        self.assertEqual(parsed.features[0].rows, [4])

    def test_outside_greenland_is_a_warning_only(self):
        parsed = parse([row('99-01', 1, 12.5, 55.7)], self.editor)   # Copenhagen
        self.assertEqual(all_errors(parsed), [])
        self.assertTrue(any('outside Greenland' in text for _r, text in all_warnings(parsed)))
        self.assertIsNotNone(parsed.features[0].result)

    def test_swapped_lon_lat_is_a_warning(self):
        parsed = parse([row('99-01', 1, 64.18, -51.7)], self.editor)
        self.assertTrue(any('swapped' in text for _r, text in all_warnings(parsed)))

    def test_size_limit(self):
        rows = [row('99-01', i, -51.7, 64.18) for i in range(1, 5)]
        with mock.patch.object(feature_import, 'MAX_VERTICES', 3):
            with self.assertRaises(feature_import.ImportTooLarge):
                parse(rows, self.editor)
            self.assertEqual(len(parse(rows[:3], self.editor).features), 3)


class ReportColumnTests(FeatureImportTestBase):
    """Report page import: the Report column may be empty or name the report."""

    def test_empty_or_matching_report_column(self):
        parsed = parse([row(None, 1, -51.7, 64.18), row('99-01', 2, -51.7, 64.19)],
                       self.dtu_own, report=self.pub)
        self.assertEqual(all_errors(parsed), [])
        self.assertEqual([f.report for f in parsed.features], [self.pub, self.pub])

    def test_other_report_is_a_row_error(self):
        parsed = parse([row('99-01', 1, -51.7, 64.18), row('99-02', 2, -51.7, 64.19)],
                       self.editor, report=self.pub)
        self.assertEqual(len(parsed.features), 1)
        (row_number, text), = parsed.errors
        self.assertEqual(row_number, 3)
        self.assertIn("report '99-02' is not this report (99-01)", text)

    def test_report_number_read_as_date_is_an_error(self):
        parsed = parse([row(datetime.datetime(2099, 1, 7), 1, -51.7, 64.18)], self.editor)
        self.assertIn('read as a date', parsed.errors[0][1])


class AdministrationReportTests(FeatureImportTestBase):
    """Administration import: add_feature on every report of the sheet."""

    def test_report_the_user_may_not_edit_or_that_does_not_exist(self):
        rows = [row('99-01', 1, -51.7, 64.18), row('99-02', 2, -51.7, 64.19),
                row('77-77', 3, -51.7, 64.2)]
        parsed = parse(rows, self.dtu_own)
        errors = all_errors(parsed)
        self.assertEqual([r for r, _t in errors], [3, 4])
        self.assertIn("report '99-02' does not exist or you may not add features to it",
                      errors[0][1])
        self.assertIn("report '77-77' does not exist or you may not add features to it",
                      errors[1][1])
        self.assertEqual(parsed.features[0].errors, [])

    def test_editor_may_import_into_every_report(self):
        parsed = parse([row('99-01', 1, -51.7, 64.18), row('99-02', 2, -51.7, 64.19)],
                       self.editor)
        self.assertEqual(all_errors(parsed), [])


# --- Steps -----------------------------------------------------------------------------------

class ImportStepTests(FeatureImportTestBase):

    def sheet(self):
        rows = [row(None, 1, -51.7, 64.18, name='Sample S1'),
                row(None, 2, *LINE_UTM[0], kind='line', srid=32622, name='Profile P1',
                    type='Field measurement', quality='GPS (phase)')]
        rows += [cont(None, 2, *vertex) for vertex in LINE_UTM[1:]]
        rows += [row(None, 3, *RING[0], kind='polygon', name='Area A', type='Other')]
        rows += [cont(None, 3, *vertex) for vertex in RING[1:]]
        return rows

    def start(self, rows=None, user=None, path=None, headers=HEADERS):
        self.client.force_login(user or self.dtu_own)
        response = self.upload(path or self.report_import_path(), rows or self.sheet(),
                               headers=headers)
        return self.import_id_of(response)

    def test_upload_and_preview_save_nothing(self):
        before = Feature.objects.count()
        import_id = self.start()
        self.assertEqual(Feature.objects.count(), before)
        response = self.client.get(self.preview_path(import_id))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="feature-import-submit"', html)
        self.assertIn('Import 3 features', html)
        self.assertIn('Profile P1', html)
        self.assertIn('id="feature-import-map"', html)
        self.assertIn('id="feature-import-geojson"', html)
        self.assertEqual(len(response.context['preview_geojson']['features']), 3)
        self.assertEqual(Feature.objects.count(), before)

    def test_import_saves_all_features(self):
        import_id = self.start()
        response = self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        self.assertIn('3 features imported into report 99-01.', self.messages_of(response))
        features = {f.name: f for f in self.pub.feature_set.all()}
        self.assertEqual(set(features), {'Sample S1', 'Profile P1', 'Area A'})
        point, line, polygon = features['Sample S1'], features['Profile P1'], features['Area A']
        for feature in (point, line, polygon):
            self.assertEqual(feature.created_by, self.dtu_own)
            self.assertEqual(feature.modified_by, self.dtu_own)
            self.assertEqual(feature.date, datetime.date(2025, 7, 14))
            self.assertIsNone(feature.observation_date)
        self.assertTrue(stored_wkt(point, 'points').upper().startswith('MULTIPOINT'))
        self.assertIsNone(stored_wkt(point, 'lines'))
        self.assertTrue(stored_wkt(line, 'lines').upper().startswith('MULTILINESTRING'))
        self.assertTrue(stored_wkt(polygon, 'polys').upper().startswith('MULTIPOLYGON'))
        self.assertEqual(line.source_srid, 32622)
        self.assertTrue(line.source_geometry.startswith('MULTILINESTRING ((465200'),
                        line.source_geometry)
        self.assertTrue(line.transform_note.startswith('EPSG:32622 -> EPSG:4326'))
        self.assertEqual(point.source_srid, 4326)
        self.assertEqual(point.transform_note, 'EPSG:4326 (no transformation)')
        self.assertEqual((line.type, line.pos_quality), (Feature.FIELD_MEASUREMENT, 'GPS (phase)'))
        expected = from_vertices('line', LINE_UTM, 32622).lines
        self.assertTrue(line.lines.equals_exact(expected, 1e-9))
        self.assertNotIn(import_id, self.stored_imports())
        # The import id is used up.
        response = self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertEqual(self.pub.feature_set.count(), 3)

    def test_observation_date_column_is_stored(self):
        rows = [row(None, 1, -51.7, 64.18) + ['2025-07-10']]
        import_id = self.start(rows, headers=HEADERS + ['Observation_date'])
        self.client.post(self.confirm_path(import_id), {'action': 'import'})
        feature, = self.pub.feature_set.all()
        self.assertEqual(feature.observation_date, datetime.date(2025, 7, 10))

    def test_one_bad_feature_blocks_the_import(self):
        rows = self.sheet() + [row(None, 4, -51.7, 64.18, date='14/07/2025')]
        import_id = self.start(rows)
        response = self.client.get(self.preview_path(import_id))
        html = response.content.decode()
        self.assertNotIn('id="feature-import-submit"', html)
        self.assertIn('Nothing can be imported', html)
        self.assertIn('row 10', html)
        response = self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertEqual(Feature.objects.filter(publications=self.pub).count(), 0)
        self.assertIn('The file has errors; nothing was imported.', self.messages_of(response))

    def test_failure_during_the_import_saves_nothing(self):
        import_id = self.start()
        original_save = Feature.save
        calls = []

        def failing_save(feature, *args, **kwargs):
            calls.append(feature.name)
            if len(calls) == 2:
                raise RuntimeError('disk full')
            return original_save(feature, *args, **kwargs)

        with mock.patch.object(Feature, 'save', failing_save), \
                self.assertLogs('publications.views_feature_import', 'ERROR'):
            response = self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertEqual(len(calls), 2)
        self.assertEqual(Feature.objects.filter(publications=self.pub).count(), 0)
        self.assertEqual(Feature.objects.count(), 0)
        self.assertIn('The import failed; nothing was saved.', self.messages_of(response))
        self.assertIn(import_id, self.stored_imports())   # can be tried again

    def test_cancel_saves_nothing(self):
        import_id = self.start()
        response = self.client.post(self.confirm_path(import_id), {'action': 'cancel'})
        self.assertRedirects(
            response, reverse('publications:import_report_features', kwargs={'pk': self.pub.pk}),
            fetch_redirect_response=False)
        self.assertEqual(Feature.objects.count(), 0)
        self.assertNotIn(import_id, self.stored_imports())

    def test_unknown_expired_or_other_users_import(self):
        import_id = self.start()
        expired_id = self.start()
        session = self.client.session
        imports = session[feature_import.SESSION_KEY]
        imports[expired_id]['created'] -= feature_import.SESSION_MAX_AGE + 1
        session[feature_import.SESSION_KEY] = imports
        session.save()
        for name, key in (('unknown', 'NoSuchImport123'), ('expired', expired_id)):
            for method, path in (('get', self.preview_path(key)),
                                 ('post', self.confirm_path(key))):
                with self.subTest(case=name, method=method):
                    response = getattr(self.client, method)(path, {'action': 'import'})
                    self.assertRedirects(response, reverse('publications:import_features'),
                                         fetch_redirect_response=False)
                    self.assertIn(EXPIRED_MESSAGE, self.messages_of(response))
        # Another user's import id (in the same session store) is unknown for this user.
        session = self.client.session
        data = session[feature_import.SESSION_KEY]
        self.client.force_login(self.editor)
        session = self.client.session
        session[feature_import.SESSION_KEY] = data
        session.save()
        response = self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertRedirects(response, reverse('publications:import_features'),
                             fetch_redirect_response=False)
        self.assertEqual(Feature.objects.count(), 0)

    def test_size_limit_is_an_error_at_upload(self):
        self.client.force_login(self.dtu_own)
        rows = [row(None, i, -51.7, 64.18) for i in range(1, 5)]
        with mock.patch.object(feature_import, 'MAX_VERTICES', 3):
            response = self.upload(self.report_import_path(), rows)
        self.assertEqual(response.status_code, 200)
        self.assertIn('more than 3 vertex rows', response.content.decode())
        self.assertEqual(self.stored_imports(), {})

    def test_not_an_excel_file(self):
        self.client.force_login(self.dtu_own)
        for name, content, text in (
                ('features.xlsx', b'not a zip file', 'could not be read as an Excel'),
                ('features.csv', b'a,b', 'Only Excel files (.xlsx)')):
            with self.subTest(name=name):
                response = self.client.post(self.report_import_path(),
                                            {'file': SimpleUploadedFile(name, content)})
                self.assertEqual(response.status_code, 200)
                self.assertIn(text, response.content.decode())
        self.assertEqual(self.stored_imports(), {})

    def test_second_import_of_the_same_sheet_is_a_warning(self):
        import_id = self.start()
        self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertEqual(self.pub.feature_set.count(), 3)
        # A changed point: not a duplicate.
        rows = self.sheet()
        rows[0] = row(None, 1, -51.6, 64.18, name='Sample S1')
        import_id = self.start(rows)
        response = self.client.get(self.preview_path(import_id))
        warnings = [text for _row, level, text in response.context['problems']
                    if level == 'warning']
        self.assertEqual(len(warnings), 2, warnings)
        self.assertTrue(all('imported before?' in text for text in warnings))
        self.assertNotIn("'Sample S1'", ' '.join(warnings))
        self.assertTrue(response.context['importable'])
        self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertEqual(self.pub.feature_set.count(), 6)

    def test_confirm_checks_the_reports_again(self):
        import_id = self.start()
        Authorship.objects.filter(publication=self.pub).delete()   # dtu_own no longer listed
        response = self.client.get(self.preview_path(import_id))
        self.assertFalse(response.context['importable'])
        self.assertIn('You may no longer add features to report 99-01.',
                      response.content.decode())
        response = self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertIn('Nothing was imported.', self.messages_of(response))
        self.assertEqual(Feature.objects.count(), 0)

    def test_confirm_refuses_a_deleted_report(self):
        import_id = self.start(user=self.editor)
        self.pub.delete()
        response = self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertIn('Report 99-01 no longer exists.', self.messages_of(response))
        self.assertEqual(Feature.objects.count(), 0)

    def test_administration_import_into_two_reports(self):
        rows = [row('99-01', 1, -51.7, 64.18), row('99-02', 1, -51.7, 64.19)]
        import_id = self.start(rows, user=self.editor, path=self.admin_import_path())
        response = self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertRedirects(response, reverse('publications:import_features'),
                             fetch_redirect_response=False)
        self.assertIn('2 features imported into reports 99-01, 99-02.',
                      self.messages_of(response))
        self.assertEqual(self.pub.feature_set.count(), 1)
        self.assertEqual(self.other_pub.feature_set.count(), 1)

    def test_administration_import_with_a_report_the_user_may_not_edit(self):
        # dtu_own may edit 99-01 but not 99-02: rows for 99-02 are errors, nothing imported.
        rows = [row('99-01', 1, -51.7, 64.18), row('99-02', 2, -51.7, 64.19)]
        import_id = self.start(rows, user=self.dtu_own, path=self.admin_import_path())
        response = self.client.get(self.preview_path(import_id))
        self.assertFalse(response.context['importable'])
        self.assertNotIn('id="feature-import-submit"', response.content.decode())
        self.assertIn("report &#x27;99-02&#x27; does not exist or you may not add features",
                      response.content.decode())
        self.client.post(self.confirm_path(import_id), {'action': 'import'})
        self.assertEqual(Feature.objects.count(), 0)

    def test_report_page_import_validates_the_report_column(self):
        rows = [row('99-01', 1, -51.7, 64.18), row('99-02', 2, -51.7, 64.19)]
        import_id = self.start(rows, user=self.editor)
        response = self.client.get(self.preview_path(import_id))
        self.assertFalse(response.context['importable'])
        self.assertIn("is not this report (99-01)", response.content.decode())

    def test_session_keeps_only_a_few_imports(self):
        ids = [self.start() for _ in range(feature_import.SESSION_MAX_IMPORTS + 1)]
        self.assertEqual(sorted(self.stored_imports()), sorted(ids[1:]))

    @override_settings(FA_DATAFORSYNINGEN_TOKEN='dummy-token-t10')
    def test_preview_map_gets_the_token_only_as_data_attribute(self):
        import_id = self.start()
        html = self.client.get(self.preview_path(import_id)).content.decode()
        self.assertEqual(html.count('dummy-token-t10'), 1)
        self.assertIn('data-dataforsyningen-token="dummy-token-t10"', html)
        self.assertIn('publications/vendor/leaflet-1.9.4/leaflet.js', html)
        self.assertIn('feature-import-preview.js', html)


# --- Access ----------------------------------------------------------------------------------

class AccessTests(FeatureImportTestBase):

    def test_report_import_page(self):
        path = self.report_import_path()
        self.assertRedirectsToLogin(self.client.get(path))
        self.assertRedirectsToLogin(self.upload(path, [row(None, 1, -51.7, 64.18)]))
        for user, status in ((self.dtu_not_own, 403), (self.staff, 403), (self.no_role, 403),
                             (self.dtu_own, 200), (self.staff_own, 200), (self.editor, 200)):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(path)
                self.assertEqual(response.status_code, status)
                upload = self.upload(path, [row(None, 1, -51.7, 64.18)])
                self.assertEqual(upload.status_code, 403 if status == 403 else 302)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(page_path('import_report_features', pk=99999))
                         .status_code, 404)

    def test_administration_import_page(self):
        path = self.admin_import_path()
        self.assertRedirectsToLogin(self.client.get(path))
        for user, status in ((self.no_role, 403), (self.dtu_not_own, 200), (self.dtu_own, 200),
                             (self.editor, 200)):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(path).status_code, status)

    def test_preview_and_confirm(self):
        self.client.force_login(self.dtu_own)
        import_id = self.import_id_of(self.upload(self.report_import_path(),
                                                  [row(None, 1, -51.7, 64.18)]))
        self.client.logout()
        self.assertRedirectsToLogin(self.client.get(self.preview_path(import_id)))
        self.assertRedirectsToLogin(self.client.post(self.confirm_path(import_id),
                                                     {'action': 'import'}))
        self.client.force_login(self.no_role)
        self.assertDenied(self.client.get(self.preview_path(import_id)))
        self.assertDenied(self.client.post(self.confirm_path(import_id), {'action': 'import'}))
        # Another DTU user does not have the import in their session.
        self.client.force_login(self.dtu_not_own)
        response = self.client.get(self.preview_path(import_id))
        self.assertRedirects(response, reverse('publications:import_features'),
                             fetch_redirect_response=False)
        self.assertEqual(Feature.objects.count(), 0)

    def test_confirm_is_post_only(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(self.confirm_path('abc')).status_code, 405)

    def test_report_page_button(self):
        report = page_path('report', pk=self.pub.pk)
        link = reverse('publications:import_report_features', kwargs={'pk': self.pub.pk})
        self.client.force_login(self.dtu_own)
        self.assertIn(f'href="{link}"', self.client.get(report).content.decode())
        self.client.force_login(self.dtu_not_own)
        other = page_path('report', pk=self.other_pub.pk)
        self.assertNotIn('import-features-link', self.client.get(other).content.decode())

    def test_upload_page_links_the_template(self):
        self.client.force_login(self.dtu_own)
        html = self.client.get(self.report_import_path()).content.decode()
        self.assertIn('publications/docs/ARTEK_feature_list.xlsx', html)
        self.assertIn('id="feature-import-form"', html)


# --- Template --------------------------------------------------------------------------------

class TemplateWorkbookTests(FeatureImportTestBase):

    def committed(self):
        path = finders.find(feature_import.TEMPLATE_STATIC_PATH)
        self.assertIsNotNone(path, 'template workbook missing')
        return openpyxl.load_workbook(path)

    def test_template_has_both_sheets_and_parser_headers(self):
        workbook = self.committed()
        self.assertEqual(workbook.sheetnames, ['Features', 'Help'])
        headers = [cell.value for cell in workbook['Features'][1]]
        self.assertEqual(headers, [column.header for column in feature_import.COLUMNS])
        for header in headers:
            self.assertIn(feature_import._normalise_header(header), feature_import.HEADER_ALIASES)
        help_text = ' '.join(str(cell.value) for line in workbook['Help'].iter_rows()
                             for cell in line if cell.value is not None)
        for header in headers:
            self.assertIn(header, help_text)
        for code, _name in GREENLAND_SRIDS:
            self.assertIn(str(code), help_text)
        self.assertIn('YYYY-MM-DD', help_text)

    def test_template_examples_import_cleanly(self):
        Publication.objects.create(type=self.pubtype, title='Example', number='25-07',
                                   year=2025)
        path = finders.find(feature_import.TEMPLATE_STATIC_PATH)
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parsed = feature_import.parse_workbook(workbook, self.editor)
        self.assertEqual(all_errors(parsed), [])
        self.assertEqual([f.kind for f in parsed.features], ['point', 'line', 'polygon'])
        self.assertEqual(parsed.features[1].srid, 32622)

    def test_committed_template_is_what_the_command_writes(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, 'template.xlsx')
            call_command('make_feature_import_template', '--output', output,
                         stdout=io.StringIO())
            fresh = openpyxl.load_workbook(output)
        committed = self.committed()
        for name in ('Features', 'Help'):
            with self.subTest(sheet=name):
                self.assertEqual(list(fresh[name].iter_rows(values_only=True)),
                                 list(committed[name].iter_rows(values_only=True)))
