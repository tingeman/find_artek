"""Excel import of reports (register_from_file.xlsx_pubs, and the upload page
add_reports_from_file_upload with the real parser).

The workbooks are built in the test with openpyxl; USE_LDAP is off unless a test says
otherwise (the directory is then mocked). Person resolution details are in
test_import_ldap_off; here: which reports are created, with which authors, supervisors and
topics, and which rows or sheets are reported instead of imported.
All names, numbers and study numbers are made up.
"""

import os
import shutil
import tempfile
from unittest import mock

import openpyxl
from django.contrib import messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from publications import register_from_file
from publications.models import Person, Publication, PubType
from publications.roles import ARTEK_EDITOR
from publications.test_factories import (
    ldap_entry, make_person, make_report, make_user, page_path,
)

HEADER = ['number', 'year', 'title', 'type', 'topic', 'authors', 'supervisors']


def row(number, year, title, authors='', supervisors='', topic='', type_='STUDENTREPORT'):
    return [number, year, title, type_, topic, authors, supervisors]


class _ExcelCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.report_type = PubType.objects.create(type='STUDENTREPORT')
        PubType.objects.create(type='ARTICLE')
        cls.user = make_user('zqeditor', ARTEK_EDITOR)
        cls.student = make_person('Stu', 'Zqdent', id_number='s990001')
        cls.supervisor = make_person('Su', 'Zqvisor', initials='zqsv')

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

    def authors(self, pub):
        return [a.person for a in pub.authorship_set.order_by('author_id')]

    def supervisors(self, pub):
        return [s.person for s in pub.supervisorship_set.order_by('supervisor_id')]


@override_settings(USE_LDAP=False)
class XlsxImportTests(_ExcelCase):

    def test_reports_are_created_with_persons_and_topics(self):
        result = self.import_sheets({'Reports': [
            HEADER,
            row('99-01', 1999, 'Permafrost at Zqville', 'Jane Zqroe and s990001', 'zqsv',
                topic='Permafrost Geology'),
            row('99-02', 1999, 'Roads on ice', 'Zqlee, Ann', 'zqsv'),
        ]})
        self.assertEqual(result, [(
            messages.SUCCESS, "2 of 2 publications registered/updated from sheet 'Reports'.")])

        pub = Publication.objects.get(number='99-01')
        self.assertEqual((pub.title, pub.year, pub.type), ('Permafrost at Zqville', 1999,
                                                           self.report_type))
        self.assertEqual((pub.created_by, pub.modified_by), (self.user, self.user))
        # Imported reports are unvalidated (hidden from anonymous users) until verified.
        self.assertFalse(pub.verified)

        authors = self.authors(pub)
        self.assertEqual([(p.first, p.last) for p in authors],
                         [('Jane', 'Zqroe'), ('Stu', 'Zqdent')])
        self.assertEqual(authors[1], self.student)           # matched by study number
        self.assertEqual(authors[0].created_by, self.user)   # new person
        self.assertEqual(self.supervisors(pub), [self.supervisor])
        self.assertEqual(sorted(t.topic for t in pub.publication_topics.all()),
                         ['Geology', 'Permafrost'])

        other = Publication.objects.get(number='99-02')
        self.assertEqual([(p.first, p.last) for p in self.authors(other)], [('Ann', 'Zqlee')])
        self.assertEqual(self.supervisors(other), [self.supervisor])

    def test_row_without_topic_is_imported(self):
        # Before the fix, an empty topic cell raised AttributeError and stopped the import
        # after the rows before it had been saved.
        result = self.import_sheets({'Reports': [
            HEADER, row('99-01', 1999, 'No topic'), row('99-02', 1999, 'Next')]})
        self.assertEqual(Publication.objects.get(number='99-01').publication_topics.count(), 0)
        self.assertTrue(Publication.objects.filter(number='99-02').exists())
        self.assertEqual(result[-1][0], messages.SUCCESS)

    def test_name_matching_an_existing_person_still_creates_a_flagged_person(self):
        existing = Person.objects.create(name='Jane Zqroe')
        self.import_sheets({'Reports': [HEADER, row('99-01', 1999, 'T', 'Jane Zqroe')]})
        link = Publication.objects.get(number='99-01').authorship_set.get()
        self.assertNotEqual(link.person, existing)
        self.assertTrue(link.exact_match)

    def test_year_is_taken_from_the_number(self):
        self.import_sheets({'Reports': [HEADER, row('98-07', None, 'T')]})
        self.assertEqual(Publication.objects.get(number='98-07').year, 1998)

    def test_number_is_generated_from_the_year(self):
        self.import_sheets({'Reports': [HEADER, row(None, 1997, 'T')]})
        self.assertEqual(Publication.objects.get(title='T').number, '97-01')

    def test_existing_number_gets_the_next_free_number(self):
        make_report(self.report_type, '99-01', verified=True, confidential=False, year=1999)
        result = self.import_sheets({'Reports': [HEADER, row('99-01', 1999, 'New one')]})
        self.assertEqual(Publication.objects.get(title='New one').number, '99-02')
        self.assertIn((messages.INFO, "Publication number '99-01' already exists, assigning "
                                      "next available number '99-02'."), result)
        self.assertEqual(Publication.objects.get(number='99-01').title, 'Report 99-01')

    def test_row_without_number_and_year_is_skipped(self):
        result = self.import_sheets({'Reports': [
            HEADER, row('99-01', 1999, 'Good'), row(None, None, 'No number')]})
        self.assertFalse(Publication.objects.filter(title='No number').exists())
        self.assertIn(
            (messages.INFO, "1 of 2 publications registered/updated from sheet 'Reports'."),
            result)

    def test_unsupported_type_is_skipped(self):
        result = self.import_sheets({'Reports': [
            HEADER, row('99-01', 1999, 'An article', type_='ARTICLE')]})
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(result[0][0], messages.WARNING)
        self.assertIn('Skipping report', result[0][1])

    def test_sheet_missing_columns_is_not_imported(self):
        result = self.import_sheets({
            'Partial': [['number', 'year', 'title', 'type', 'topic'],
                        ['99-01', 1999, 'T', 'STUDENTREPORT', '']],
            'Empty': [],
        })
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(result, [
            (messages.WARNING,
             "Sheet 'Partial' is missing columns: authors, supervisors, nothing imported."),
            (messages.WARNING, "Sheet 'Empty' is empty, nothing imported."),
        ])

    def test_persons_that_cannot_be_resolved_are_reported(self):
        result = self.import_sheets({'Reports': [
            HEADER, row('99-01', 1999, 'T', 'van Zqroe and s990999', 'zqxx')]})
        pub = Publication.objects.get(number='99-01')
        self.assertEqual(self.authors(pub), [])
        self.assertEqual(self.supervisors(pub), [])
        self.assertEqual(result[:3], [
            (messages.ERROR, "The author name 'van Zqroe' does not contain enough information "
                             "to add it to the database (must contain at least given and sur "
                             "names)."),
            (messages.WARNING, "Author identified by 's990999' was not found in database. "
                               "Please add author manually!"),
            (messages.WARNING, "Supervisor identified by 'zqxx' was not found in database. "
                               "Please add supervisor manually!"),
        ])


