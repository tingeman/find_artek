"""Excel import of reports (register_from_file.xlsx_pubs, and the upload page
add_reports_from_file_upload with the real parser). Plan test-coverage T7b.

- All or nothing: the whole file is one transaction; any row error saves nothing (reports,
  persons, also persons from the directory, topics, keywords) and every problem is listed as
  "Sheet '<name>', row <n>: <problem>".
- Columns: case-insensitive, singular or plural; required title, authors, number or year;
  unknown columns are ignored with a warning; a sheet named Help is not imported.
- An existing report number: row skipped with a warning, the report unchanged. The same number
  twice in the file: error. Year from number: 90-99 is 19YY, below 90 is 20YY.
- Type: report types only. Topics: existing ones only. Keywords: reused or created.
- Persons: an unknown study number or initials, or a name without a given name, is an error.

The workbooks are built in the test with openpyxl; USE_LDAP is off unless a test says
otherwise (the directory is then mocked). All names, numbers and study numbers are made up.
"""

import datetime
import os
import shutil
import tempfile
from unittest import mock

import openpyxl
from django.contrib import messages
from django.contrib.staticfiles import finders
from django.core.files.uploadedfile import SimpleUploadedFile
from django.templatetags.static import static
from django.test import TestCase, override_settings

from publications import register_from_file
from publications.models import (
    Authorship, Keyword, Keywordship, Person, Publication, PubType, Supervisorship, Topic,
    Topicship,
)
from publications.roles import ARTEK_EDITOR
from publications.test_factories import (
    app_path, ldap_entry, make_person, make_report, make_user, page_path,
)

HEADER = ['number', 'year', 'title', 'type', 'topic', 'authors', 'supervisors']
TEMPLATE = 'publications/docs/ARTEK_report_list.xlsx'
NOTHING = ("Nothing was imported: the file has {} problem{}. Correct the file and upload it "
           "again.")


def nothing_imported(count):
    return (messages.ERROR, NOTHING.format(count, 's' if count != 1 else ''))


def row(number, year, title, authors='', supervisors='', topic='', type_='STUDENTREPORT'):
    return [number, year, title, type_, topic, authors, supervisors]


class _ExcelCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.report_type = PubType.objects.create(type='STUDENTREPORT')
        PubType.objects.create(type='MASTERSTHESIS')
        PubType.objects.create(type='ARTICLE')
        cls.user = make_user('zqeditor', ARTEK_EDITOR)
        cls.student = make_person('Stu', 'Zqdent', id_number='s990001')
        cls.supervisor = make_person('Su', 'Zqvisor', initials='zqsv')
        cls.permafrost = Topic.objects.create(topic='Permafrost')
        cls.geology = Topic.objects.create(topic='Geology')
        cls.ice = Keyword.objects.create(keyword='Ice')

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='fa-test-xlsx-')
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def workbook(self, sheets):
        """Write ``sheets`` ({sheet name: list of rows}) to an .xlsx file; returns its path."""
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for name, rows in sheets.items():
            ws = wb.create_sheet(name)
            for values in rows:
                ws.append(values)
        path = os.path.join(self.dir, 'reports.xlsx')
        wb.save(path)
        return path

    def import_sheets(self, sheets):
        return register_from_file.xlsx_pubs(self.workbook(sheets), user=self.user)

    def import_rows(self, *rows, header=HEADER):
        return self.import_sheets({'Reports': [header, *rows]})

    def authors(self, pub):
        return [a.person for a in pub.authorship_set.order_by('author_id')]

    def supervisors(self, pub):
        return [s.person for s in pub.supervisorship_set.order_by('supervisor_id')]

    def counts(self):
        return {model.__name__: model.objects.count()
                for model in (Publication, Person, Topic, Keyword, Authorship, Supervisorship,
                              Topicship, Keywordship)}


