"""Duplicate markers of person links and "Confirm person" (plan release-2026-7 T7, roadmap FA-R66).

- Permission ``merge_person`` (migration 0005): artek_editor has it, dtu_user and artek_staff
  don't; superusers have it implicitly. The migration reverses cleanly.
- Report page: a red (!) (exact_match) or (?) (relaxed_match, or multiple_match alone) after
  marked authors and supervisors, with a legend, for holders only. For everyone else the
  author and supervisor HTML is the same as before T7 (apart from whitespace).
- API (report list/detail): ``match``/``multiple`` in the author dicts for holders only.
- Person page: for holders, a notice with the marked links and a "Confirm person" form.
- POST person/<pk>/confirm/ clears the flags of all three link models of that person only.
- The 403 page shows its message (access_denied.html filled a block base.html doesn't have).

Everything is made up factory data.
"""
import re

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.shortcuts import resolve_url
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from publications.models import Authorship, Editorship, Supervisorship
from publications.permissions import DENIED_MESSAGES, MERGE_PERSON, user_may
from publications.person_links import marked_links
from publications.roles import ARTEK_EDITOR, ARTEK_STAFF
from publications.test_factories import (
    api_path, make_person, make_report, make_user, page_path, report_type,
)

ROLES = ('anonymous', 'dtu_user', 'artek_editor', 'superuser')
HOLDERS = ('artek_editor', 'superuser')

EXACT_TITLE = 'Multiple {role} instances in database with this exact name!'
RELAXED_TITLE = ('This {role} instance is possibly similar to another instance in the database '
                 '(relaxed match of initial and lastname).')
SEVERAL = ' Several candidates.'


def normalize(html):
    return re.sub(r'\s+', ' ', html).strip()


class PersonMarkerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        cls.ann = make_person('Ann', 'Alpha')        # author, exact
        cls.bob = make_person('Bob', 'Beta')         # author, relaxed
        cls.cal = make_person('Cal', 'Clean')        # author, no flags
        cls.sam = make_person('Sam', 'Super')        # supervisor, relaxed + multiple
        cls.max = make_person('Max', 'Multi')        # supervisor, multiple only
        cls.eve = make_person('Eve', 'Editor')       # editor, exact
        cls.oth = make_person('Oth', 'Other')        # another person with flags
        cls.pub = make_report(pubtype, '05-01', verified=True, confidential=False,
                              title='Marked report', authors=[cls.ann, cls.bob, cls.cal],
                              supervisors=[cls.sam, cls.max], editors=[cls.eve])
        cls.conf = make_report(pubtype, '06-01', verified=True, confidential=True,
                               title='Hidden report', authors=[cls.ann, cls.oth],
                               supervisors=[cls.ann], editors=[cls.ann])
        cls.set_flags(Authorship, cls.pub, cls.ann, exact_match=True)
        cls.set_flags(Authorship, cls.pub, cls.bob, relaxed_match=True)
        cls.set_flags(Supervisorship, cls.pub, cls.sam, relaxed_match=True, multiple_match=True)
        cls.set_flags(Supervisorship, cls.pub, cls.max, multiple_match=True)
        cls.set_flags(Editorship, cls.pub, cls.eve, exact_match=True)
        # Ann marked in all three roles on the confidential report.
        cls.set_flags(Authorship, cls.conf, cls.ann, relaxed_match=True, match_string='A. Alpha')
        cls.set_flags(Supervisorship, cls.conf, cls.ann, exact_match=True)
        cls.set_flags(Editorship, cls.conf, cls.ann, multiple_match=True, relaxed_match=True)
        cls.set_flags(Authorship, cls.conf, cls.oth, exact_match=True, multiple_match=True)
        cls.users = {
            'anonymous': None,
            'dtu_user': make_user('s990010'),
            'artek_editor': make_user('edit990', ARTEK_EDITOR),
            'superuser': make_user('super990', superuser=True),
        }

    @staticmethod
    def set_flags(model, publication, person, **flags):
        model.objects.filter(publication=publication, person=person).update(**flags)

    def login(self, role):
        user = self.users[role] if isinstance(role, str) else role
        if user is None:
            self.client.logout()
        else:
            self.client.force_login(user)

    def get(self, role, path):
        self.login(role)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response

    def person_url(self, person):
        return f'{settings.URL_PREFIX}/publications/person/{person.pk}/'

    def name_link(self, person):
        return f'<a href="{self.person_url(person)}">{person.first} {person.last}</a>'

    def marker(self, person, sign, title):
        cls = 'person-marker-exact' if sign == '!' else 'person-marker-relaxed'
        return (f' (<a class="person-marker {cls}" href="{self.person_url(person)}merge/" '
                f'title="{title}" style="color:red; font-weight:bold;">{sign}</a>)')


