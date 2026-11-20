"""Person disambiguation workflow (publications.workflows.person): the gaps the report form
tests (test_report_form_persons) don't walk.

- extract_person_names: which posted values still need a step (typed names) and which don't
  (pks, valid [id:<pk>] tags, CREATE:/SKIP: markers, list strings from older session data);
- the step and complete views when the session is not what they expect (no workflow, a
  selected person that doesn't exist, an unfinished workflow, lost form data);
- person_from_form_value with an empty name.
All names are made up.
"""

from django.contrib.messages import get_messages
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

# publications.forms first: workflows.person and forms.mixins import each other, and
# importing workflows.person first fails (the app always loads it through views/forms).
import publications.forms  # noqa: F401
from publications.models import Person
from publications.test_factories import make_person, make_user, page_path
from publications.workflows.person import (
    extract_person_names, get_person_matches, person_from_form_value,
)


def post_data(field, *values):
    data = QueryDict(mutable=True)
    data.setlist(field, list(values))
    return data


class ExtractPersonNamesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.jane = make_person('Jane', 'Zqroe')

    def test_typed_names_need_a_step(self):
        self.assertEqual(
            extract_person_names(post_data('authors', 'Jane Zqroe', 'Ann Zqlee'), 'authors'),
            ['Jane Zqroe', 'Ann Zqlee'])

    def test_existing_pk_needs_no_step(self):
        self.assertEqual(
            extract_person_names(post_data('authors', str(self.jane.pk), 'Ann Zqlee'),
                                 'authors'),
            ['Ann Zqlee'])

    def test_missing_pk_is_treated_as_a_name(self):
        self.assertEqual(extract_person_names(post_data('authors', '999999'), 'authors'),
                         ['999999'])

    def test_valid_id_tag_needs_no_step(self):
        value = f'Jane Zqroe [id:{self.jane.pk}]'
        self.assertEqual(extract_person_names(post_data('authors', value), 'authors'), [])

    def test_id_tag_of_missing_person_needs_a_step(self):
        value = 'Jane Zqroe [id:999999]'
        self.assertEqual(extract_person_names(post_data('authors', value), 'authors'), [value])

    def test_id_tag_zero_needs_no_step(self):
        self.assertEqual(
            extract_person_names(post_data('authors', 'Ann Zqlee [id:0]'), 'authors'), [])

    def test_markers_need_no_step(self):
        data = post_data('authors', 'CREATE:Ann Zqlee', 'SKIP:Bo Zqvik', '', '  ')
        self.assertEqual(extract_person_names(data, 'authors'), [])

    def test_list_string_from_session_data_is_split(self):
        data = {'authors': [f"['Ann Zqlee', '{self.jane.pk}']"]}
        self.assertEqual(extract_person_names(data, 'authors'), ['Ann Zqlee'])

    def test_unparsable_list_string_is_one_name(self):
        data = {'authors': '[Ann Zqlee]'}
        self.assertEqual(extract_person_names(data, 'authors'), ['[Ann Zqlee]'])

    def test_missing_field(self):
        self.assertEqual(extract_person_names({}, 'authors'), [])
        self.assertEqual(extract_person_names({'authors': None}, 'authors'), [])

    def test_matches_of_empty_name(self):
        self.assertEqual(get_person_matches('[id:0]'), {'exact': [], 'relaxed': []})


class WorkflowViewEdgeTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('zqeditor')
        cls.jane = make_person('Jane', 'Zqroe')

    def setUp(self):
        self.client.force_login(self.user)

    def set_workflow(self, pending, step=0, resolved=(), target='add'):
        session = self.client.session
        session['person_workflow'] = {
            'pending_persons': list(pending),
            'pending_fields': ['authors'] * len(pending),
            'resolved': list(resolved),
            'original_form_data': {},
            'current_step': step,
            'field_name': 'authors',
            'source_url': '/',
            'target': target,
        }
        session.save()

    def messages_of(self, response):
        return [m.message for m in get_messages(response.wsgi_request)]

    def test_step_requires_login(self):
        self.client.logout()
        response = self.client.get(page_path('disambiguate_person_step'))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response['Location'], reverse('publications:add_report'))

    def test_step_without_workflow_goes_to_the_add_form(self):
        response = self.client.get(page_path('disambiguate_person_step'))
        self.assertRedirects(response, reverse('publications:add_report'),
                             fetch_redirect_response=False)
        self.assertIn('No person to disambiguate.', self.messages_of(response))

    def test_selecting_a_missing_person_shows_the_step_again(self):
        self.set_workflow(['Jane Zqroe'])
        response = self.client.post(page_path('disambiguate_person_step'),
                                    {'action': 'select_existing', 'person_id': '999999'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['clean_name'], 'Jane Zqroe')
        self.assertIn('Selected person not found.', self.messages_of(response))
        self.assertEqual(self.client.session['person_workflow']['current_step'], 0)

    def test_step_offers_the_matching_person(self):
        self.set_workflow(['Jane Zqroe'])
        response = self.client.get(page_path('disambiguate_person_step'))
        self.assertEqual(response.context['exact_matches'], [self.jane])
        self.assertEqual((response.context['step_number'], response.context['total_steps']),
                         (1, 1))

    def test_create_new_for_a_name_of_only_tags_is_refused(self):
        self.set_workflow(['[id:999999]'])
        response = self.client.post(page_path('disambiguate_person_step'),
                                    {'action': 'create_new'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Empty name.', self.messages_of(response))
        self.assertEqual(self.client.session['person_workflow']['current_step'], 0)

    def test_complete_before_all_steps_goes_back_to_the_step(self):
        self.set_workflow(['Jane Zqroe', 'Ann Zqlee'], step=1,
                          resolved=[['authors', 'Jane Zqroe', str(self.jane.pk)]])
        response = self.client.get(page_path('complete_person_workflow'))
        self.assertRedirects(response, reverse('publications:disambiguate_person_step'),
                             fetch_redirect_response=False)
        self.assertIn('Workflow not complete.', self.messages_of(response))

    def test_complete_with_lost_edit_form_data_goes_back_to_the_edit_form(self):
        self.set_workflow(['Jane Zqroe'], step=1,
                          resolved=[['authors', 'Jane Zqroe', str(self.jane.pk)]],
                          target='edit:4242')
        response = self.client.get(page_path('complete_person_workflow'))
        self.assertRedirects(response, reverse('publications:edit_report', kwargs={'pk': 4242}),
                             fetch_redirect_response=False)
        self.assertNotIn('person_workflow', self.client.session)


class PersonFromFormValueTests(TestCase):

    def test_empty_create_marker_is_refused(self):
        user = make_user('zqeditor')
        before = Person.objects.count()
        with self.assertRaises(ValueError):
            person_from_form_value('CREATE:  ', user, {})
        self.assertEqual(Person.objects.count(), before)
