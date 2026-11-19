"""Typed (new) person names in the add/edit report form (plan "registration" T8, roadmap FA-R12).

The author and supervisor fields post existing persons as pks and typed names as text. A typed
name sends the user through the person disambiguation workflow (disambiguate_person_step,
one step per typed name, then complete_person_workflow) before the review step. These tests
walk that way as a browser would (following every redirect) and then save the report:

- new names ("Create New Person") become new Person rows with name parts and created_by,
  in the order they were entered, for authors and supervisors in the same form;
- a typed name that matches an existing person is offered ("use existing") and reused;
- the new persons are created when the report is saved, inside its transaction: a failed
  save (or an abandoned workflow) leaves no new person behind;
- the form data stays bound to its form (add / edit:<pk>) through the workflow;
- finalize with names that were never resolved sends the user to the workflow, saves nothing.

Same setup as test_report_form (MEDIA_ROOT temporary, finalize in captureOnCommitCallbacks).
"""
from unittest import mock

from django.urls import reverse

from publications.models import Person, Publication
from publications.test_report_form import (
    ReportFormTestBase, _failing_after_handle_files, _path,
)
from publications.test_upload_appendix_access import _app_path
from publications.views import ReportFinalizeView, get_report_form_data, report_form_target

NEW = 'new'  # choice in walk_workflow: "Create New Person"


class ReportFormPersonTestBase(ReportFormTestBase):

    def walk_workflow(self, response, choices):
        """Follow the redirects from a form (or finalize) POST through the disambiguation
        steps. ``choices`` maps each typed name to NEW or to the existing Person to select
        (which must be offered on the step page). Returns the first response that leaves the
        workflow and the (field, name) of each step in order."""
        step_url = reverse('publications:disambiguate_person_step')
        complete_url = reverse('publications:complete_person_workflow')
        steps = []
        for _ in range(20):
            self.assertEqual(response.status_code, 302,
                             f'expected a redirect, got {response.status_code}')
            location = response['Location']
            if location == step_url:
                page = self.client.get(_app_path(location))
                self.assertEqual(page.status_code, 200)
                name = page.context['clean_name']
                steps.append((page.context['field_name'], name))
                choice = choices[name]
                if choice == NEW:
                    response = self.client.post(_app_path(location), {'action': 'create_new'})
                else:
                    offered = {p.pk for p in page.context['exact_matches']}
                    offered |= {p.pk for p in page.context['relaxed_matches']}
                    self.assertIn(choice.pk, offered, f'{choice} not offered for "{name}"')
                    response = self.client.post(_app_path(location), {
                        'action': 'select_existing', 'person_id': str(choice.pk)})
            elif location == complete_url:
                response = self.client.get(_app_path(location))
            else:
                return response, steps
        self.fail('the person workflow did not end')

    def authors_of(self, pub):
        return [a.person for a in pub.authorship_set.order_by('author_id')]

    def supervisors_of(self, pub):
        return [s.person for s in pub.supervisorship_set.order_by('supervisor_id')]

    def assertNewPerson(self, person, first, last):
        self.assertEqual((person.first, person.last), (first, last))
        self.assertEqual(person.created_by, self.editor)


