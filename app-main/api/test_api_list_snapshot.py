"""The JSON of the list endpoints ``/api/report/`` and ``/api/feature/``, pinned on factory data
(plan release-2026-7 T2a, roadmap FA-R97).

Written against the code before the N+1 fix and run green on it, so the fix can't change the
JSON: same keys in the same order, same list order, same values, for anonymous users, a plain
``dtu_user``, a ``dtu_user`` listed on a confidential report and an ``artek_editor``. The
expected values are literal here (made-up factory data, nothing from the real database).

Visibility (publications.visibility): anonymous users see verified, not confidential reports;
logged-in users see the not confidential ones (verified or not) and the confidential ones they
are listed on; artek_editor sees everything. ``feature_count`` counts all features of a report,
also those the user can't see otherwise (it always did).

Duplicate markers (plan release-2026-7 T7, roadmap FA-R66): two authorships carry match flags.
Only users with ``merge_person`` (artek_editor) get ``match``/``multiple`` in their author dicts;
the JSON of everyone else is the same as before T7. The artek_editor expectations were changed
deliberately in T7 (``EDITOR_MARKERS``).
"""
import datetime
import json

from django.conf import settings
from django.contrib.gis.geos import LineString, MultiLineString
from django.test import TestCase

from publications.models import Authorship, Feature, FileObject
from publications.roles import ARTEK_EDITOR
from publications.test_factories import api_path, make_person, make_report, make_user, report_type

REPORT_KEYS = ['link_to_pdf_associated_with_this_publication', 'feature_count', 'id', 'number',
               'title', 'authors', 'file', 'type', 'confidential']
FEATURE_KEYS = ['points', 'lines', 'polys', 'name', 'type', 'date', 'feature_pk',
                'related_publications']

# Report numbers. The list is ordered by number, descending, with the 9x- numbers last.
PUB1, PUB2, UNVER, CONF, ODD, OLD = '05-01', '05-02', '06-01', '06-02', '07-01', '95-01'

# Which reports each user sees, in list order.
VISIBLE = {
    'anonymous': [ODD, PUB2, PUB1, OLD],
    'dtu_user': [ODD, UNVER, PUB2, PUB1, OLD],
    'listed': [ODD, CONF, UNVER, PUB2, PUB1, OLD],
    'artek_editor': [ODD, CONF, UNVER, PUB2, PUB1, OLD],
}