class MergePersonPermissionTests(TestCase):

    def codenames(self, group_name):
        return set(Group.objects.get(name=group_name).permissions
                   .filter(content_type__app_label='publications')
                   .values_list('codename', flat=True))

    def test_only_artek_editor_has_merge_person(self):
        self.assertIn('merge_person', self.codenames(ARTEK_EDITOR))
        self.assertNotIn('merge_person', self.codenames('dtu_user'))
        self.assertNotIn('merge_person', self.codenames(ARTEK_STAFF))

    def test_user_may(self):
        self.assertFalse(user_may(AnonymousUser(), MERGE_PERSON))
        self.assertFalse(user_may(make_user('s990010'), MERGE_PERSON))
        self.assertFalse(user_may(make_user('staff990', ARTEK_STAFF), MERGE_PERSON))
        self.assertTrue(user_may(make_user('edit990', ARTEK_EDITOR), MERGE_PERSON))
        self.assertTrue(user_may(make_user('super990', superuser=True), MERGE_PERSON))

    def test_migration_reverses_and_reapplies(self):
        # Only 0005 itself, with an explicit plan: migrating to 0004 would also reverse the
        # later schema migrations (0006+), and MariaDB can't run DDL inside the test's
        # transaction (plan "features" T4).
        key = ('publications', '0005_person_merge_person_permission')
        executor = MigrationExecutor(connection)
        executor.migrate([('publications', '0004_publication_confidential')],
                         plan=[(executor.loader.graph.nodes[key], True)])
        self.assertFalse(Permission.objects.filter(
            content_type__app_label='publications', codename='merge_person').exists())
        self.assertNotIn('merge_person', self.codenames(ARTEK_EDITOR))
        # The rest of the group is untouched.
        self.assertIn('change_publication', self.codenames(ARTEK_EDITOR))

        executor = MigrationExecutor(connection)
        executor.migrate([key], plan=[(executor.loader.graph.nodes[key], False)])
        self.assertIn('merge_person', self.codenames(ARTEK_EDITOR))
        self.assertNotIn('merge_person', self.codenames('dtu_user'))


class ReportPageMarkerTests(PersonMarkerTestCase):

    def property_value(self, response, label):
        match = re.search(
            rf'<strong>{label}:</strong></div>\s*<div class="property-value">(.*?)</div>',
            response.content.decode(), re.DOTALL)
        self.assertIsNotNone(match, f'no {label} row')
        return normalize(match.group(1))

    def path(self):
        return page_path('report', pk=self.pub.pk)

    def test_without_merge_person_html_is_unchanged(self):
        """The names, links and separators of the template before T7."""
        authors = (f'{self.name_link(self.ann)}, {self.name_link(self.bob)} &amp; '
                   f'{self.name_link(self.cal)}')
        supervisors = f'{self.name_link(self.sam)} &amp; {self.name_link(self.max)}'
        for role in ('anonymous', 'dtu_user'):
            with self.subTest(role=role):
                response = self.get(role, self.path())
                self.assertEqual(self.property_value(response, 'Authors'), authors)
                self.assertEqual(self.property_value(response, 'Supervisors'), supervisors)
                self.assertNotContains(response, 'person-marker')
                self.assertNotContains(response, 'Several candidates')

    def test_holders_see_markers(self):
        authors = (f'{self.name_link(self.ann)}'
                   f'{self.marker(self.ann, "!", EXACT_TITLE.format(role="author"))}, '
                   f'{self.name_link(self.bob)}'
                   f'{self.marker(self.bob, "?", RELAXED_TITLE.format(role="author"))} &amp; '
                   f'{self.name_link(self.cal)}')
        supervisors = (
            f'{self.name_link(self.sam)}'
            f'{self.marker(self.sam, "?", RELAXED_TITLE.format(role="supervisor") + SEVERAL)}'
            f' &amp; {self.name_link(self.max)}'
            f'{self.marker(self.max, "?", RELAXED_TITLE.format(role="supervisor") + SEVERAL)}')
        for role in HOLDERS:
            with self.subTest(role=role):
                response = self.get(role, self.path())
                self.assertEqual(self.property_value(response, 'Authors'), authors)
                self.assertEqual(self.property_value(response, 'Supervisors'), supervisors)
                self.assertContains(response, 'person-marker-legend')

    def test_no_legend_without_markers(self):
        Authorship.objects.update(exact_match=False, relaxed_match=False, multiple_match=False)
        Supervisorship.objects.update(exact_match=False, relaxed_match=False,
                                      multiple_match=False)
        response = self.get('artek_editor', self.path())
        self.assertNotContains(response, 'person-marker')

    def test_single_author_and_supervisor(self):
        report = make_report(report_type(), '07-01', verified=True, confidential=False,
                             authors=[self.cal], supervisors=[self.bob])
        response = self.get('anonymous', page_path('report', pk=report.pk))
        self.assertEqual(self.property_value(response, 'Authors'), self.name_link(self.cal))
        self.assertEqual(self.property_value(response, 'Supervisors'), self.name_link(self.bob))

    def test_queries_bounded(self):
        """The persons come with their link rows: the same number of queries for 1 and for
        6 marked authors."""
        pubtype = report_type()

        def count(n):
            persons = [make_person(f'P{n}{i}', 'Count') for i in range(n)]
            report = make_report(pubtype, f'08-0{n}', verified=True, confidential=False,
                                 authors=persons, supervisors=persons)
            report.authorship_set.update(exact_match=True)
            report.supervisorship_set.update(relaxed_match=True)
            self.login('artek_editor')
            with CaptureQueriesContext(connection) as captured:
                self.assertEqual(
                    self.client.get(page_path('report', pk=report.pk)).status_code, 200)
            return len(captured)

        self.assertEqual(count(1), count(6))


