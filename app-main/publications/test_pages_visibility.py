"""The report page and the feature page follow the visibility rule (roadmap FA-R75, plan
PLAN_confidential T3).

ReportView and FeatureView use permissions.VIEW (publications.visibility): the page is shown to
users who may see the entry; a hidden entry sends anonymous users to the login (302 with next)
and is 404 for logged-in users, so its existence isn't confirmed; an unknown pk is 404.
The feature page lists only the visible reports of the feature, with a link to each report
page; the report page shows a "Confidential" badge on confidential reports.

The expected answers are written out by hand (not computed from the code under test).
"""
import datetime

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from publications.models import (
    Authorship, Feature, FileObject, ImageObject, ImageObjectship, Person, Publication, PubType,
)
from publications.roles import ARTEK_EDITOR, ARTEK_STAFF, DTU_USER
from publications.test_upload_appendix_access import _app_path

# Reports of the fixture (by number); their titles are 'Hidden-check title <number>'.
P = '98-01'    # public: verified, not confidential
U = '98-02'    # unverified, not confidential
C = '98-03'    # confidential, verified
CU = '98-04'   # confidential, unverified

USERS = ('anonymous', 'dtu', 'author', 'staff', 'artek_editor', 'superuser')

# Expected status of the report page per report and user: 200 shown, 302 login, 404 hidden.
REPORT_STATUS = {
    P: {'anonymous': 200, 'dtu': 200, 'author': 200, 'staff': 200, 'artek_editor': 200,
        'superuser': 200},
    U: {'anonymous': 302, 'dtu': 200, 'author': 200, 'staff': 200, 'artek_editor': 200,
        'superuser': 200},
    C: {'anonymous': 302, 'dtu': 404, 'author': 200, 'staff': 404, 'artek_editor': 200,
        'superuser': 200},
    CU: {'anonymous': 302, 'dtu': 404, 'author': 200, 'staff': 404, 'artek_editor': 200,
         'superuser': 200},
}

# Features: name -> reports.
FEATURES = {
    'F-public': {P},
    'F-hidden': {C, CU},           # only confidential reports
    'F-mixed': {P, U, C, CU},
    'F-none': set(),
}

# Expected status of the feature page per feature and user.
FEATURE_STATUS = {
    'F-public': {u: 200 for u in USERS},
    'F-hidden': REPORT_STATUS[C],
    'F-mixed': {u: 200 for u in USERS},
    'F-none': {u: 200 for u in USERS},
}

# Reports each user may see (to check which titles the feature page lists).
VISIBLE = {
    user: {number for number, statuses in REPORT_STATUS.items() if statuses[user] == 200}
    for user in USERS
}


def title(number):
    return f'Hidden-check title {number}'


class PageVisibilityTestBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')

        def report(number, verified, confidential):
            return Publication.objects.create(
                type=pubtype, number=number, title=title(number), year=1998,
                verified=verified, confidential=confidential)

        cls.pubs = {
            P: report(P, verified=True, confidential=False),
            U: report(U, verified=False, confidential=False),
            C: report(C, verified=True, confidential=True),
            CU: report(CU, verified=False, confidential=True),
        }
        author = Person.objects.create(first='Stu', last='Dent', id_number='s980001')
        for pub in cls.pubs.values():
            Authorship.objects.create(publication=pub, person=author, author_id=0)

        cls.features = {}
        for name, numbers in FEATURES.items():
            feature = Feature.objects.create(name=name, date=datetime.date(1998, 7, 1))
            feature.publications.set([cls.pubs[n] for n in numbers])
            cls.features[name] = feature

        groups = {name: Group.objects.get(name=name)
                  for name in (DTU_USER, ARTEK_STAFF, ARTEK_EDITOR)}

        def user(username, *group_names, superuser=False):
            if superuser:
                u = User.objects.create_superuser(username, password='x')
            else:
                u = User.objects.create_user(username, password='x')
            u.groups.add(groups[DTU_USER], *(groups[g] for g in group_names))
            return u

        cls.users = {
            'anonymous': None,
            'dtu': user('s980999'),                       # not listed
            'author': user('S980001'),                    # author (id_number, other case)
            'staff': user('stfx', ARTEK_STAFF),           # not listed
            'artek_editor': user('edtx', ARTEK_EDITOR),   # not listed
            'superuser': user('root98', superuser=True),
        }

    def get_as(self, user_key, url_name, pk):
        self.client.logout()
        user = self.users[user_key]
        if user is not None:
            self.client.force_login(user)
        return self.client.get(_app_path(reverse(f'publications:{url_name}', kwargs={'pk': pk})))

    def assertStatus(self, response, expected):
        if expected == 302:
            self.assertEqual(response.status_code, 302)
            self.assertTrue(
                response['Location'].startswith(resolve_url(settings.LOGIN_URL) + '?next='),
                response['Location'])
        else:
            self.assertEqual(response.status_code, expected)


