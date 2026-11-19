"""The visibility rule of publications and features (roadmap FA-R75, plan PLAN_confidential T2).

A publication is visible to anonymous users (and user None) when it is verified and not
confidential; to logged-in users when it is not confidential, or they are listed on it
(author, supervisor or editor: user name = id_number or initials, ignoring case, empty values
never match), or they are in ``artek_editor`` or superusers. A feature is visible when it has no
publication or at least one visible one.

Every user of the matrix is checked against every publication and feature in the queryset form
(visible_publications, visible_features), the object form (can_view_publication,
can_view_feature) and permissions.user_may(..., VIEW, ...): all three must give the expected
answer, which is written out by hand below (not computed from the code under test).
"""
import datetime

from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import TestCase

from publications.models import (
    Authorship, Editorship, Feature, Person, Publication, PubType, Supervisorship,
)
from publications.permissions import EDIT, VIEW, user_may
from publications.roles import ARTEK_EDITOR, ARTEK_STAFF, DTU_USER
from publications.visibility import (
    can_view_feature, can_view_publication, listed_on_q, sees_all, visible_features,
    visible_publications,
)

# Publications of the fixture (by number).
P = '99-01'    # public: verified, not confidential
U = '99-02'    # unverified, not confidential
C = '99-03'    # confidential, verified
CU = '99-04'   # confidential, unverified
CO = '99-05'   # confidential, verified, nobody of the matrix listed (only the blank person)
ALL = {P, U, C, CU, CO}

# Which users are listed on which publications (all listed persons are on P, U, C and CU).
LISTED = {P, U, C, CU}

# Expected visible publications per user of the matrix.
EXPECTED = {
    'anonymous': {P},
    'none': {P},
    'dtu': {P, U},
    'author': {P, U, C, CU},           # listed by id_number (other case)
    'supervisor': {P, U, C, CU},       # listed by initials (other case)
    'editor_listed': {P, U, C, CU},    # listed as editor (by initials)
    'staff': {P, U},                   # artek_staff, not listed
    'artek_editor': ALL,
    'superuser': ALL,
    'blank': {P, U},                   # logged in with an empty user name
}

# Features: name -> publications.
FEATURES = {
    'F-public': {P},
    'F-unverified': {U},
    'F-confidential': {C, CU},
    'F-other': {CO},
    'F-mixed': {P, U, C, CO},
    'F-none': set(),
}


def expected_features(visible):
    """Feature name -> its visible publications, for the features visible with ``visible``."""
    return {name: pubs & visible for name, pubs in FEATURES.items()
            if not pubs or pubs & visible}


class VisibilityMatrixTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')

        def report(number, verified, confidential, comment=''):
            return Publication.objects.create(
                type=pubtype, number=number, title=f'Report {number}', year=1999,
                verified=verified, confidential=confidential, comment=comment)

        cls.pubs = {
            P: report(P, verified=True, confidential=False),
            U: report(U, verified=False, confidential=False),
            C: report(C, verified=True, confidential=True),
            CU: report(CU, verified=False, confidential=True),
            CO: report(CO, verified=True, confidential=True),
        }

        author = Person.objects.create(first='Stu', last='Dent', id_number='S990001')
        supervisor = Person.objects.create(first='Su', last='Pervisor', initials='SuPv')
        editor = Person.objects.create(first='Ed', last='Itor', initials='edtr')
        # A person without id_number and initials: must never match (also not an empty
        # user name). Listed on every publication.
        blank = Person.objects.create(first='No', last='Ids')
        for number in sorted(LISTED):
            pub = cls.pubs[number]
            Authorship.objects.create(publication=pub, person=author, author_id=0)
            Supervisorship.objects.create(publication=pub, person=supervisor, supervisor_id=0)
            Editorship.objects.create(publication=pub, person=editor, editor_id=0)
        for i, pub in enumerate(cls.pubs.values()):
            Authorship.objects.create(publication=pub, person=blank, author_id=10 + i)

        cls.features = {}
        for name, numbers in FEATURES.items():
            feature = Feature.objects.create(name=name, date=datetime.date(1999, 7, 1))
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

        cls.user_pks = {
            'dtu': user('s990999').pk,
            'author': user('s990001').pk,
            'supervisor': user('supv').pk,
            'editor_listed': user('EDTR').pk,
            'staff': user('stfo', ARTEK_STAFF).pk,
            'artek_editor': user('edit', ARTEK_EDITOR).pk,
            'superuser': user('root', superuser=True).pk,
        }
        # create_user refuses an empty user name; the database doesn't.
        blank_user = User.objects.create(username='')
        blank_user.groups.add(groups[DTU_USER])
        cls.user_pks['blank'] = blank_user.pk

    def get_user(self, key):
        """A fresh user instance (no cached answers), AnonymousUser or None."""
        if key == 'anonymous':
            return AnonymousUser()
        if key == 'none':
            return None
        return User.objects.get(pk=self.user_pks[key])

    def test_matrix_covers_all_users(self):
        self.assertEqual(set(EXPECTED), set(self.user_pks) | {'anonymous', 'none'})

    def test_publications_queryset_form(self):
        for key, expected in EXPECTED.items():
            with self.subTest(user=key):
                numbers = list(visible_publications(Publication.objects.all(), self.get_user(key))
                               .values_list('number', flat=True))
                self.assertEqual(len(numbers), len(set(numbers)), 'duplicate rows')
                self.assertEqual(set(numbers), expected)

    def test_publications_object_form_and_view_action(self):
        for key, expected in EXPECTED.items():
            user = self.get_user(key)
            for number, pub in self.pubs.items():
                with self.subTest(user=key, publication=number):
                    self.assertEqual(can_view_publication(user, pub), number in expected)
                    self.assertEqual(user_may(user, VIEW, pub), number in expected)

    def test_features_queryset_form(self):
        for key, visible in EXPECTED.items():
            user = self.get_user(key)
            with self.subTest(user=key):
                features = list(visible_features(Feature.objects.all(), user))
                names = [f.name for f in features]
                self.assertEqual(len(names), len(set(names)), 'duplicate rows')
                # A visible feature lists only its visible publications.
                listed = {f.name: set(visible_publications(f.publications.all(), user)
                                      .values_list('number', flat=True))
                          for f in features}
                self.assertEqual(listed, expected_features(visible))

    def test_features_object_form_and_view_action(self):
        for key, visible in EXPECTED.items():
            user = self.get_user(key)
            expected = expected_features(visible)
            for name, feature in self.features.items():
                with self.subTest(user=key, feature=name):
                    self.assertEqual(can_view_feature(user, feature), name in expected)
                    self.assertEqual(user_may(user, VIEW, feature), name in expected)

    def test_listed_on_q(self):
        listed_users = {'author', 'supervisor', 'editor_listed'}
        for key in EXPECTED:
            user = self.get_user(key)
            with self.subTest(user=key):
                numbers = set(Publication.objects.filter(listed_on_q(user))
                              .values_list('number', flat=True))
                self.assertEqual(numbers, LISTED if key in listed_users else set())
                # Same answer as the object form.
                for number, pub in self.pubs.items():
                    self.assertEqual(pub.is_own_publication_of(user), number in numbers)

    def test_listed_on_q_through_features(self):
        user = self.get_user('supervisor')
        names = set(Feature.objects.filter(listed_on_q(user, 'publications__'))
                    .values_list('name', flat=True))
        self.assertEqual(names, {'F-public', 'F-unverified', 'F-confidential', 'F-mixed'})
        self.assertFalse(Feature.objects.filter(listed_on_q(None, 'publications__')).exists())

    def test_sees_all(self):
        for key in EXPECTED:
            with self.subTest(user=key):
                self.assertEqual(sees_all(self.get_user(key)), key in ('artek_editor', 'superuser'))

    def test_visible_publications_keeps_other_filters(self):
        user = self.get_user('author')
        qs = visible_publications(Publication.objects.filter(verified=True), user)
        self.assertEqual(set(qs.values_list('number', flat=True)), {P, C})

    def test_comment_no_longer_matters(self):
        # Since migration 0004 only the field decides; the keyword in the comment is ignored.
        pub = self.pubs[P]
        pub.comment = 'confidential'
        pub.save()
        self.assertTrue(can_view_publication(None, pub))
        self.assertIn(pub, visible_publications(Publication.objects.all(), None))

    def test_view_action_needs_a_publication_or_feature(self):
        with self.assertRaises(ValueError):
            user_may(self.get_user('dtu'), VIEW, None)
        with self.assertRaises(ValueError):
            user_may(self.get_user('dtu'), VIEW, Person.objects.first())

    def test_other_actions_unchanged_for_anonymous(self):
        # VIEW is the only action that can be True for anonymous users.
        self.assertFalse(user_may(AnonymousUser(), EDIT, self.pubs[P]))