class ApiMarkerTests(PersonMarkerTestCase):

    def plain(self, person):
        return {'pk': person.pk, 'first': person.first, 'last': person.last}

    def authors(self, role, path):
        data = self.get(role, path).json()
        if isinstance(data, dict):
            return data['authors']
        return next(item for item in data if item['id'] == self.pub.pk)['authors']

    def test_authors_per_role(self):
        plain = [self.plain(self.ann), self.plain(self.bob), self.plain(self.cal)]
        marked = [{**plain[0], 'match': 'exact'}, {**plain[1], 'match': 'relaxed'}, plain[2]]
        for path in (api_path('report-list'), api_path('report-detail', pk=self.pub.pk)):
            for role in ROLES:
                with self.subTest(path=path, role=role):
                    authors = self.authors(role, path)
                    self.assertEqual(authors, marked if role in HOLDERS else plain)
                    # Same key order as before for the plain dicts.
                    self.assertEqual(list(authors[2]), ['pk', 'first', 'last'])

    def test_multiple(self):
        """multiple_match adds "multiple": true; alone it counts as a relaxed match."""
        conf_path = api_path('report-detail', pk=self.conf.pk)
        authors = self.get('artek_editor', conf_path).json()['authors']
        self.assertEqual(authors, [
            {**self.plain(self.ann), 'match': 'relaxed'},
            {**self.plain(self.oth), 'match': 'exact', 'multiple': True},
        ])
        Authorship.objects.filter(publication=self.conf, person=self.ann).update(
            relaxed_match=False, multiple_match=True)
        authors = self.get('superuser', conf_path).json()['authors']
        self.assertEqual(authors[0], {**self.plain(self.ann), 'match': 'relaxed',
                                      'multiple': True})


class PersonPageMarkerTests(PersonMarkerTestCase):

    def test_notice_only_for_holders(self):
        path = page_path('person', pk=self.ann.pk)
        for role in ROLES:
            with self.subTest(role=role):
                response = self.get(role, path)
                if role in HOLDERS:
                    self.assertContains(response, 'id="confirm-person"')
                    self.assertContains(
                        response, '4 links of this person are marked as possible duplicates')
                    self.assertContains(response, 'Confirm person')
                    self.assertContains(
                        response, f'action="{settings.URL_PREFIX}/publications/person/'
                                  f'{self.ann.pk}/confirm/"')
                    self.assertContains(response, 'csrfmiddlewaretoken')
                    for text in ('Author of', 'Supervisor of', 'Editor of', 'Hidden report',
                                 'Marked report'):
                        self.assertContains(response, text)
                else:
                    self.assertNotContains(response, 'confirm-person')
                    self.assertNotContains(response, 'possible duplicate')
                    self.assertNotContains(response, 'Hidden report')

    def test_marked_editor(self):
        response = self.get('artek_editor', page_path('person', pk=self.eve.pk))
        self.assertContains(response, '1 link of this person is marked as a possible duplicate')
        self.assertContains(response, 'Editor of')

    def test_no_notice_without_markers(self):
        response = self.get('artek_editor', page_path('person', pk=self.cal.pk))
        self.assertNotContains(response, 'confirm-person')

    def test_hidden_reports_are_counted_not_listed(self):
        """A holder of merge_person who isn't an editor doesn't see the confidential report."""
        user = make_user('s990020')
        user.user_permissions.add(Permission.objects.get(
            content_type__app_label='publications', codename='merge_person'))
        response = self.get(user, page_path('person', pk=self.ann.pk))
        self.assertContains(response, '4 links of this person are marked as possible duplicates')
        self.assertContains(response, 'Marked report')
        self.assertNotContains(response, 'Hidden report')
        self.assertContains(response, "3 more on reports you can't see")

    def test_marked_links(self):
        self.assertEqual([(role, link.publication_id) for role, link in marked_links(self.ann)],
                         [('author', self.pub.pk), ('author', self.conf.pk),
                          ('supervisor', self.conf.pk), ('editor', self.conf.pk)])