class ReportPageVisibilityTests(PageVisibilityTestBase):

    def test_report_page_matrix(self):
        for number, statuses in REPORT_STATUS.items():
            for user_key, expected in statuses.items():
                with self.subTest(report=number, user=user_key):
                    response = self.get_as(user_key, 'report', self.pubs[number].pk)
                    self.assertStatus(response, expected)
                    body = response.content.decode()
                    if expected == 200:
                        self.assertTemplateUsed(response, 'publications/report.html')
                        self.assertIn(title(number), body)
                    else:
                        self.assertNotIn(title(number), body)

    def test_anonymous_login_redirect_comes_back_to_the_report(self):
        response = self.get_as('anonymous', 'report', self.pubs[C].pk)
        self.assertStatus(response, 302)
        self.assertIn(f'report/{self.pubs[C].pk}/', response['Location'])

    def test_unknown_report_is_404(self):
        missing = max(p.pk for p in self.pubs.values()) + 1000
        for user_key in USERS:
            with self.subTest(user=user_key):
                self.assertEqual(self.get_as(user_key, 'report', missing).status_code, 404)

    def test_confidential_badge_on_confidential_report(self):
        for user_key in ('author', 'artek_editor', 'superuser'):
            for number in (C, CU):
                with self.subTest(user=user_key, report=number):
                    response = self.get_as(user_key, 'report', self.pubs[number].pk)
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'confidential-badge')
                    self.assertContains(response, 'Confidential</span>')

    def test_no_badge_on_report_that_is_not_confidential(self):
        for user_key in ('anonymous', 'author', 'artek_editor'):
            with self.subTest(user=user_key):
                response = self.get_as(user_key, 'report', self.pubs[P].pk)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'confidential-badge')

    def test_report_lists_only_visible_features(self):
        # A feature of a visible report is visible by the rule; the context holds exactly the
        # report's features.
        response = self.get_as('dtu', 'report', self.pubs[P].pk)
        names = {f.name for f in response.context['associated_features']}
        self.assertEqual(names, {'F-public', 'F-mixed'})


class FeaturePageVisibilityTests(PageVisibilityTestBase):

    def test_feature_page_matrix(self):
        for name, statuses in FEATURE_STATUS.items():
            for user_key, expected in statuses.items():
                with self.subTest(feature=name, user=user_key):
                    response = self.get_as(user_key, 'feature', self.features[name].pk)
                    self.assertStatus(response, expected)
                    body = response.content.decode()
                    if expected == 200:
                        self.assertTemplateUsed(response, 'publications/feature.html')
                        self.assertIn(name, body)
                    shown = VISIBLE[user_key] if expected == 200 else set()
                    for number in FEATURES[name]:
                        if number in shown:
                            self.assertIn(title(number), body)
                        else:
                            # A hidden report's title never appears.
                            self.assertNotIn(title(number), body)

    def test_feature_page_links_to_visible_reports(self):
        response = self.get_as('dtu', 'feature', self.features['F-mixed'].pk)
        self.assertEqual(response.status_code, 200)
        for number in (P, U):
            url = reverse('publications:report', kwargs={'pk': self.pubs[number].pk})
            self.assertContains(response, f'href="{url}"')
        for number in (C, CU):
            url = reverse('publications:report', kwargs={'pk': self.pubs[number].pk})
            self.assertNotContains(response, f'href="{url}"')
        self.assertEqual(
            [p.number for p in response.context['visible_reports']], [P, U])

    def test_unknown_feature_is_404(self):
        missing = max(f.pk for f in self.features.values()) + 1000
        for user_key in USERS:
            with self.subTest(user=user_key):
                self.assertEqual(self.get_as(user_key, 'feature', missing).status_code, 404)

    def test_file_and_image_links_point_to_media(self):
        # Only the names are set; no file is written or read.
        feature = self.features['F-public']
        file_obj = FileObject.objects.create(file='features/98-01/data_sheet.csv')
        image = ImageObject.objects.create(image='features/98-01/photo_1.jpg', caption='Photo')
        feature.files.add(file_obj)
        ImageObjectship.objects.create(imageobject=image, feature=feature)

        response = self.get_as('anonymous', 'feature', feature.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{file_obj.file.url}"')
        self.assertContains(response, f'href="{image.image.url}"')
        self.assertTrue(file_obj.file.url.startswith(settings.MEDIA_URL), file_obj.file.url)
        self.assertContains(response, '>data_sheet.csv</a>')
        self.assertContains(response, '>photo_1.jpg</a>')
