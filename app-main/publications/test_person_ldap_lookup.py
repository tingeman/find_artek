"""DTU directory (AD/LDAP) lookup in the person disambiguation step (plan release-2026-7 T12).

A typed study number ('s' + 6 digits) or initials (2-6 letters) is also looked up in the DTU
directory when USE_LDAP is on. A hit that is not in the database is offered as an extra choice
("Given Surname (initials) [DTU directory]"); choosing it stores an 'LDAP:' marker, and the
person is fetched from the directory again and created (or an existing one with the same
identifiers reused) when the report is saved, without match flags. A hit already in the
database is shown as that person. USE_LDAP off, a failing directory or no hit: the step works
as before. A full name never asks the directory.

No network: workflows.person asks utils_person.find_ldap_person, which is mocked in every test
(ldap3 itself would fail the test). Entries are made-up test_factories.ldap_entry objects.
"""
from types import SimpleNamespace
from unittest import mock

from django.contrib.messages import get_messages
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from ldap3.core.exceptions import LDAPSocketOpenError

from publications.models import Person, Publication
from publications.test_factories import app_path, ldap_entry, make_person, page_path
from publications.test_report_form_persons import NEW, ReportFormPersonTestBase
from publications.views import get_report_form_data
from publications.workflows.person import directory_query, person_review_label

DIRECTORY = 'directory'  # choice in walk: the (first) DTU directory choice
STEP_URL = reverse('publications:disambiguate_person_step')
FLAGS = ('exact_match', 'relaxed_match', 'multiple_match')


def employee():
    entry = ldap_entry('Zqskaa', 'Asger', title='Lektor', employee_id='99001',
                       department='Sustain', initials='zqska')
    entry.mail = SimpleNamespace(value='zqska@example.org')  # never shown or stored
    return entry


def student():
    return ldap_entry('Zqstud', 'Mia Lund', company='Studerende', name='s990123')


def _no_ldap3(*args, **kwargs):
    raise AssertionError('ldap3 must not be used in these tests')


class DirectoryQueryTests(SimpleTestCase):

    def test_study_numbers_and_initials_are_looked_up(self):
        self.assertEqual(directory_query('s990123'), {'name': 's990123'})
        self.assertEqual(directory_query('S990123'), {'name': 'S990123'})
        self.assertEqual(directory_query(' zqska '), {'initials': 'zqska'})
        self.assertEqual(directory_query('AB'), {'initials': 'AB'})
        self.assertEqual(directory_query('zqska [id:0]'), {'initials': 'zqska'})

    def test_other_text_is_not_looked_up(self):
        for text in ('Jane Newcomer', 'a', 'abcdefg', 'ab1', 's12345', 's1234567', 'zq*',
                     'zq)(x', 'Ål', '', '[id:12]'):
            with self.subTest(text=text):
                self.assertIsNone(directory_query(text))

    def test_review_label(self):
        self.assertEqual(person_review_label('LDAP:zqska:Asger Zqskaa'),
                         'Asger Zqskaa (zqska, from the DTU directory)')
        self.assertEqual(person_review_label('CREATE:Jane Newcomer'), 'Jane Newcomer (new person)')
        self.assertIsNone(person_review_label('12'))


