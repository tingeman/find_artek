from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import User
from django.http import QueryDict

from publications.models import Person
from publications.services.disambiguation import PersonDisambiguationService


class PersonDisambiguationServiceEdgeCases(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='edge', password='pw')

        self.request = self.factory.get('/')
        self.request.user = self.user
        middleware = SessionMiddleware(get_response=lambda r: None)
        middleware.process_request(self.request)
        self.request.session.save()

        self.service = PersonDisambiguationService(self.request)

    def test_multi_workflow_queue_and_advance(self):
        # Start two workflows queued
        self.service.start_workflow('authors', ['A1', 'A2'], {'authors': ['A1', 'A2']})
        self.service.start_workflow('supervisors', ['S1'], {'supervisors': ['S1']})

        pd = self.request.session['person_disambiguation']
        self.assertEqual(len(pd['workflows']), 2)
        self.assertEqual(pd['current_index'], 0)

        # Resolve both persons in first workflow
        self.service.resolve_current_person('1')
        self.service.resolve_current_person('2')

        # Finalizing first workflow should advance to next
        res = self.service.finalize_workflow()
        # finalize_workflow may return None or a tuple with first element None when advancing
        if res is not None:
            # allow shape (None, redirect_url)
            self.assertIsInstance(res, tuple)
            self.assertIsNone(res[0])
        pd = self.request.session['person_disambiguation']
        self.assertEqual(pd.get('current_index'), 1)

    def test_extract_raw_person_data_variants(self):
        # QueryDict with multiple values
        q = QueryDict('authors=Alice&authors=Bob')
        res = self.service._extract_raw_person_data(q, 'authors')
        self.assertEqual(res, ['Alice', 'Bob'])

        # semicolon-delimited string
        data = {'authors': 'Alice; Bob;Charlie'}
        res2 = self.service._extract_raw_person_data(data, 'authors')
        self.assertEqual(res2, ['Alice', 'Bob', 'Charlie'])

        # comma-delimited string
        data2 = {'authors': 'X, Y, Z'}
        self.assertEqual(self.service._extract_raw_person_data(data2, 'authors'), ['X', 'Y', 'Z'])

        # stringified list
        data3 = {'authors': "['One','Two']"}
        self.assertEqual(self.service._extract_raw_person_data(data3, 'authors'), ['One', 'Two'])

    def test_process_finalized_workflows_multi_field(self):
        # Prepare finalized workflows and resolved_field_values with CREATE markers
        pd = self.request.session['person_disambiguation']
        pd['workflows'] = [
            {'field_name': 'authors', 'pending_persons': [], 'current_step': 0},
            {'field_name': 'supervisors', 'pending_persons': [], 'current_step': 0},
        ]
        # resolved_field_values is what get_resolved_form_data reads to build final form
        pd['resolved_field_values'] = {
            'authors': ['CREATE:Auth A', '123'],
            'supervisors': ['CREATE:Sup A']
        }
        # do not attempt to save non-serializable objects; assign into session mapping
        self.request.session['person_disambiguation'] = pd

        before = Person.objects.count()
        processed = self.service.process_finalized_workflows()
        after = Person.objects.count()
        # should have created two new persons (one author and one supervisor)
        self.assertTrue(processed)
        self.assertEqual(after - before, 2)

        # top-level form_data should exist and contain numeric ids (strings)
        form_data = self.request.session.get('form_data')
        self.assertIsNotNone(form_data)
        self.assertIn('authors', form_data)
        self.assertTrue(all(isinstance(v, str) for v in form_data['authors']))

    def test_get_resolved_form_data_preserves_order(self):
        # Ensure workflows exist so get_resolved_form_data rebuilds from resolved_field_values
        pd = self.request.session['person_disambiguation']
        pd['workflows'] = [{'field_name': 'authors'}]
        pd['original_form_data'] = {'authors': ['first', 'middle', 'last']}
        pd['resolved_field_values'] = {
            'authors': ['2', 'CREATE:New', '1']
        }
        self.request.session['person_disambiguation'] = pd

        resolved = self.service.get_resolved_form_data()
        self.assertIn('authors', resolved)
        self.assertEqual(resolved['authors'], ['2', 'CREATE:New', '1'])

    def test_is_name_resolved_edge_cases(self):
        # id_tag == 0 -> treated as resolved (create marker)
        # monkeypatch _get_tag to return 0
        orig_get_tag = self.service._get_tag
        self.service._get_tag = lambda s, t: 0
        self.assertTrue(self.service.is_name_resolved('anything'))

        # ldap tag should be treated as not resolved (mock returns 'ldap')
        self.service._get_tag = lambda s, t: 'ldap'
        self.assertFalse(self.service.is_name_resolved('someone'))

        # numeric id that does not exist -> False
        self.service._get_tag = orig_get_tag
        self.assertFalse(self.service.is_name_resolved('9999999'))

    def test_update_form_data_with_resolved_persons_various_values(self):
        # prepare a workflow with resolved_persons mapping to different value types
        existing = Person.objects.create(first='Exist', last='User', created_by=self.user, modified_by=self.user)

        # Build an in-memory session dict (avoid putting Person instances into actual session storage)
        pd = {
            'original_form_data': {'authors': ['A', 'B', 'C']},
            'workflows': [],
            'resolved_field_values': {}
        }
        wf = {
            'field_name': 'authors',
            'pending_persons': ['A', 'B', 'C'],
            'resolved_persons': {
                'A': str(existing.pk),
                'B': existing,  # Person object provided directly to service (not serialized)
                'C': 'CREATE:NewOne'
            },
            'current_step': 3
        }

        pd['workflows'].append(wf)
        pd['current_index'] = 0

        # Monkeypatch the service to return our in-memory pd
        self.service._get_session_data = lambda: pd

        updated = self.service.update_form_data_with_resolved_persons()
        self.assertIsNotNone(updated)
        self.assertIn('authors', updated)
        vals = updated['authors']

        # A should become the existing id string
        self.assertEqual(str(existing.pk), vals[0])
        # B may be returned as a Person object or as its id; accept both
        if hasattr(vals[1], 'pk'):
            self.assertEqual(existing.pk, vals[1].pk)
        else:
            self.assertEqual(str(existing.pk), vals[1])
        # C remains CREATE: marker
        self.assertTrue(str(vals[2]).startswith('CREATE:'))