@override_settings(USE_LDAP=True)
class XlsxImportLdapTests(_ExcelCase):

    def test_study_number_not_in_directory_names_the_role_in_lower_case(self):
        # Before the fix: "... Please add Author manually!" (the {0} placeholder twice).
        with mock.patch('publications.utils_person.find_ldap_person', return_value=[]):
            result = self.import_sheets({'Reports': [HEADER, row('99-01', 1999, 'T',
                                                                 's990999')]})
        self.assertEqual(result[0], (
            messages.WARNING,
            "Author identified by 's990999' was not found in database. "
            "Please add author manually!"))


@override_settings(USE_LDAP=False)
class XlsxUploadPageTests(_ExcelCase):
    """The upload page with the real parser (access rules: test_write_access)."""

    def test_editor_upload_creates_reports_and_shows_the_messages(self):
        with open(self.workbook({'Reports': [
                HEADER, row('99-01', 1999, 'Uploaded report', 's990001', 'zqsv')]}), 'rb') as f:
            content = f.read()
        self.client.force_login(self.user)
        response = self.client.post(page_path('add_reports_from_file_upload'), {
            'file_type': 'xlsx',
            'file': SimpleUploadedFile('reports.xlsx', content),
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        pub = Publication.objects.get(number='99-01')
        self.assertEqual(self.authors(pub), [self.student])
        self.assertEqual(self.supervisors(pub), [self.supervisor])
        shown = [str(m) for m in response.context['messages']]
        self.assertIn("1 of 1 publications registered/updated from sheet 'Reports'.", shown)

    def test_wrong_file_extension_is_refused(self):
        self.client.force_login(self.user)
        response = self.client.post(page_path('add_reports_from_file_upload'), {
            'file_type': 'xlsx',
            'file': SimpleUploadedFile('reports.csv', b'number,year'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Only .xlsx files are supported.', response.context['form'].errors['file'])
        self.assertFalse(Publication.objects.exists())


@override_settings(USE_LDAP=True)
class XlsxImportLdapMatchTests(_ExcelCase):

    def test_supervisor_from_directory_is_not_linked_to_a_person_with_empty_initials(self):
        # The database has a student with empty initials (cls.student). Before the fix of
        # get_or_create_person_from_ldap, the supervisor found in the directory by initials
        # was linked to that student.
        entry = ldap_entry('Zqvisor', 'Ny', title='Lektor', employee_id='99002',
                           department='Zq Dept', initials='zqny')
        with mock.patch('publications.utils_person.find_ldap_person',
                        return_value=[entry]) as find:
            self.import_sheets({'Reports': [HEADER, row('99-01', 1999, 'T', '', 'zqny')]})
        find.assert_called_once_with(initials='zqny')
        [supervisor] = self.supervisors(Publication.objects.get(number='99-01'))
        self.assertNotEqual(supervisor, self.student)
        self.assertEqual((supervisor.initials, supervisor.id_number, supervisor.last),
                         ('zqny', '99002', 'Zqvisor'))