class ApiListSnapshotTests(TestCase):
    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        cls.ann = make_person('Ann', 'Alpha')
        cls.ben = make_person('Ben', 'Beta')
        cls.sue = make_person('Sue', 'Pervisor')
        listed_person = make_person('Li', 'Sted', id_number='s990011')

        def pdf(number):
            return FileObject.objects.create(file=f'reports/{number}.pdf')

        def report(number, **kwargs):
            kwargs.setdefault('verified', True)
            kwargs.setdefault('confidential', False)
            return make_report(pubtype, number, **kwargs)

        cls.pubs = {
            PUB1: report(PUB1, title='Road embankments', authors=[cls.ann, cls.ben],
                         supervisors=[cls.sue], topics=['Geotechnics'],
                         keywords=['permafrost'], file=pdf(PUB1)),
            PUB2: report(PUB2, title='Water supply', authors=[cls.ben, cls.ann],
                         supervisors=[cls.ann], topics=['Geotechnics', 'Hydrology']),
            UNVER: report(UNVER, title='Unverified harbour', verified=False,
                          authors=[cls.ann], supervisors=[cls.sue], topics=['Hydrology'],
                          keywords=['permafrost'], file=pdf(UNVER)),
            CONF: report(CONF, title='Confidential mine', confidential=True,
                         authors=[cls.ben], supervisors=[listed_person, cls.sue],
                         topics=['Geotechnics'], keywords=['permafrost'], file=pdf(CONF)),
            ODD: report(ODD, title='Snow drift'),
            OLD: report(OLD, title='Old report', authors=[cls.sue]),
        }
        # Authorships created against their author_id order (ann is author 0 but her row
        # comes second): pins the order the API lists authors in.
        Authorship.objects.create(publication=cls.pubs[ODD], person=cls.ben, author_id=1)
        Authorship.objects.create(publication=cls.pubs[ODD], person=cls.ann, author_id=0,
                                  exact_match=True)
        # T7: a relaxed match with several candidates (shown to artek_editor only).
        Authorship.objects.filter(publication=cls.pubs[PUB1], person=cls.ben).update(
            relaxed_match=True, multiple_match=True)

        def feature(name, *publications, **fields):
            f = Feature.objects.create(name=name, date=datetime.date(1999, 7, 1), **fields)
            for publication in publications:     # one by one: the link rows in this order
                f.publications.add(publication)
            return f

        p = cls.pubs
        cls.features = [
            # A line, not a point: a MultiPoint saved through Django is stored as NULL on
            # MariaDB 11.2 (GEOS writes 'MULTIPOINT ((x y))'), so it can't be pinned here.
            feature('F-public', p[PUB1], type='BOREHOLE',
                    lines=MultiLineString(LineString((-50.5, 67.0), (-50.25, 67.5)),
                                          srid=4326)),
            # Linked to several reports, the link rows not in report order: the API lists
            # them by report id (the order the database returns them in).
            feature('F-many', p[CONF], p[PUB2], p[PUB1], p[UNVER], type='SAMPLE'),
            feature('F-unverified', p[UNVER]),
            feature('F-confidential', p[CONF]),
            feature('F-none'),
            feature('', p[OLD], p[PUB2]),
        ]

        cls.users = {
            'anonymous': None,
            'dtu_user': make_user('s990010'),
            'listed': make_user('s990011'),
            'artek_editor': make_user('edit990', ARTEK_EDITOR),
        }

    # ----- expected values, written out by hand -----

    def person(self, p):
        return {'pk': p.pk, 'first': p.first, 'last': p.last}

    # (report, index in its author list) -> what artek_editor's author dict adds (T7).
    EDITOR_MARKERS = {
        (PUB1, 1): {'match': 'relaxed', 'multiple': True},
        (ODD, 1): {'match': 'exact'},
    }

    def expected_report(self, number, user_label='anonymous'):
        ann, ben, sue = self.person(self.ann), self.person(self.ben), self.person(self.sue)
        url = lambda n: f'{settings.MEDIA_URL}reports/{n}.pdf'   # noqa: E731
        values = {
            PUB1: (url(PUB1), 2, 'Road embankments', [ann, ben], f'{PUB1}.pdf', False),
            PUB2: (None, 2, 'Water supply', [ben, ann], None, False),
            UNVER: (url(UNVER), 2, 'Unverified harbour', [ann], f'{UNVER}.pdf', False),
            CONF: (url(CONF), 2, 'Confidential mine', [ben], f'{CONF}.pdf', True),
            ODD: (None, 0, 'Snow drift', [ben, ann], None, False),
            OLD: (None, 1, 'Old report', [sue], None, False),
        }[number]
        link, count, title, authors, file, confidential = values
        if user_label == 'artek_editor':
            authors = [{**author, **self.EDITOR_MARKERS.get((number, i), {})}
                       for i, author in enumerate(authors)]
        return {
            'link_to_pdf_associated_with_this_publication': link,
            'feature_count': count,
            'id': self.pubs[number].pk,
            'number': number,
            'title': title,
            'authors': authors,
            'file': file,
            'type': 'STUDENTREPORT',
            'confidential': confidential,
        }

    def expected_features(self, user_label):
        visible = set(VISIBLE[user_label])

        def pubs(*numbers):
            return [{'id': self.pubs[n].pk, 'number': n, 'title': self.pubs[n].title}
                    for n in numbers if n in visible]

        f = self.features
        rows = [
            (f[0], {'type': 'MultiLineString', 'coordinates': [[[-50.5, 67.0], [-50.25, 67.5]]]},
             'F-public', 'BOREHOLE',
             pubs(PUB1)),
            (f[1], None, 'F-many', 'SAMPLE', pubs(PUB1, PUB2, UNVER, CONF)),
            (f[2], None, 'F-unverified', 'OTHER', pubs(UNVER)),
            (f[3], None, 'F-confidential', 'OTHER', pubs(CONF)),
            (f[4], None, 'F-none', 'OTHER', []),
            (f[5], None, None, 'OTHER', pubs(PUB2, OLD)),
        ]
        result = []
        for feature, line, name, ftype, related in rows:
            # Listed when it has no publication or at least one visible one.
            if feature.publications.exists() and not related:
                continue
            result.append({
                'points': None, 'lines': line, 'polys': None, 'name': name, 'type': ftype,
                'date': '1999-07-01', 'feature_pk': feature.pk, 'related_publications': related,
            })
        return result

    # ----- helpers -----

    def get(self, user_label, path, params=None):
        user = self.users[user_label]
        if user is None:
            self.client.logout()
        else:
            self.client.force_login(user)
        response = self.client.get(path, params or {})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def assert_reports(self, data, numbers, user_label):
        self.assertEqual([r['number'] for r in data], numbers)
        for item in data:
            self.assertEqual(list(item.keys()), REPORT_KEYS)
            self.assertEqual(item, self.expected_report(item['number'], user_label))

    # ----- tests -----

    def test_report_list(self):
        for label, numbers in VISIBLE.items():
            with self.subTest(user=label):
                self.assert_reports(self.get(label, api_path('report-list')), numbers, label)

    def test_report_list_filtered(self):
        filters = {
            'topic': ({'topic': 'Geotechnics'}, {PUB1, PUB2, CONF}),
            'author_id': ({'author_id': self.ann.pk}, {PUB1, PUB2, UNVER, ODD}),
            'supervisor_id': ({'supervisor_id': self.sue.pk}, {PUB1, UNVER, CONF}),
            'q': ({'q': 'permafrost'}, {PUB1, UNVER, CONF}),
            'q title': ({'q': 'water'}, {PUB2}),
        }
        for label, numbers in VISIBLE.items():
            for name, (params, matching) in filters.items():
                with self.subTest(user=label, filter=name):
                    self.assert_reports(self.get(label, api_path('report-list'), params),
                                        [n for n in numbers if n in matching], label)

    def test_report_detail(self):
        for label, numbers in VISIBLE.items():
            for number in numbers:
                with self.subTest(user=label, report=number):
                    item = self.get(label, api_path('report-detail', pk=self.pubs[number].pk))
                    self.assertEqual(list(item.keys()), REPORT_KEYS)
                    self.assertEqual(item, self.expected_report(number, label))

    def test_feature_list(self):
        for label in VISIBLE:
            with self.subTest(user=label):
                data = self.get(label, api_path('feature-list'))
                for item in data:
                    self.assertEqual(list(item.keys()), FEATURE_KEYS)
                    if item['lines'] is not None:
                        item['lines'] = json.loads(item['lines'])
                # The feature list has no order_by (database order); compare by pk.
                self.assertEqual(sorted(data, key=lambda i: i['feature_pk']),
                                 self.expected_features(label))

    def test_feature_list_of_a_publication(self):
        for label in VISIBLE:
            with self.subTest(user=label):
                data = self.get(label, api_path('feature-list'),
                                {'publication_id': self.pubs[PUB2].pk})
                expected = [f for f in self.expected_features(label)
                            if f['feature_pk'] in (self.features[1].pk, self.features[5].pk)]
                self.assertEqual(sorted(data, key=lambda i: i['feature_pk']), expected)