@override_settings(USE_LDAP=False)
class XlsxImportTests(_ExcelCase):

    def test_reports_are_created_with_persons_topics_and_keywords(self):
        result = self.import_sheets({'Reports': [
            HEADER + ['abstract', 'keywords', 'comment'],
            row('99-01', 1999, 'Permafrost at Zqville', 'Jane Zqroe and s990001', 'zqsv',
                topic='permafrost; Geology') + ['An abstract.', 'ice, Zqsnow', 'A comment.'],
            row('99-02', 1999, 'Roads on ice', 'Zqlee, Ann', 'zqsv'),
        ]})
        self.assertEqual(result, [
            (messages.SUCCESS, "Sheet 'Reports': 2 reports created, 0 rows skipped.")])

        pub = Publication.objects.get(number='99-01')
        self.assertEqual((pub.title, pub.year, pub.type, pub.abstract, pub.comment),
                         ('Permafrost at Zqville', 1999, self.report_type, 'An abstract.',
                          'A comment.'))
        self.assertEqual((pub.created_by, pub.modified_by), (self.user, self.user))
        # Imported reports are unvalidated (hidden from anonymous users) until verified.
        self.assertFalse(pub.verified)

        authors = self.authors(pub)
        self.assertEqual([(p.first, p.last) for p in authors],
                         [('Jane', 'Zqroe'), ('Stu', 'Zqdent')])
        self.assertEqual(authors[1], self.student)           # matched by study number
        self.assertEqual(authors[0].created_by, self.user)   # new person
        self.assertEqual(self.supervisors(pub), [self.supervisor])
        self.assertEqual(set(pub.publication_topics.all()), {self.permafrost, self.geology})
        keywords = set(pub.publication_keywords.all())
        self.assertIn(self.ice, keywords)                     # reused, case-insensitive
        self.assertEqual(sorted(k.keyword for k in keywords), ['Ice', 'Zqsnow'])
        self.assertEqual(Keyword.objects.filter(keyword__iexact='ice').count(), 1)

        other = Publication.objects.get(number='99-02')
        self.assertEqual([(p.first, p.last) for p in self.authors(other)], [('Ann', 'Zqlee')])
        self.assertEqual(self.supervisors(other), [self.supervisor])

    def test_headers_are_case_insensitive_singular_or_plural(self):
        header = ['Number', 'TITLE', 'Author', 'Supervisor', 'Topics', 'Keyword', 'Comments']
        result = self.import_rows(
            ['99-01', 'T', 's990001', 'zqsv', 'Geology', 'Zqfrost', 'Note'], header=header)
        self.assertEqual(result[-1][0], messages.SUCCESS)
        pub = Publication.objects.get(number='99-01')
        self.assertEqual(self.authors(pub), [self.student])
        self.assertEqual(self.supervisors(pub), [self.supervisor])
        self.assertEqual(list(pub.publication_topics.all()), [self.geology])
        self.assertEqual([k.keyword for k in pub.publication_keywords.all()], ['Zqfrost'])
        self.assertEqual(pub.comment, 'Note')

    def test_unknown_columns_are_ignored_with_a_warning(self):
        result = self.import_rows(row('99-01', 1999, 'T', 's990001') + ['x', 'y'],
                                  header=HEADER + ['Grade', 'Remarks'])
        self.assertEqual(result, [
            (messages.WARNING, "Sheet 'Reports': unknown columns ignored: Grade, Remarks."),
            (messages.SUCCESS, "Sheet 'Reports': 1 report created, 0 rows skipped."),
        ])
        self.assertTrue(Publication.objects.filter(number='99-01').exists())

    def test_type_and_supervisors_are_optional(self):
        result = self.import_rows(['99-01', 'T', 's990001'],
                                  header=['number', 'title', 'authors'])
        self.assertEqual(result[-1][0], messages.SUCCESS)
        self.assertEqual(Publication.objects.get(number='99-01').type, self.report_type)

    def test_sheet_missing_required_columns_is_an_error(self):
        result = self.import_sheets({
            'NoAuthors': [['number', 'year', 'title'], ['99-01', 1999, 'T']],
            'NoNumberOrYear': [['title', 'authors'], ['T', 's990001']],
            'Good': [HEADER, row('99-02', 1999, 'T', 's990001')],
        })
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(result, [
            nothing_imported(2),
            (messages.ERROR, "Sheet 'NoAuthors': required columns missing: authors."),
            (messages.ERROR, "Sheet 'NoNumberOrYear': required columns missing: number or "
                             "year."),
        ])

    def test_empty_sheet_and_help_sheet_are_not_imported(self):
        result = self.import_sheets({
            'Empty': [],
            'Help': [['Column', 'Required?', 'What to write'], ['number', 'x', 'y']],
            'Reports': [HEADER, row('99-01', 1999, 'T', 's990001')],
        })
        self.assertEqual(result, [
            (messages.WARNING, "Sheet 'Empty' is empty, nothing imported."),
            (messages.SUCCESS, "Sheet 'Reports': 1 report created, 0 rows skipped."),
        ])

    def test_blank_rows_are_ignored(self):
        result = self.import_rows(row('99-01', 1999, 'T', 's990001'), [None] * 7,
                                  row('99-02', 1999, 'U', 's990001'))
        self.assertEqual(result[-1],
                         (messages.SUCCESS, "Sheet 'Reports': 2 reports created, 0 rows skipped."))

    def test_empty_authors_cell_is_an_error(self):
        result = self.import_rows(row('99-01', 1999, 'No authors', None),
                                  row('99-02', 1999, 'Only separators', ' ; '),
                                  row('99-03', 1999, 'Good', 's990001'))
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(result, [
            nothing_imported(2),
            (messages.ERROR, "Sheet 'Reports', row 2: at least one author is required."),
            (messages.ERROR, "Sheet 'Reports', row 3: at least one author is required."),
        ])

    def test_empty_title_is_allowed(self):
        # Entries prepared for a course before the reports are written; the title comes later.
        result = self.import_rows(row('99-01', 1999, None, 's990001'),
                                  row(None, 1999, '', 's990001'))
        self.assertEqual(result, [
            (messages.INFO, "Sheet 'Reports', row 3: report number '99-02' assigned."),
            (messages.SUCCESS, "Sheet 'Reports': 2 reports created, 0 rows skipped."),
        ])
        for number in ('99-01', '99-02'):
            pub = Publication.objects.get(number=number)
            self.assertEqual((pub.title, pub.year), ('', 1999))
            self.assertEqual(self.authors(pub), [self.student])

    def test_existing_number_with_empty_title_is_named_by_id(self):
        existing = make_report(self.report_type, '99-01', verified=False, confidential=False,
                               year=1999, title='')
        result = self.import_rows(row('99-01', 1999, 'New', 's990001'))
        self.assertEqual(result[0], (
            messages.WARNING,
            f"Sheet 'Reports', row 2: report number '99-01' already exists (report "
            f"[id:{existing.pk}]); row skipped, the existing report was not changed."))

    def test_editors_column_is_optional_and_linked_in_order(self):
        for header_name in ('editors', 'Editor'):
            with self.subTest(header=header_name):
                Publication.objects.all().delete()
                result = self.import_rows(row('99-01', 1999, 'T', 's990001')
                                          + ['Jane Zqroe; zqsv'],
                                          header=HEADER + [header_name])
                self.assertEqual(result[-1][0], messages.SUCCESS)
                pub = Publication.objects.get(number='99-01')
                editors = [e.person for e in pub.editorship_set.order_by('editor_id')]
                self.assertEqual([(p.first, p.last) for p in editors],
                                 [('Jane', 'Zqroe'), ('Su', 'Zqvisor')])
                self.assertEqual(editors[1], self.supervisor)

    def test_unknown_editor_is_an_error(self):
        result = self.import_rows(row('99-01', 1999, 'T', 's990001') + ['zqxx'],
                                  header=HEADER + ['editors'])
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(result[1], (
            messages.ERROR, "Sheet 'Reports', row 2: editor 'zqxx' was not found in the "
                            "database."))

    def test_name_matching_an_existing_person_still_creates_a_flagged_person(self):
        existing = Person.objects.create(name='Jane Zqroe')
        self.import_rows(row('99-01', 1999, 'T', 'Jane Zqroe'))
        link = Publication.objects.get(number='99-01').authorship_set.get()
        self.assertNotEqual(link.person, existing)
        self.assertTrue(link.exact_match)

    def test_row_without_topic_is_imported(self):
        result = self.import_rows(row('99-01', 1999, 'No topic', 's990001'),
                                  row('99-02', 1999, 'Next', 's990001'))
        self.assertEqual(Publication.objects.get(number='99-01').publication_topics.count(), 0)
        self.assertTrue(Publication.objects.filter(number='99-02').exists())
        self.assertEqual(result[-1][0], messages.SUCCESS)

    # ---- numbers and years --------------------------------------------------------------

    def test_year_is_taken_from_the_number(self):
        self.import_rows(row('98-07', None, 'A', 's990001'), row('05-01', None, 'B', 's990001'),
                         row('90-03', None, 'C', 's990001'), row('89-02', None, 'D', 's990001'))
        years = dict(Publication.objects.values_list('number', 'year'))
        self.assertEqual(years, {'98-07': 1998, '05-01': 2005, '90-03': 1990, '89-02': 2089})

    def test_number_is_generated_from_the_year(self):
        result = self.import_rows(row(None, 1997, 'T', 's990001'))
        self.assertEqual(Publication.objects.get(title='T').number, '97-01')
        self.assertIn((messages.INFO, "Sheet 'Reports', row 2: report number '97-01' assigned."),
                      result)

    def test_year_only_rows_get_distinct_numbers_around_given_ones(self):
        make_report(self.report_type, '97-01', verified=True, confidential=False, year=1997)
        self.import_rows(row(None, 1997, 'A', 's990001'), row(None, 1997, 'B', 's990001'),
                         row('97-03', 1997, 'C', 's990001'), row(None, 1997, 'D', 's990001'))
        numbers = dict(Publication.objects.filter(title__in='ABCD')
                       .values_list('title', 'number'))
        self.assertEqual(numbers, {'A': '97-02', 'B': '97-04', 'C': '97-03', 'D': '97-05'})

    def test_existing_number_is_skipped_and_the_report_unchanged(self):
        existing = make_report(self.report_type, '99-01', verified=True, confidential=False,
                               year=1999, title='Old title')
        result = self.import_rows(row('99-01', 1999, 'New title', 'Jane Zqroe'),
                                  row('99-02', 1999, 'Other', 's990001'))
        existing.refresh_from_db()
        self.assertEqual(existing.title, 'Old title')
        self.assertEqual(existing.authorship_set.count(), 0)
        self.assertFalse(Person.objects.filter(last='Zqroe').exists())
        self.assertEqual(result, [
            (messages.WARNING,
             f"Sheet 'Reports', row 2: report number '99-01' already exists (report 'Old title' "
             f"[id:{existing.pk}]); row skipped, the existing report was not changed."),
            (messages.INFO, "Sheet 'Reports': 1 report created, 1 row skipped."),
        ])

    def test_same_number_twice_in_the_file_is_an_error(self):
        result = self.import_sheets({
            'A': [HEADER, row('99-01', 1999, 'T', 's990001')],
            'B': [HEADER, row('99-01', 1999, 'U', 's990001')],
        })
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(result, [
            nothing_imported(1),
            (messages.ERROR, "Sheet 'B', row 2: number '99-01' is also in Sheet 'A', row 2."),
        ])

    def test_row_without_number_and_year_is_an_error(self):
        result = self.import_rows(row('99-01', 1999, 'Good', 's990001'),
                                  row(None, None, 'No number', 's990001'))
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(result, [
            nothing_imported(1),
            (messages.ERROR, "Sheet 'Reports', row 3: a number or a year is required."),
        ])

    def test_bad_year_and_number_without_year_prefix(self):
        result = self.import_rows(row('99-01', 'nineteen', 'A', 's990001'),
                                  row('X-1', None, 'B', 's990001'))
        self.assertEqual(result[1:], [
            (messages.ERROR, "Sheet 'Reports', row 2: year 'nineteen' is not a number."),
            (messages.ERROR, "Sheet 'Reports', row 3: no year, and the number 'X-1' does not "
                             "start with a two-digit year (e.g. 99-01)."),
        ])

    def test_number_read_as_a_date_is_an_error(self):
        result = self.import_rows(row(datetime.datetime(1999, 1, 1), 1999, 'T', 's990001'))
        self.assertFalse(Publication.objects.exists())
        self.assertIn('the number was read as a date by Excel', result[1][1])

    # ---- type, topics -------------------------------------------------------------------

    def test_type_is_case_insensitive(self):
        self.import_rows(row('99-01', 1999, 'T', 's990001', type_='mastersthesis'))
        self.assertEqual(Publication.objects.get(number='99-01').type.type, 'MASTERSTHESIS')

    def test_unknown_or_non_report_type_is_an_error(self):
        result = self.import_rows(row('99-01', 1999, 'An article', 's990001', type_='ARTICLE'),
                                  row('99-02', 1999, 'Odd', 's990001', type_='POEM'))
        self.assertFalse(Publication.objects.exists())
        accepted = 'STUDENTREPORT, MASTERSTHESIS, PHDTHESIS, DIPLOMPROJEKT, BACHELORTHESIS'
        self.assertEqual(result[1:], [
            (messages.ERROR, f"Sheet 'Reports', row 2: type 'ARTICLE' is not accepted; "
                             f"accepted types: {accepted}."),
            (messages.ERROR, f"Sheet 'Reports', row 3: type 'POEM' is not accepted; "
                             f"accepted types: {accepted}."),
        ])

    def test_unknown_topic_is_an_error_listing_the_topics(self):
        result = self.import_rows(row('99-01', 1999, 'T', 's990001', topic='Geology, Zqmagic'))
        self.assertFalse(Publication.objects.exists())
        self.assertFalse(Topic.objects.filter(topic='Zqmagic').exists())
        self.assertEqual(result[1], (
            messages.ERROR,
            "Sheet 'Reports', row 2: unknown topic 'Zqmagic'; valid topics: Geology, Permafrost."))

    # ---- persons ------------------------------------------------------------------------

    def test_persons_that_cannot_be_resolved_are_errors(self):
        result = self.import_rows(row('99-01', 1999, 'T', 'van Zqroe and s990999', 'zqxx'))
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(result, [
            nothing_imported(3),
            (messages.ERROR, "Sheet 'Reports', row 2: author name 'van Zqroe' needs a given name "
                             "and a surname ('Given Surname'), or give a study number or "
                             "initials."),
            (messages.ERROR, "Sheet 'Reports', row 2: author 's990999' was not found in the "
                             "database."),
            (messages.ERROR, "Sheet 'Reports', row 2: supervisor 'zqxx' was not found in the "
                             "database."),
        ])

    # ---- all or nothing -----------------------------------------------------------------

    def test_one_bad_row_among_good_rows_saves_nothing(self):
        before = self.counts()
        result = self.import_sheets({
            'First': [HEADER + ['keywords'],
                      row('99-01', 1999, 'Good', 'Jane Zqroe', 'zqsv', topic='Geology')
                      + ['Zqnewword'],
                      row(None, 1999, 'Good too', 'Ann Zqlee; s990001')],
            'Second': [HEADER, row('99-03', 1999, 'Bad', 'Bo Zqvik', 'zqxx'),
                       row('99-04', 1999, 'Good', 'Cy Zqbo')],
        })
        self.assertEqual(self.counts(), before)
        self.assertEqual(result, [
            nothing_imported(1),
            (messages.ERROR, "Sheet 'Second', row 2: supervisor 'zqxx' was not found in the "
                             "database."),
        ])

    def test_all_problems_are_listed(self):
        result = self.import_rows(row(None, None, 'A', 's990001'),
                                  row('99-02', 1999, 'B', 's990999'),
                                  row('99-03', 1999, 'C', 's990001', topic='Zqmagic'))
        self.assertEqual(result[0], nothing_imported(3))
        # By row, although the person problem of row 3 is found after the others.
        self.assertEqual([r.split(':')[0] for _level, r in result[1:]],
                         ["Sheet 'Reports', row 2", "Sheet 'Reports', row 3",
                          "Sheet 'Reports', row 4"])

    def test_problems_are_sorted_by_sheet_row_and_order_found(self):
        result = self.import_sheets({
            'First': [HEADER,
                      row('99-01', 1999, 'A', 's990999'),                        # pass 2
                      row('99-02', 1999, 'B', None, type_='POEM')],               # pass 1
            'Second': [['number', 'title'], ['99-03', 'C']],                      # sheet
            'Third': [HEADER, row('99-04', 1999, 'D', 'zqxx', 'zqyy')],         # pass 2
        })
        accepted = 'STUDENTREPORT, MASTERSTHESIS, PHDTHESIS, DIPLOMPROJEKT, BACHELORTHESIS'
        self.assertEqual([text for _level, text in result], [
            NOTHING.format(6, 's'),
            "Sheet 'First', row 2: author 's990999' was not found in the database.",
            "Sheet 'First', row 3: at least one author is required.",
            f"Sheet 'First', row 3: type 'POEM' is not accepted; accepted types: {accepted}.",
            "Sheet 'Second': required columns missing: authors.",
            "Sheet 'Third', row 2: author 'zqxx' was not found in the database.",
            "Sheet 'Third', row 2: supervisor 'zqyy' was not found in the database.",
        ])

    def test_reupload_creates_nothing_and_warns_per_row(self):
        sheets = {'Reports': [HEADER, row('99-01', 1999, 'A', 'Jane Zqroe'),
                              row('99-02', 1999, 'B', 's990001', topic='Geology')]}
        self.import_sheets(sheets)
        before = self.counts()
        result = self.import_sheets(sheets)
        self.assertEqual(self.counts(), before)
        self.assertEqual([level for level, _text in result],
                         [messages.WARNING, messages.WARNING, messages.INFO])
        self.assertIn("row 2: report number '99-01' already exists", result[0][1])
        self.assertIn("row 3: report number '99-02' already exists", result[1][1])
        self.assertEqual(result[2][1], "Sheet 'Reports': 0 reports created, 2 rows skipped.")