@override_settings(USE_LDAP=True)
class DirectoryLookupTestBase(ReportFormPersonTestBase):

    def setUp(self):
        super().setUp()
        self.entries = {('initials', 'zqska'): [employee()], ('name', 's990123'): [student()]}
        self.find = self.patch('publications.utils_person.find_ldap_person',
                               side_effect=self.fake_directory)
        self.patch('publications.utils_person.ldap3.Server', side_effect=_no_ldap3)
        self.patch('publications.utils_person.ldap3.Connection', side_effect=_no_ldap3)

    def patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def fake_directory(self, **query):
        ((attribute, value),) = query.items()
        return list(self.entries.get((attribute, value.lower()), []))

    def messages_of(self, response):
        return [m.message for m in get_messages(response.wsgi_request)]

    def start(self, path=None, **fields):
        """Post the add form (or ``path``) with ``fields``; the response (a redirect)."""
        return self.client.post(path or page_path('add_report'), self.form_data(**fields))

    def step_page(self):
        page = self.client.get(app_path(STEP_URL))
        self.assertEqual(page.status_code, 200)
        return page

    def walk(self, response, choices):
        """walk_workflow with one more choice: DIRECTORY picks the directory hit offered."""
        complete_url = reverse('publications:complete_person_workflow')
        for _ in range(20):
            self.assertEqual(response.status_code, 302)
            location = response['Location']
            if location == STEP_URL:
                page = self.step_page()
                choice = choices[page.context['clean_name']]
                if choice == DIRECTORY:
                    hits = page.context['directory_choices']
                    self.assertEqual(len(hits), 1, 'one directory choice expected')
                    response = self.client.post(app_path(STEP_URL), {
                        'action': 'select_directory', 'directory_id': hits[0]['identifier']})
                elif choice == NEW:
                    response = self.client.post(app_path(STEP_URL), {'action': 'create_new'})
                else:
                    response = self.client.post(app_path(STEP_URL), {
                        'action': 'select_existing', 'person_id': str(choice.pk)})
            elif location == complete_url:
                response = self.client.get(app_path(location))
            else:
                return response
        self.fail('the person workflow did not end')

    def flags(self, link):
        return {f: getattr(link, f) for f in FLAGS}

    def no_flags(self):
        return dict.fromkeys(FLAGS, False)


