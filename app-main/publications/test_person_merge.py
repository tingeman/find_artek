"""Merging duplicate persons (plan release-2026-7 T8, roadmap FA-R58 merge part).

- The service (publications.person_merge): plan_merge writes nothing; merge_persons moves the
  links of all three roles, drops duplicates (same report, same role), keeps the order of the
  persons on each report, fills only empty identity fields (conflicts keep the kept value and
  are reported), clears the kept person's markers, deletes the merged persons, logs one INFO
  line without names, rolls everything back when a step fails, refuses unhandled relations,
  stale confirmations, self-merges, empty lists and missing persons.
- The views (person/<pk>/merge/, .../merge/confirm/, .../merge/do/): merge_person only; the
  page lists the matcher's candidates; the confirmation lists the changes and writes nothing;
  do performs it; GET on the POST URLs is 405; reports the viewer may not see are counted, not
  listed. The report and person pages render after a merge.

Everything is made up factory data.
"""
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import transaction
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from publications import person_merge
from publications.models import Authorship, Editorship, Person, Supervisorship
from publications.person_merge import (
    HANDLED_RELATIONS, MergeError, StaleMergeError, merge_persons, person_relations,
    plan_merge,
)
from publications.roles import ARTEK_EDITOR, ARTEK_STAFF
from publications.test_factories import (
    make_person, make_report, make_user, page_path, report_type,
)

LINKS = (Authorship, Supervisorship, Editorship)


def snapshot():
    """Every person and link row, to compare before and after."""
    persons = {p['id']: p for p in Person.objects.values()}
    links = {model.__name__: sorted(model.objects.values_list(
        'pk', 'publication_id', 'person_id', 'exact_match', 'relaxed_match', 'multiple_match'))
        for model in LINKS}
    return persons, links