@override_settings(USE_LDAP=True)
class XlsxImportLdapTests(_ExcelCase):

    def test_study_number_not_in_directory_is_an_error(self):
        with mock.patch('publications.utils_person.find_ldap_person', return_value=[]):
            result = self.import_rows(row('99-01', 1999, 'T', 's990999'))
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(result[1], (
            messages.ERROR,
            "Sheet 'Reports', row 2: author 's990999' was not found in the database or the DTU "
            "directory."))

    def test_supervisor_from_directory_is_not_linked_to_a_person_with_empty_initials(self):
        # The database has a student with empty initials (cls.student). Before the fix of
        # get_or_create_person_from_ldap, the supervisor found in the directory by initials
        # was linked to that student.
        entry = ldap_entry('Zqvisor', 'Ny', title='Lektor', employee_id='99002',
                           department='Zq Dept', initials='zqny')
        with mock.patch('publications.utils_person.find_ldap_person',
                        return_value=[entry]) as find:
            self.import_rows(row('99-01', 1999, 'T', 's990001', 'zqny'))
        find.assert_called_once_with(initials='zqny')
        [supervisor] = self.supervisors(Publication.objects.get(number='99-01'))
        self.assertNotEqual(supervisor, self.student)
        self.assertEqual((supervisor.initials, supervisor.id_number, supervisor.last),
                         ('zqny', '99002', 'Zqvisor'))

    def test_persons_from_the_directory_are_rolled_back_on_error(self):
        def directory(**query):
            if query == {'name': 's990555'}:
                return [ldap_entry('Zqnew', 'Stu', company='Studerende', name='s990555')]
            return []

        before = self.counts()
        with mock.patch('publications.utils_person.find_ldap_person', side_effect=directory):
            result = self.import_rows(row('99-01', 1999, 'Good', 's990555'),
                                      row('99-02', 1999, 'Bad', 's990001', type_='POEM'))
        self.assertEqual(result[0], nothing_imported(1))
        self.assertFalse(Person.objects.filter(id_number='s990555').exists())
        self.assertEqual(self.counts(), before)