class StepPageTests(DirectoryLookupTestBase):

    def test_initials_offer_the_directory_person(self):
        self.start(authors=['zqska'])
        page = self.step_page()
        self.find.assert_called_with(initials='zqska')
        hits = page.context['directory_choices']
        self.assertEqual([(h['identifier'], h['name']) for h in hits], [('zqska', 'Asger Zqskaa')])
        self.assertContains(page, 'Asger Zqskaa (zqska) [DTU directory]')
        self.assertContains(page, 'Lektor | Sustain')
        self.assertContains(page, 'value="select_directory"')
        self.assertContains(page, 'value="create_new"')
        self.assertNotContains(page, 'zqska@example.org')
        self.assertNotContains(page, 'No matching persons found')

    def test_study_number_offers_the_directory_person_any_case(self):
        self.start(authors=['S990123'])
        page = self.step_page()
        self.find.assert_called_with(name='S990123')
        self.assertContains(page, 'Mia Lund Zqstud (s990123) [DTU directory]')
        self.assertContains(page, 'student')

    def test_full_name_does_not_ask_the_directory(self):
        self.start(authors=['Jane Newcomer'])
        page = self.step_page()
        self.find.assert_not_called()
        self.assertEqual(page.context['directory_choices'], [])
        self.assertNotContains(page, 'DTU directory')

    def test_no_hit_shows_the_step_as_before(self):
        self.start(authors=['zqnone'])
        page = self.step_page()
        self.find.assert_called_with(initials='zqnone')
        self.assertEqual(page.context['directory_choices'], [])
        self.assertContains(page, 'No matching persons found')

    @override_settings(USE_LDAP=False)
    def test_use_ldap_off_does_not_ask_the_directory(self):
        self.start(authors=['zqska'])
        page = self.step_page()
        self.find.assert_not_called()
        self.assertEqual(page.context['directory_choices'], [])
        self.assertContains(page, 'value="create_new"')

    def test_failing_directory_logs_one_warning_and_shows_the_step(self):
        self.start(authors=['zqska'])
        self.find.side_effect = LDAPSocketOpenError('socket closed for zqska')
        with self.assertLogs('publications.workflows.person', level='WARNING') as logs:
            page = self.step_page()
        self.assertEqual(page.context['directory_choices'], [])
        self.assertContains(page, 'value="create_new"')
        self.assertEqual(len(logs.records), 1)
        self.assertIn('LDAPSocketOpenError', logs.output[0])
        self.assertNotIn('zqska', logs.output[0])

    def test_directory_person_in_the_database_is_not_offered_as_new(self):
        known = make_person('Asger', 'Zqskaa', initials='zqska')
        self.start(authors=['zqska'])
        page = self.step_page()
        self.assertEqual(page.context['directory_choices'], [])
        self.assertIn(known, page.context['exact_matches'] + page.context['relaxed_matches'])
        self.assertEqual(page.context['directory_person_ids'], {known.pk})
        self.assertContains(page, 'In DTU directory')
        self.assertNotContains(page, 'value="select_directory"')

    def test_database_person_matched_by_employee_id_is_offered(self):
        # Same employee id, no initials in the database: the name/initials matching of the
        # step doesn't find this person, the directory identifiers do.
        known = make_person('A.', 'Zqskaa-Old', id_number='99001')
        self.start(authors=['zqska'])
        page = self.step_page()
        self.assertEqual(page.context['directory_choices'], [])
        self.assertIn(known, page.context['exact_matches'] + page.context['relaxed_matches'])
        self.assertEqual(page.context['directory_person_ids'], {known.pk})
        self.assertContains(page, 'In DTU directory')

    def test_choosing_a_gone_entry_shows_the_step_again(self):
        self.start(authors=['zqska'])
        self.step_page()
        self.entries.clear()
        response = self.client.post(app_path(STEP_URL), {'action': 'select_directory',
                                                         'directory_id': 'zqska'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['clean_name'], 'zqska')
        self.assertIn('The DTU directory entry is not available (any more). '
                      'Please choose another option.', self.messages_of(response))
        self.assertEqual(self.client.session['person_workflow']['current_step'], 0)

    def test_choosing_another_identifier_than_the_typed_one_is_refused(self):
        self.start(authors=['zqska'])
        response = self.client.post(app_path(STEP_URL), {'action': 'select_directory',
                                                         'directory_id': 's990123'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['person_workflow']['current_step'], 0)


class SaveTests(DirectoryLookupTestBase):

    def test_directory_author_is_created_on_save_without_flags(self):
        persons_before = Person.objects.count()
        response = self.walk(self.start(authors=['zqska', str(self.author2.pk)]),
                             {'zqska': DIRECTORY})
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)
        self.assertEqual(Person.objects.count(), persons_before)  # nothing before the save
        self.assertEqual(get_report_form_data(self.client.session, 'add')['authors'],
                         ['LDAP:zqska:Asger Zqskaa', str(self.author2.pk)])
        review = self.client.get(page_path('add_report_review'))
        self.assertContains(review, 'Asger Zqskaa (zqska, from the DTU directory)')

        self.find.reset_mock()
        self.finalize(page_path('add_report_finalize'))
        self.find.assert_called_once_with(initials='zqska')  # asked again at save
        pub = Publication.objects.get(title='New report')
        self.assertEqual(Person.objects.count(), persons_before + 1)
        person = Person.objects.get(initials='zqska')
        self.assertEqual(
            (person.first, person.last, person.id_number, person.position, person.department,
             person.email, person.created_by),
            ('Asger', 'Zqskaa', '99001', 'Lektor', 'Sustain', '', self.editor))
        self.assertEqual(self.authors_of(pub), [person, self.author2])
        self.assertEqual(self.flags(pub.authorship_set.get(person=person)), self.no_flags())

    def test_existing_person_with_the_identifier_is_reused_at_save(self):
        self.walk(self.start(authors=['zqska']), {'zqska': DIRECTORY})
        # Added by someone else between the step and the save
        known = make_person('Asger', 'Zqskaa', initials='zqska')
        persons_before = Person.objects.count()
        self.finalize(page_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertEqual(self.authors_of(pub), [known])
        self.assertEqual(Person.objects.count(), persons_before)

    def test_directory_supervisor_student(self):
        persons_before = Person.objects.count()
        self.walk(self.start(supervisors=['s990123']), {'s990123': DIRECTORY})
        self.finalize(page_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        person = Person.objects.get(id_number='s990123')
        self.assertEqual((person.first, person.middle, person.last, person.position, person.initials),
                         ('Mia', 'Lund', 'Zqstud', 'student', ''))
        self.assertEqual(self.supervisors_of(pub), [person])
        self.assertEqual(self.authors_of(pub), [self.author1, self.author2])
        self.assertEqual(self.flags(pub.supervisorship_set.get()), self.no_flags())
        self.assertEqual(Person.objects.count(), persons_before + 1)

    def test_same_directory_person_as_author_and_supervisor_is_one_person(self):
        persons_before = Person.objects.count()
        self.walk(self.start(authors=['zqska'], supervisors=['ZQSKA']),
                  {'zqska': DIRECTORY, 'ZQSKA': DIRECTORY})
        self.finalize(page_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        person = Person.objects.get(initials='zqska')
        self.assertEqual(self.authors_of(pub), [person])
        self.assertEqual(self.supervisors_of(pub), [person])
        self.assertEqual(Person.objects.count(), persons_before + 1)

    def test_edit_with_directory_author(self):
        report = self.make_report('25-09')
        self.walk(self.start(page_path('edit_report', pk=report.pk), title='Edited report',
                             authors=[str(self.author1.pk), 'zqska']),
                  {'zqska': DIRECTORY})
        review = self.client.get(page_path('edit_report_review', pk=report.pk))
        self.assertContains(review, 'Asger Zqskaa (zqska, from the DTU directory)')
        self.finalize(page_path('edit_report_finalize', pk=report.pk))
        person = Person.objects.get(initials='zqska')
        self.assertEqual(self.authors_of(report), [self.author1, person])

    def test_abandoned_workflow_creates_no_person(self):
        persons_before = Person.objects.count()
        self.walk(self.start(authors=['zqska']), {'zqska': DIRECTORY})
        self.client.get(page_path('add_report_review'))
        # The user leaves without saving.
        self.assertEqual(Person.objects.count(), persons_before)
        self.assertFalse(Publication.objects.exists())

    def test_entry_gone_at_save_is_an_error_and_creates_nothing(self):
        persons_before = Person.objects.count()
        self.walk(self.start(authors=['zqska'], supervisors=['Neusup, Carl']),
                  {'zqska': DIRECTORY, 'Neusup, Carl': NEW})
        self.entries.clear()
        response, _ = self.finalize(page_path('add_report_finalize'))
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)
        messages = ' '.join(self.messages_of(response))
        self.assertIn('"Asger Zqskaa" (zqska) is no longer in the DTU directory', messages)
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(Person.objects.count(), persons_before)

    def test_failing_directory_at_save_is_an_error_and_creates_nothing(self):
        persons_before = Person.objects.count()
        self.walk(self.start(authors=['zqska']), {'zqska': DIRECTORY})
        self.find.side_effect = LDAPSocketOpenError('down')
        with self.assertLogs('publications.workflows.person', level='WARNING'):
            response, _ = self.finalize(page_path('add_report_finalize'))
        self.assertIn('could not be fetched', ' '.join(self.messages_of(response)))
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(Person.objects.count(), persons_before)

    def test_use_ldap_switched_off_before_save_is_an_error(self):
        self.walk(self.start(authors=['zqska']), {'zqska': DIRECTORY})
        persons_before = Person.objects.count()
        with override_settings(USE_LDAP=False):
            response, _ = self.finalize(page_path('add_report_finalize'))
        self.assertIn('switched off', ' '.join(self.messages_of(response)))
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(Person.objects.count(), persons_before)
