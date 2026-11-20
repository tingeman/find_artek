"""Filters and order of the report list ``/api/report/`` (plan "test coverage" T6).

Who sees which report is tested in test_report_api.py; here every report is verified and not
confidential, so every user sees all of them, and the tests are about the filters ``topic``,
``author_id``, ``supervisor_id``, ``q`` (title, abstract, keyword) and the order.
"""
from django.test import TestCase

from publications.test_factories import api_path, make_person, make_report, report_type


class ReportListFilterTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        cls.ann = make_person('Ann', 'Alpha')
        cls.ben = make_person('Ben', 'Beta')
        cls.sue = make_person('Sue', 'Pervisor')

        def report(number, **kwargs):
            return make_report(pubtype, number, verified=True, confidential=False, **kwargs)

        report('05-01', title='Road embankments on permafrost',
               abstract='Thaw settlement below a gravel road.',
               authors=[cls.ann, cls.ben], supervisors=[cls.sue],
               topics=['Geotechnics'], keywords=['permafrost', 'roads'])
        report('05-02', title='Water supply of a settlement',
               abstract='Groundwater in the active layer.',
               authors=[cls.ben], supervisors=[cls.sue, cls.ann],
               topics=['Hydrology', 'Geotechnics'], keywords=['groundwater'])
        report('06-01', title='Harbour foundations',
               abstract='Pile foundations in marine clay.',
               authors=[cls.ann], topics=['Hydrology'], keywords=['clay', 'Permafrost'])
        report('06-02', title='Snow drift at buildings', abstract='Wind tunnel study.')
        cls.path = api_path('report-list')

    def numbers(self, **params):
        response = self.client.get(self.path, params)
        self.assertEqual(response.status_code, 200)
        result = [r['number'] for r in response.json()]
        self.assertEqual(len(result), len(set(result)), 'duplicate rows')
        return sorted(result)

    def test_no_filter_lists_everything(self):
        self.assertEqual(self.numbers(), ['05-01', '05-02', '06-01', '06-02'])

    def test_topic(self):
        self.assertEqual(self.numbers(topic='Geotechnics'), ['05-01', '05-02'])
        self.assertEqual(self.numbers(topic='Hydrology'), ['05-02', '06-01'])

    def test_topic_is_the_exact_name(self):
        for value in ('geo', 'Geotechnic'):
            with self.subTest(topic=value):
                self.assertEqual(self.client.get(self.path, {'topic': value}).status_code, 404)

    def test_empty_topic_is_no_filter(self):
        self.assertEqual(self.numbers(topic=''), ['05-01', '05-02', '06-01', '06-02'])

    def test_author_id(self):
        self.assertEqual(self.numbers(author_id=self.ann.pk), ['05-01', '06-01'])
        self.assertEqual(self.numbers(author_id=self.ben.pk), ['05-01', '05-02'])
        # Supervising is not authoring.
        self.assertEqual(self.numbers(author_id=self.sue.pk), [])

    def test_supervisor_id(self):
        self.assertEqual(self.numbers(supervisor_id=self.sue.pk), ['05-01', '05-02'])
        self.assertEqual(self.numbers(supervisor_id=self.ann.pk), ['05-02'])
        self.assertEqual(self.numbers(supervisor_id=self.ben.pk), [])

    def test_non_numeric_person_id_is_400(self):
        for param in ('author_id', 'supervisor_id'):
            for value in ('abc', '1.5', '12x'):
                with self.subTest(param=param, value=value):
                    response = self.client.get(self.path, {param: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(param, response.json())

    def test_unknown_person_gives_an_empty_list(self):
        self.assertEqual(self.numbers(author_id=999999), [])
        self.assertEqual(self.numbers(supervisor_id=999999), [])

    def test_q_searches_title(self):
        self.assertEqual(self.numbers(q='harbour'), ['06-01'])

    def test_q_searches_abstract(self):
        self.assertEqual(self.numbers(q='tunnel'), ['06-02'])
        # 'settlement' is in the abstract of 05-01 and the title of 05-02.
        self.assertEqual(self.numbers(q='settlement'), ['05-01', '05-02'])

    def test_q_searches_keywords(self):
        self.assertEqual(self.numbers(q='groundwater'), ['05-02'])
        # Case-insensitive; 05-01 has it in title and keyword, 06-01 only as a keyword.
        self.assertEqual(self.numbers(q='PERMAFROST'), ['05-01', '06-01'])

    def test_q_part_of_a_word(self):
        self.assertEqual(self.numbers(q='found'), ['06-01'])

    def test_q_all_terms_must_match(self):
        self.assertEqual(self.numbers(q='permafrost road'), ['05-01'])
        self.assertEqual(self.numbers(q='permafrost clay'), ['06-01'])
        self.assertEqual(self.numbers(q='permafrost wind'), [])

    def test_q_quoted_phrase(self):
        self.assertEqual(self.numbers(q='"gravel road"'), ['05-01'])
        self.assertEqual(self.numbers(q='"road gravel"'), [])

    def test_q_does_not_search_other_fields(self):
        # Author names and report numbers are not searched.
        self.assertEqual(self.numbers(q='Alpha'), [])
        self.assertEqual(self.numbers(q='06-02'), [])

    def test_filters_combine(self):
        self.assertEqual(self.numbers(topic='Geotechnics', author_id=self.ann.pk), ['05-01'])
        self.assertEqual(self.numbers(topic='Hydrology', supervisor_id=self.ann.pk), ['05-02'])
        self.assertEqual(self.numbers(author_id=self.ann.pk, q='permafrost'),
                         ['05-01', '06-01'])
        self.assertEqual(self.numbers(author_id=self.ben.pk, supervisor_id=self.ann.pk),
                         ['05-02'])

    def test_report_fields(self):
        response = self.client.get(self.path, {'q': 'harbour'})
        self.assertEqual(response.status_code, 200)
        [entry] = response.json()
        self.assertEqual(set(entry), {
            'link_to_pdf_associated_with_this_publication', 'feature_count', 'id', 'number',
            'title', 'authors', 'file', 'type', 'confidential'})
        self.assertEqual(entry['title'], 'Harbour foundations')
        self.assertEqual(entry['type'], 'STUDENTREPORT')
        self.assertEqual(entry['authors'], [{'pk': self.ann.pk, 'first': 'Ann', 'last': 'Alpha'}])
        self.assertEqual(entry['feature_count'], 0)
        self.assertIsNone(entry['file'])
        self.assertIsNone(entry['link_to_pdf_associated_with_this_publication'])


class ReportListOrderTests(TestCase):
    """Report numbers of the 2000s and later first, then those of the 1990s ('9x-'), each
    group by number descending (as text)."""

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        for number, year in (('98-03', 1998), ('05-10', 2005), ('26-01', 2026), ('91-12', 1991),
                             ('05-02', 2005), ('10-01', 2010), ('99-01', 1999)):
            make_report(pubtype, number, verified=True, confidential=False, year=year)

    def test_order(self):
        response = self.client.get(api_path('report-list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['number'] for r in response.json()],
                         ['26-01', '10-01', '05-10', '05-02', '99-01', '98-03', '91-12'])

    def test_order_with_filter(self):
        response = self.client.get(api_path('report-list'), {'q': 'Report'})
        self.assertEqual([r['number'] for r in response.json()],
                         ['26-01', '10-01', '05-10', '05-02', '99-01', '98-03', '91-12'])