class ConfirmPersonTests(PersonMarkerTestCase):

    def path(self, person):
        return page_path('person_confirm', pk=person.pk)

    def flags(self, model, publication, person):
        return model.objects.filter(publication=publication, person=person).values(
            'exact_match', 'relaxed_match', 'multiple_match', 'match_string').get()

    def all_flags(self):
        return {(model.__name__, row['publication_id'], row['person_id']):
                (row['exact_match'], row['relaxed_match'], row['multiple_match'],
                 row['match_string'])
                for model in (Authorship, Supervisorship, Editorship)
                for row in model.objects.values()}

    def test_confirm_clears_all_links_of_the_person_only(self):
        before = self.all_flags()
        self.login('artek_editor')
        response = self.client.post(self.path(self.ann))
        # The Location holds the script prefix ('/find' with the production settings).
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('publications:person',
                                                       kwargs={'pk': self.ann.pk}))
        cleared = {'exact_match': False, 'relaxed_match': False, 'multiple_match': False,
                   'match_string': ''}
        for model, publication in ((Authorship, self.pub), (Authorship, self.conf),
                                   (Supervisorship, self.conf), (Editorship, self.conf)):
            with self.subTest(model=model.__name__, report=publication.number):
                self.assertEqual(self.flags(model, publication, self.ann), cleared)
        after = self.all_flags()
        for key, value in before.items():
            if key[2] != self.ann.pk:
                self.assertEqual(after[key], value, key)
        # Other persons are still marked.
        self.assertTrue(self.flags(Authorship, self.conf, self.oth)['exact_match'])
        self.assertTrue(self.flags(Editorship, self.pub, self.eve)['exact_match'])

        page = self.client.get(page_path('person', pk=self.ann.pk))
        self.assertContains(page, 'Person Ann Alpha confirmed')
        self.assertNotContains(page, 'confirm-person')
        report = self.client.get(page_path('report', pk=self.pub.pk))
        self.assertNotContains(report, f'person/{self.ann.pk}/merge/')
        self.assertContains(report, f'person/{self.bob.pk}/merge/')

    def test_superuser_may_confirm(self):
        self.login('superuser')
        response = self.client.post(self.path(self.eve))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.flags(Editorship, self.pub, self.eve)['exact_match'])

    def test_confirm_per_role(self):
        before = self.all_flags()
        self.login('anonymous')
        response = self.client.post(self.path(self.ann))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(resolve_url(settings.LOGIN_URL) + '?next='),
                        response['Location'])

        self.login('dtu_user')
        response = self.client.post(self.path(self.ann))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, DENIED_MESSAGES[MERGE_PERSON], status_code=403)

        self.login(make_user('staff990', ARTEK_STAFF))
        self.assertEqual(self.client.post(self.path(self.ann)).status_code, 403)
        self.assertEqual(self.all_flags(), before)

    def test_get_is_refused(self):
        before = self.all_flags()
        for role in ROLES:
            with self.subTest(role=role):
                self.login(role)
                self.assertEqual(self.client.get(self.path(self.ann)).status_code, 405)
        self.assertEqual(self.all_flags(), before)

    def test_unknown_person(self):
        self.login('artek_editor')
        response = self.client.post(page_path('person_confirm', pk=999999))
        self.assertEqual(response.status_code, 404)


class AccessDeniedPageTests(TestCase):
    """access_denied.html filled {% block body %}, which base.html doesn't have: the message
    was never shown (found in T6)."""

    def test_403_page_shows_its_message(self):
        self.client.force_login(make_user('s990010'))
        response = self.client.get(page_path('add_report'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'access-denied-message', status_code=403)
        self.assertContains(response, 'You do not have permissions to add reports!',
                            status_code=403)
        self.assertContains(response, 'Access denied!', status_code=403)