@override_settings(USE_LDAP=False)
class XlsxTemplateTests(_ExcelCase):
    """The template linked from the upload page is a static file, and the parser accepts it."""

    def test_static_finder_finds_the_template(self):
        self.assertIsNotNone(finders.find(TEMPLATE))

    def test_template_headers_are_accepted(self):
        path = os.path.join(self.dir, 'filled.xlsx')
        shutil.copy(finders.find(TEMPLATE), path)
        wb = openpyxl.load_workbook(path)
        ws = wb.worksheets[0]
        header = [c.value for c in ws[1]]
        self.assertEqual(header, register_from_file.TEMPLATE_COLUMNS)
        self.assertIn('Help', wb.sheetnames)
        values = {'number': '99-01', 'year': 1999, 'title': 'From the template',
                  'type': 'STUDENTREPORT', 'topic': 'Geology', 'authors': 's990001',
                  'supervisors': 'zqsv', 'abstract': 'A', 'keywords': 'Zqword',
                  'comment': 'C'}
        ws.append([values[name] for name in header])
        wb.save(path)
        result = register_from_file.xlsx_pubs(path, user=self.user)
        self.assertEqual(result, [
            (messages.SUCCESS, f"Sheet '{ws.title}': 1 report created, 0 rows skipped.")])
        pub = Publication.objects.get(number='99-01')
        self.assertEqual((pub.title, pub.abstract, pub.comment), ('From the template', 'A', 'C'))

    def test_template_has_no_data_rows(self):
        wb = openpyxl.load_workbook(finders.find(TEMPLATE))
        self.assertEqual(wb.worksheets[0].max_row, 1)


