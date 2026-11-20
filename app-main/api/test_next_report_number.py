"""Next report number (plan "test coverage" T6).

``publications.utils_models.generate_next_report_number(year)`` gives ``YY-NN``: the last two
digits of the year and the lowest increment from 01 not yet used by a report of that year
(gaps are filled). It is used when a report is saved without a number and by the endpoint
``/api/ajax/next-report-number/?year=<year>`` (the report form updates the number field from
it). Who may call the endpoint is in test_smoke_urls.py.
"""
from django.test import TestCase

from publications.models import Publication
from publications.test_factories import api_path, make_report, report_type
from publications.utils_models import generate_next_report_number


class NextReportNumberTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pubtype = report_type()

    def report(self, number, year):
        return make_report(self.pubtype, number, verified=True, confidential=False, year=year)

    def test_no_reports_yet(self):
        self.assertEqual(generate_next_report_number(2026), '26-01')

    def test_next_after_existing(self):
        self.report('26-01', 2026)
        self.report('26-02', 2026)
        self.assertEqual(generate_next_report_number(2026), '26-03')

    def test_gap_is_filled(self):
        self.report('26-01', 2026)
        self.report('26-03', 2026)
        self.assertEqual(generate_next_report_number(2026), '26-02')

    def test_other_years_do_not_count(self):
        self.report('25-01', 2025)
        self.report('25-02', 2025)
        # Same two digits, other century: numbers are per year.
        self.report('26-01', 1926)
        self.assertEqual(generate_next_report_number(2026), '26-01')
        self.assertEqual(generate_next_report_number(2025), '25-03')

    def test_unverified_and_confidential_reports_count(self):
        make_report(self.pubtype, '26-01', verified=False, confidential=False, year=2026)
        make_report(self.pubtype, '26-02', verified=True, confidential=True, year=2026)
        self.assertEqual(generate_next_report_number(2026), '26-03')

    def test_other_number_formats_do_not_block(self):
        for number in ('26-1', '2026-01', 'x26-01', ''):
            self.report(number, 2026)
        self.assertEqual(generate_next_report_number(2026), '26-01')

    def test_two_digits_up_to_99_then_three(self):
        for increment in range(1, 100):
            self.report(f'26-{increment:02d}', 2026)
        self.assertEqual(generate_next_report_number(2026), '26-100')

    def test_year_2000(self):
        self.assertEqual(generate_next_report_number(2000), '00-01')

    def test_year_as_string(self):
        self.report('26-01', 2026)
        self.assertEqual(generate_next_report_number('2026'), '26-02')


class NextReportNumberEndpointTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        make_report(pubtype, '26-01', verified=True, confidential=False, year=2026)
        cls.path = api_path('get_next_report_number')

    def test_number_for_year(self):
        response = self.client.get(self.path, {'year': 2026})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'number': '26-02'})

    def test_year_without_reports(self):
        response = self.client.get(self.path, {'year': 2031})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'number': '31-01'})

    def test_missing_year_is_400(self):
        for params in ({}, {'year': ''}):
            with self.subTest(params=params):
                response = self.client.get(self.path, params)
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json())

    def test_invalid_year_is_400(self):
        for value in ('abc', '20.26', '2026x'):
            with self.subTest(year=value):
                response = self.client.get(self.path, {'year': value})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {'error': 'Invalid year format'})

    def test_does_not_create_a_report(self):
        before = Publication.objects.count()
        self.client.get(self.path, {'year': 2026})
        self.client.get(self.path, {'year': 2026})
        self.assertEqual(Publication.objects.count(), before)