class AddReportNewPersonsTests(ReportFormPersonTestBase):

    def test_typed_new_author_and_supervisor_are_created_on_save(self):
        persons_before = Person.objects.count()
        response = self.client.post(_path('add_report'), self.form_data(
            authors=[str(self.author1.pk), 'Jane Newcomer', str(self.author2.pk)],
            supervisors=['Neusup, Carl', str(self.supervisor.pk)],
        ))
        response, steps = self.walk_workflow(response, {'Jane Newcomer': NEW, 'Neusup, Carl': NEW})
        self.assertEqual(steps, [('authors', 'Jane Newcomer'), ('supervisors', 'Neusup, Carl')])
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)

        # Form data still bound to the add form; nothing is created before the save.
        self.assertIsNotNone(get_report_form_data(self.client.session, 'add'))
        self.assertEqual(Person.objects.count(), persons_before)

        review = self.client.get(_path('add_report_review'))
        self.assertEqual(review.status_code, 200)
        self.assertContains(review, 'Jane Newcomer')
        self.assertContains(review, 'Neusup')

        response, _ = self.finalize(_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': pub.pk}),
                             fetch_redirect_response=False)

        self.assertEqual(Person.objects.count(), persons_before + 2)
        jane = Person.objects.get(last='Newcomer')
        carl = Person.objects.get(last='Neusup')
        self.assertNewPerson(jane, 'Jane', 'Newcomer')
        self.assertNewPerson(carl, 'Carl', 'Neusup')
        self.assertEqual(self.authors_of(pub), [self.author1, jane, self.author2])
        self.assertEqual(self.supervisors_of(pub), [carl, self.supervisor])

    def test_typed_name_of_existing_person_is_reused(self):
        persons_before = Person.objects.count()
        response = self.client.post(_path('add_report'), self.form_data(
            authors=['Ann Author', str(self.author2.pk)],
            supervisors=[str(self.supervisor.pk)],
        ))
        response, steps = self.walk_workflow(response, {'Ann Author': self.author1})
        self.assertEqual(steps, [('authors', 'Ann Author')])
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)

        self.finalize(_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertEqual(self.authors_of(pub), [self.author1, self.author2])
        self.assertEqual(self.supervisors_of(pub), [self.supervisor])
        self.assertEqual(Person.objects.count(), persons_before)

    def test_same_new_name_as_author_and_supervisor_is_one_person(self):
        persons_before = Person.objects.count()
        response = self.client.post(_path('add_report'), self.form_data(
            authors=['Jane Newcomer'], supervisors=['Jane Newcomer']))
        self.walk_workflow(response, {'Jane Newcomer': NEW})
        self.finalize(_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        jane = Person.objects.get(last='Newcomer')
        self.assertEqual(self.authors_of(pub), [jane])
        self.assertEqual(self.supervisors_of(pub), [jane])
        self.assertEqual(Person.objects.count(), persons_before + 1)

    def test_failed_save_leaves_no_new_person(self):
        persons_before = Person.objects.count()
        response = self.client.post(_path('add_report'), self.form_data(
            authors=['Jane Newcomer'], supervisors=['Neusup, Carl']))
        self.walk_workflow(response, {'Jane Newcomer': NEW, 'Neusup, Carl': NEW})

        with mock.patch.object(ReportFinalizeView, '_handle_files', _failing_after_handle_files()):
            response, _ = self.finalize(_path('add_report_finalize'))
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)
        self.assertFalse(Publication.objects.exists())
        self.assertEqual(Person.objects.count(), persons_before)

        # The data is still there: the retry saves the report with both new persons.
        self.finalize(_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertEqual([p.last for p in self.authors_of(pub)], ['Newcomer'])
        self.assertEqual([p.last for p in self.supervisors_of(pub)], ['Neusup'])
        self.assertEqual(Person.objects.count(), persons_before + 2)

    def test_finalize_with_unresolved_name_goes_to_the_workflow(self):
        """Form data with a typed name that never went through the workflow (the user left
        it): finalize saves nothing and sends the user through the workflow first."""
        persons_before = Person.objects.count()
        # The form starts the workflow; the user leaves it and posts the review page instead.
        self.client.post(_path('add_report'), self.form_data(authors=['Jane Newcomer']))

        response, _ = self.finalize(_path('add_report_finalize'))
        self.assertFalse(Publication.objects.exists())
        response, steps = self.walk_workflow(response, {'Jane Newcomer': NEW})
        self.assertEqual(steps, [('authors', 'Jane Newcomer')])
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)
        self.assertEqual(Person.objects.count(), persons_before)

        self.finalize(_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertEqual([p.last for p in self.authors_of(pub)], ['Newcomer'])


    def test_step_offers_no_use_as_is_and_ignores_the_old_skip_action(self):
        """'Use As-Is (Create Later)' was removed (2026-11-19): the step page has no such
        button, and a posted action 'skip' resolves nothing (the same step is shown again)."""
        step_path = _app_path(reverse('publications:disambiguate_person_step'))
        self.client.post(_path('add_report'), self.form_data(authors=['Jane Newcomer']))
        page = self.client.get(step_path)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'value="skip"')
        self.assertNotContains(page, 'Use As-Is')
        self.assertContains(page, 'value="create_new"')

        again = self.client.post(step_path, {'action': 'skip'})
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.context['clean_name'], 'Jane Newcomer')