@override_settings(USE_LDAP=False)
class XlsxUploadPageTests(_ExcelCase):
    """The upload page with the real parser (access rules: test_write_access)."""

    def upload(self, path, name='reports.xlsx'):
        """Post the file and follow the redirect to the page that shows the messages.

        Followed by hand: with the '/find' prefix (production settings) the Location includes
        it, and the test client's follow=True would request it as a path (404).
        """
        with open(path, 'rb') as f:
            content = f.read()
        response = self.client.post(page_path('add_reports_from_file_upload'), {
            'file_type': 'xlsx',
            'file': SimpleUploadedFile(name, content),
        })
        self.assertEqual(response.status_code, 302)
        return self.client.get(app_path(response.url))

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_page_links_the_template_and_explains_the_rules(self):
        response = self.client.get(page_path('add_reports_from_file_upload'))
        self.assertContains(response, f'href="{static(TEMPLATE)}"')
        self.assertContains(response, 'All or nothing')

    def test_editor_upload_creates_reports_and_shows_the_messages(self):
        response = self.upload(self.workbook({'Reports': [
            HEADER, row('99-01', 1999, 'Uploaded report', 's990001', 'zqsv')]}))
        self.assertEqual(response.status_code, 200)
        pub = Publication.objects.get(number='99-01')
        self.assertEqual(self.authors(pub), [self.student])
        self.assertEqual(self.supervisors(pub), [self.supervisor])
        shown = [str(m) for m in response.context['messages']]
        self.assertIn("Sheet 'Reports': 1 report created, 0 rows skipped.", shown)

    def test_editor_upload_of_entries_without_title(self):
        response = self.upload(self.workbook({'Reports': [
            HEADER, row(None, 1999, None, 's990001'), row(None, 1999, None, 's990001')]}))
        self.assertEqual(Publication.objects.filter(title='').count(), 2)
        shown = [str(m) for m in response.context['messages']]
        self.assertEqual(shown, [
            "Sheet 'Reports', row 2: report number '99-01' assigned.",
            "Sheet 'Reports', row 3: report number '99-02' assigned.",
            "Sheet 'Reports': 2 reports created, 0 rows skipped.",
        ])

    def test_editor_upload_with_an_error_shows_the_problems_and_saves_nothing(self):
        response = self.upload(self.workbook({'Reports': [
            HEADER, row('99-01', 1999, 'Good', 's990001'), row('99-02', 1999, 'Bad', 'zqxx')]}))
        self.assertFalse(Publication.objects.exists())
        shown = [str(m) for m in response.context['messages']]
        self.assertEqual(shown, [
            NOTHING.format(1, ''),
            "Sheet 'Reports', row 3: author 'zqxx' was not found in the database."])

    def test_wrong_file_extension_is_refused(self):
        response = self.client.post(page_path('add_reports_from_file_upload'), {
            'file_type': 'xlsx',
            'file': SimpleUploadedFile('reports.csv', b'number,year'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Only .xlsx files are supported.', response.context['form'].errors['file'])
        self.assertFalse(Publication.objects.exists())