class MergeFixture(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        cls.kept = make_person('Ann', 'Alpha', id_number='s990001', initials='')
        cls.dup = make_person('Ann', 'Alpha', id_number='s990002', email='ann@example.org',
                              position='student', initials='AAL')
        cls.dup2 = make_person('Anders', 'Alpha', department='Arctic', initials='ANA')
        cls.x = make_person('Xia', 'Xenon')
        cls.y = make_person('Yan', 'Yellow')
        cls.zed = make_person('Zed', 'Zulu')
        # dup is author no. 2 of 3 on r1.
        cls.r1 = make_report(pubtype, '90-01', verified=True, confidential=False,
                             title='Order report', authors=[cls.x, cls.dup, cls.y])
        # kept and dup both authors of r2: dup's link is a duplicate.
        cls.r2 = make_report(pubtype, '90-02', verified=True, confidential=False,
                             title='Shared report', authors=[cls.kept, cls.dup],
                             supervisors=[cls.kept])
        # dup supervisor and editor of r3; supervisor of r2 too (duplicate of kept's).
        cls.r3 = make_report(pubtype, '90-03', verified=True, confidential=False,
                             title='Roles report', supervisors=[cls.dup], editors=[cls.dup])
        Supervisorship.objects.create(publication=cls.r2, person=cls.dup, supervisor_id=1)
        # dup2 on a confidential report and on r1.
        cls.conf = make_report(pubtype, '90-04', verified=True, confidential=True,
                               title='Secret report', authors=[cls.dup2])
        Editorship.objects.create(publication=cls.r1, person=cls.dup2, editor_id=0)
        # kept's own link is marked.
        Authorship.objects.filter(publication=cls.r2, person=cls.kept).update(
            exact_match=True, multiple_match=True, match_string='Ann Alpha')
        cls.editor = make_user('edit991', ARTEK_EDITOR)

    def refresh(self, person):
        return Person.objects.get(pk=person.pk)


class MergeServiceTests(MergeFixture):

    def test_plan_describes_the_merge_and_writes_nothing(self):
        before = snapshot()
        plan = plan_merge(self.kept, [self.dup])
        self.assertEqual(snapshot(), before)
        self.assertEqual(plan.blockers, [])
        item, = plan.merged
        self.assertEqual(item.person, self.dup)
        pubs = {role: [link.publication_id for link in links] for role, links in item.moved.items()}
        self.assertEqual(pubs, {'author': [self.r1.pk], 'supervisor': [self.r3.pk],
                                'editor': [self.r3.pk]})
        dropped = {role: [link.publication_id for link in links]
                   for role, links in item.dropped.items()}
        self.assertEqual(dropped, {'author': [self.r2.pk], 'supervisor': [self.r2.pk],
                                   'editor': []})
        self.assertEqual(item.filled, {'initials': 'AAL', 'email': 'ann@example.org',
                                       'position': 'student'})
        self.assertEqual(item.conflicts, [('id_number', 's990001', 's990002')])
        self.assertEqual(plan.moved_counts(), {'author': 1, 'supervisor': 1, 'editor': 1})
        self.assertEqual(plan.dropped_counts(), {'author': 1, 'supervisor': 1, 'editor': 0})
        self.assertEqual(len(plan.fingerprint), 64)
        self.assertEqual(plan_merge(self.kept, [self.dup]).fingerprint, plan.fingerprint)

    def test_merge_moves_links_of_all_roles_and_drops_duplicates(self):
        merge_persons(self.kept, [self.dup], self.editor)
        self.assertFalse(Person.objects.filter(pk=self.dup.pk).exists())
        for model in LINKS:
            self.assertFalse(model.objects.filter(person_id=self.dup.pk).exists())
        self.assertEqual(
            sorted(Authorship.objects.filter(person=self.kept)
                   .values_list('publication_id', flat=True)), [self.r1.pk, self.r2.pk])
        self.assertEqual(
            sorted(Supervisorship.objects.filter(person=self.kept)
                   .values_list('publication_id', flat=True)), [self.r2.pk, self.r3.pk])
        self.assertEqual(
            list(Editorship.objects.filter(person=self.kept)
                 .values_list('publication_id', flat=True)), [self.r3.pk])
        # No report lists the kept person twice in a role.
        for model in LINKS:
            pubs = list(model.objects.filter(person=self.kept)
                        .values_list('publication_id', flat=True))
            self.assertEqual(len(pubs), len(set(pubs)), model.__name__)
        # Others untouched.
        self.assertTrue(Person.objects.filter(pk=self.dup2.pk).exists())
        self.assertEqual(Editorship.objects.get(publication=self.r1).person_id, self.dup2.pk)

    def test_author_order_on_each_report_is_kept(self):
        link = Authorship.objects.get(publication=self.r1, person=self.dup)
        merge_persons(self.kept, [self.dup], self.editor)
        self.assertEqual(list(self.r1.sorted_authors()), [self.x, self.kept, self.y])
        moved = Authorship.objects.get(publication=self.r1, person=self.kept)
        self.assertEqual((moved.pk, moved.author_id), (link.pk, link.author_id))
        self.assertEqual(list(self.r2.sorted_authors()), [self.kept])

    def test_fields_filled_only_when_empty_and_conflicts_keep_the_kept_value(self):
        merge_persons(self.kept, [self.dup], self.editor)
        kept = self.refresh(self.kept)
        self.assertEqual(kept.id_number, 's990001')        # conflict: kept value stays
        self.assertEqual(kept.email, 'ann@example.org')    # empty: filled
        self.assertEqual(kept.position, 'student')
        self.assertEqual(kept.initials, 'AAL')
        self.assertEqual((kept.first, kept.last), ('Ann', 'Alpha'))
        self.assertEqual(kept.modified_by, self.editor)

    def test_two_merged_persons_fill_in_order_and_conflict_with_each_other(self):
        plan = plan_merge(self.kept, [self.dup2, self.dup])     # merged in pk order
        self.assertEqual([m.person for m in plan.merged], [self.dup, self.dup2])
        self.assertEqual(plan.merged[1].filled, {'department': 'Arctic'})
        self.assertIn(('initials', 'AAL', 'ANA'), plan.merged[1].conflicts)
        merge_persons(self.kept, [self.dup, self.dup2], self.editor)
        kept = self.refresh(self.kept)
        self.assertEqual((kept.initials, kept.department), ('AAL', 'Arctic'))
        self.assertEqual(Person.objects.filter(pk__in=[self.dup.pk, self.dup2.pk]).count(), 0)
        self.assertEqual(Authorship.objects.get(publication=self.conf).person, self.kept)
        self.assertEqual(Editorship.objects.get(publication=self.r1).person, self.kept)

    def test_a_report_shared_by_two_merged_persons_keeps_one_link(self):
        Editorship.objects.create(publication=self.r1, person=self.dup, editor_id=1)
        plan = merge_persons(self.kept, [self.dup, self.dup2], self.editor)
        self.assertEqual(plan.dropped_counts()['editor'], 1)
        links = Editorship.objects.filter(publication=self.r1)
        self.assertEqual([link.person for link in links], [self.kept])

    def test_flags_cleared_on_the_kept_person(self):
        Supervisorship.objects.filter(person=self.dup, publication=self.r3).update(
            relaxed_match=True)
        merge_persons(self.kept, [self.dup], self.editor)
        for model in LINKS:
            for link in model.objects.filter(person=self.kept):
                self.assertEqual(
                    (link.exact_match, link.relaxed_match, link.multiple_match,
                     link.match_string), (False, False, False, ''), model.__name__)

    def test_everything_rolled_back_when_a_step_fails(self):
        before = snapshot()
        with mock.patch.object(person_merge, 'clear_markers', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                merge_persons(self.kept, [self.dup, self.dup2], self.editor)
        self.assertEqual(snapshot(), before)

    def test_relations_to_person_are_the_three_link_models(self):
        """Pins what was found: a new relation to Person fails here until the merge handles
        it (or knowingly refuses it)."""
        found = {(model, name) for model, name, _ in person_relations()}
        self.assertEqual(found, HANDLED_RELATIONS)
        self.assertEqual(person_merge.unhandled_relations(), [])

    def test_unhandled_relation_with_rows_blocks_the_merge(self):
        fake = [(Authorship, 'person', 'fake_relation')]
        before = snapshot()
        with mock.patch.object(person_merge, 'unhandled_relations', return_value=fake):
            plan = plan_merge(self.kept, [self.dup])
            self.assertEqual(len(plan.blockers), 1)
            self.assertIn('fake_relation', plan.blockers[0])
            with self.assertRaisesMessage(MergeError, "can't be done"):
                merge_persons(self.kept, [self.dup], self.editor)
            # No rows for zed: no blocker.
            self.assertEqual(plan_merge(self.kept, [self.zed]).blockers, [])
        self.assertEqual(snapshot(), before)

    def test_stale_fingerprint_refused(self):
        plan = plan_merge(self.kept, [self.dup])
        changes = (
            lambda: Editorship.objects.create(publication=self.r2, person=self.dup, editor_id=5),
            lambda: Person.objects.filter(pk=self.dup.pk).update(email='other@example.org'),
            lambda: Authorship.objects.filter(publication=self.r2, person=self.kept).delete(),
        )
        for change in changes:
            with self.subTest(change=change), transaction.atomic():
                change()
                before = snapshot()
                with self.assertRaises(StaleMergeError):
                    merge_persons(self.kept, [self.dup], self.editor,
                                  expected_plan=plan.fingerprint)
                self.assertEqual(snapshot(), before)
                transaction.set_rollback(True)   # undo the change for the next case
        # Unchanged data: the same fingerprint (or the plan itself) is accepted.
        merge_persons(self.kept, [self.dup], self.editor, expected_plan=plan)
        self.assertFalse(Person.objects.filter(pk=self.dup.pk).exists())

    def test_self_empty_and_missing_refused(self):
        before = snapshot()
        cases = (
            ([self.kept], "into itself"),
            ([self.dup, self.kept], "into itself"),
            ([], "No persons"),
            ([Person(pk=999999)], "no longer exist"),
        )
        for merged, message in cases:
            with self.subTest(message=message, merged=merged):
                with self.assertRaisesMessage(MergeError, message):
                    plan_merge(self.kept, merged)
                with self.assertRaisesMessage(MergeError, message):
                    merge_persons(self.kept, merged, self.editor)
        with self.assertRaisesMessage(MergeError, "no longer exists"):
            merge_persons(Person(pk=999998), [self.dup], self.editor)
        self.assertEqual(snapshot(), before)

    def test_log_line_has_pks_and_counts_and_no_names_or_values(self):
        with self.assertLogs('publications.persons', 'INFO') as logs:
            merge_persons(self.kept, [self.dup], self.editor)
        self.assertEqual(len(logs.records), 1)
        record = logs.records[0]
        self.assertEqual(record.levelname, 'INFO')
        line = record.getMessage()
        self.assertIn(f'user={self.editor.pk}', line)
        self.assertIn(f'kept={self.kept.pk}', line)
        self.assertIn(f'deleted=[{self.dup.pk}]', line)
        self.assertIn('moved=author:1,supervisor:1,editor:1', line)
        self.assertIn('dropped=author:1,supervisor:1,editor:0', line)
        self.assertIn('filled=initials,email,position', line)
        for secret in ('Ann', 'Alpha', 'ann@example.org', 's99000', 'student', 'AAL'):
            self.assertNotIn(secret, line)


class MergeViewTests(MergeFixture):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.users = {
            'anonymous': None,
            'dtu_user': make_user('s990011'),
            'artek_staff': make_user('staff991', ARTEK_STAFF),
            'artek_editor': cls.editor,
            'superuser': make_user('super991', superuser=True),
        }
        # merge_person without seeing everything (not in artek_editor).
        cls.holder = make_user('s990012')
        cls.holder.user_permissions.add(Permission.objects.get(codename='merge_person'))

    def login(self, role):
        user = self.users[role] if isinstance(role, str) else role
        if user is None:
            self.client.logout()
        else:
            self.client.force_login(user)

    def assertBackToMergePage(self, response, message):
        """A redirect to the kept person's merge page (the Location holds the script prefix,
        '/find' with the production settings), which then shows ``message``."""
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'],
                         reverse('publications:person_merge', kwargs={'pk': self.kept.pk}))
        self.assertContains(self.client.get(self.paths()['person_merge']), message)

    def paths(self, person=None):
        pk = (person or self.kept).pk
        return {name: page_path(name, pk=pk)
                for name in ('person_merge', 'person_merge_confirm', 'person_merge_do')}

    def test_permission_per_role(self):
        expected = {'anonymous': 'login', 'dtu_user': 403, 'artek_staff': 403,
                    'artek_editor': 'ok', 'superuser': 'ok'}
        for role, answer in expected.items():
            self.login(role)
            for name, path in self.paths().items():
                method = self.client.get if name == 'person_merge' else self.client.post
                with self.subTest(role=role, url=name):
                    before = snapshot()
                    response = method(path, {'merge': [self.dup.pk]})
                    if answer == 'login':
                        self.assertEqual(response.status_code, 302)
                        self.assertTrue(response['Location'].startswith(
                            resolve_url(settings.LOGIN_URL) + '?next='), response['Location'])
                    elif answer == 403:
                        self.assertEqual(response.status_code, 403)
                        self.assertContains(response, 'Only ARTEK editors', status_code=403)
                    else:
                        # do without a fingerprint: back to the merge page.
                        self.assertIn(response.status_code, (200, 302))
                    self.assertEqual(snapshot(), before)

    def test_get_on_post_urls_is_405(self):
        for role in ('anonymous', 'artek_editor'):
            self.login(role)
            for name in ('person_merge_confirm', 'person_merge_do'):
                with self.subTest(role=role, url=name):
                    response = self.client.get(self.paths()[name])
                    self.assertEqual(response.status_code, 405)
        self.assertTrue(Person.objects.filter(pk=self.dup.pk).exists())

    def test_page_lists_the_candidates(self):
        self.login('artek_editor')
        response = self.client.get(self.paths()['person_merge'])
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(f'name="merge" value="{self.dup.pk}"', content)
        self.assertIn(f'name="merge" value="{self.dup2.pk}"', content)
        self.assertNotIn(f'name="merge" value="{self.kept.pk}"', content)
        self.assertNotIn(f'name="merge" value="{self.zed.pk}"', content)
        self.assertNotIn(f'name="merge" value="{self.x.pk}"', content)
        # Candidates with reports, roles and identifiers; the autocomplete field.
        self.assertIn('90-01 Order report', content)
        self.assertIn('Supervisor (2)', content)
        self.assertIn('s990002', content)
        self.assertIn('data-ajax--url', content)
        self.assertIn(reverse('publications:person-autocomplete'), content)
        self.assertIn(reverse('publications:person_merge_confirm', kwargs={'pk': self.kept.pk}),
                      content)

    def test_hidden_reports_are_counted_not_listed(self):
        self.login(self.holder)
        response = self.client.get(self.paths()['person_merge'])
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Secret report')
        self.assertNotContains(response, '90-04')
        self.assertContains(response, "1 report you can't see")
        response = self.client.post(self.paths()['person_merge_confirm'],
                                    {'merge': [self.dup2.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Secret report')
        self.assertContains(response, "1 report you can't see")
        # The editor sees everything.
        self.login('artek_editor')
        self.assertContains(self.client.get(self.paths()['person_merge']), '90-04 Secret report')

    def test_confirmation_lists_the_changes_and_writes_nothing(self):
        self.login('artek_editor')
        before = snapshot()
        response = self.client.post(self.paths()['person_merge_confirm'],
                                    {'merge': [str(self.dup.pk)], 'others': [str(self.dup2.pk)]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(snapshot(), before)
        self.assertEqual(Person.objects.count(), len(before[0]))
        content = response.content.decode()
        self.assertIn('Moved as author', content)
        self.assertIn('90-01 Order report', content)
        self.assertIn('Dropped (the kept person is already author there)', content)
        self.assertIn('90-02 Shared report', content)
        self.assertIn('Fills the empty field email of the kept person with "ann@example.org"',
                      content)
        self.assertIn('Conflict in id_number: the kept "s990001" stays, '
                      '"s990002" is dropped', content)
        self.assertIn(f'data-person="{self.dup.pk}"', content)
        self.assertIn(f'data-person="{self.dup2.pk}"', content)
        plan = plan_merge(self.kept, [self.dup, self.dup2])
        self.assertIn(f'name="fingerprint" value="{plan.fingerprint}"', content)
        self.assertIn(f'name="merge" value="{self.dup.pk}"', content)

    def test_confirmation_shows_blockers_without_merge_button(self):
        self.login('artek_editor')
        fake = [(Authorship, 'person', 'fake_relation')]
        with mock.patch.object(person_merge, 'unhandled_relations', return_value=fake):
            response = self.client.post(self.paths()['person_merge_confirm'],
                                        {'merge': [self.dup.pk]})
        self.assertContains(response, 'person-merge-blockers')
        self.assertNotContains(response, 'name="fingerprint"')

    def test_bad_choices_go_back_with_a_message(self):
        self.login('artek_editor')
        cases = (({}, 'No persons'), ({'merge': [self.kept.pk]}, 'into itself'),
                 ({'merge': ['abc']}, 'could not be read'),
                 ({'merge': [999999]}, 'no longer exist'))
        for data, message in cases:
            with self.subTest(data=data):
                before = snapshot()
                response = self.client.post(self.paths()['person_merge_confirm'], data)
                self.assertBackToMergePage(response, message)
                self.assertEqual(snapshot(), before)

    def test_do_merge_performs_it(self):
        self.login('artek_editor')
        plan = plan_merge(self.kept, [self.dup])
        with self.assertLogs('publications.persons', 'INFO'):
            response = self.client.post(self.paths()['person_merge_do'],
                                        {'merge': [self.dup.pk], 'fingerprint': plan.fingerprint})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'],
                         reverse('publications:person', kwargs={'pk': self.kept.pk}))
        self.assertFalse(Person.objects.filter(pk=self.dup.pk).exists())
        self.assertEqual(Authorship.objects.get(publication=self.r1, author_id=1).person,
                         self.kept)
        page = self.client.get(page_path('person', pk=self.kept.pk))
        self.assertContains(page, 'Merged 1 person(s) into Ann Alpha')
        self.assertContains(page, '3 link(s) moved, 2 duplicate link(s) dropped')
        # Smoke: the pages render after the merge.
        for pub in (self.r1, self.r2, self.r3):
            self.assertEqual(self.client.get(page_path('report', pk=pub.pk)).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(page_path('person', pk=self.kept.pk)).status_code, 200)
        self.assertEqual(self.client.get(page_path('report', pk=self.r1.pk)).status_code, 200)
        self.assertEqual(self.client.get(page_path('person', pk=self.dup.pk)).status_code, 404)

    def test_do_merge_with_stale_or_missing_fingerprint_changes_nothing(self):
        self.login('artek_editor')
        plan = plan_merge(self.kept, [self.dup])
        Editorship.objects.create(publication=self.r2, person=self.dup, editor_id=3)
        for data, message in (
                ({'merge': [self.dup.pk], 'fingerprint': plan.fingerprint}, 'changed after'),
                ({'merge': [self.dup.pk]}, 'not confirmed')):
            with self.subTest(message=message):
                before = snapshot()
                response = self.client.post(self.paths()['person_merge_do'], data)
                self.assertBackToMergePage(response, message)
                self.assertEqual(snapshot(), before)

    def test_person_page_links_to_the_merge_page_for_holders(self):
        merge_url = reverse('publications:person_merge', kwargs={'pk': self.zed.pk})
        for role, shown in (('anonymous', False), ('dtu_user', False), ('artek_staff', False),
                            ('artek_editor', True), ('superuser', True)):
            self.login(role)
            with self.subTest(role=role):
                # zed has no markers: the link is still there for holders.
                response = self.client.get(page_path('person', pk=self.zed.pk))
                if shown:
                    self.assertContains(response, merge_url)
                    self.assertContains(response, 'Merge duplicates')
                else:
                    self.assertNotContains(response, merge_url)
                    self.assertNotContains(response, 'Merge duplicates')
        # A marked person: the notice has the confirm button and the merge link.
        self.login('artek_editor')
        response = self.client.get(page_path('person', pk=self.kept.pk))
        self.assertContains(response, 'id="confirm-person"')
        self.assertContains(response, 'Confirm person')
        self.assertContains(response,
                            reverse('publications:person_merge', kwargs={'pk': self.kept.pk}))

    def test_report_marker_links_to_the_merge_page(self):
        self.login('artek_editor')
        response = self.client.get(page_path('report', pk=self.r2.pk))
        self.assertContains(
            response, f'href="{reverse("publications:person_merge", kwargs={"pk": self.kept.pk})}"')