class EditReportNewPersonsTests(ReportFormPersonTestBase):

    def test_edit_with_typed_new_author_and_supervisor(self):
        report = self.make_report('25-03')
        other = self.make_report('25-04', title='Other report')
        persons_before = Person.objects.count()

        response = self.client.post(_path('edit_report', pk=report.pk), self.form_data(
            title='Edited report',
            authors=[str(self.author1.pk), 'Jane Newcomer'],
            supervisors=['Neusup, Carl'],
        ))
        response, steps = self.walk_workflow(response, {'Jane Newcomer': NEW, 'Neusup, Carl': NEW})
        self.assertEqual(steps, [('authors', 'Jane Newcomer'), ('supervisors', 'Neusup, Carl')])
        self.assertRedirects(response, reverse('publications:edit_report_review', kwargs={'pk': report.pk}),
                             fetch_redirect_response=False)

        # Still bound to this report's edit form, never to another one or the add form.
        session = self.client.session
        self.assertIsNotNone(get_report_form_data(session, report_form_target(report.pk)))
        self.assertIsNone(get_report_form_data(session, report_form_target(other.pk)))
        self.assertIsNone(get_report_form_data(session, 'add'))

        review = self.client.get(_path('edit_report_review', pk=report.pk))
        self.assertEqual(review.status_code, 200)

        response, _ = self.finalize(_path('edit_report_finalize', pk=report.pk))
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': report.pk}),
                             fetch_redirect_response=False)
        report.refresh_from_db()
        self.assertEqual(report.title, 'Edited report')
        jane = Person.objects.get(last='Newcomer')
        carl = Person.objects.get(last='Neusup')
        self.assertNewPerson(jane, 'Jane', 'Newcomer')
        self.assertNewPerson(carl, 'Carl', 'Neusup')
        self.assertEqual(self.authors_of(report), [self.author1, jane])
        self.assertEqual(self.supervisors_of(report), [carl])
        self.assertEqual(Person.objects.count(), persons_before + 2)
        self.assertEqual(self.authors_of(other), [self.author1])

    def test_workflow_of_a_left_form_does_not_change_another_forms_data(self):
        """The workflow started in the edit form of one report, then the user fills in the
        add form; finishing the old workflow later must not write into the add form's data."""
        report = self.make_report('25-06')
        self.client.post(_path('edit_report', pk=report.pk), self.form_data(
            authors=['Jane Newcomer']))
        self.client.post(_path('add_report'), self.form_data(title='Another new report'))
        add_data = get_report_form_data(self.client.session, 'add')

        step = _path('disambiguate_person_step')
        response = self.client.post(step, {'action': 'create_new'})
        response = self.client.get(_app_path(response['Location']))
        self.assertEqual(get_report_form_data(self.client.session, 'add'), add_data)
        self.assertIsNone(get_report_form_data(self.client.session, report_form_target(report.pk)))
        self.assertRedirects(response, reverse('publications:edit_report', kwargs={'pk': report.pk}),
                             fetch_redirect_response=False)

    def test_edit_with_typed_name_of_existing_person(self):
        report = self.make_report('25-05')
        persons_before = Person.objects.count()
        response = self.client.post(_path('edit_report', pk=report.pk), self.form_data(
            title='Edited report', authors=[str(self.author1.pk)], supervisors=['Sue Pervisor']))
        response, _ = self.walk_workflow(response, {'Sue Pervisor': self.supervisor})
        self.assertRedirects(response, reverse('publications:edit_report_review', kwargs={'pk': report.pk}),
                             fetch_redirect_response=False)
        self.finalize(_path('edit_report_finalize', pk=report.pk))
        self.assertEqual(self.supervisors_of(report), [self.supervisor])
        self.assertEqual(Person.objects.count(), persons_before)
