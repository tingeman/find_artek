from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import User
from django.urls import reverse

from publications.models import Person
from publications.services.disambiguation import PersonDisambiguationService


class PersonDisambiguationServiceTests(TestCase):
    """Unit tests for PersonDisambiguationService behaviour."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='tester', password='pw')

        # create an existing person to simulate an ID already present
        self.existing = Person.objects.create(
            first='Existing', last='Person', created_by=self.user, modified_by=self.user
        )

        # helper request with session
        self.request = self.factory.get('/')
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(self.request)
        self.request.session.save()

        self.service = PersonDisambiguationService(self.request)

    def test_start_resolve_finalize_and_process(self):
        """Start a workflow, resolve names (including CREATE), finalize and process CREATE markers."""
        original = {'authors': ['New Author', str(self.existing.id)]}
        # start workflow for authors
        self.service.start_workflow('authors', original['authors'], original)

        pd = self.request.session.get('person_disambiguation')
        self.assertIsNotNone(pd)
        self.assertEqual(pd.get('current_index'), 0)
        self.assertEqual(len(pd.get('workflows', [])), 1)

        # Resolve first person as a CREATE: marker
        current = self.service.get_current_person()
        self.assertEqual(current, 'New Author')
        self.service.resolve_current_person('CREATE:New Author')

        # Resolve second person as existing id (should be considered resolved)
        current = self.service.get_current_person()
        self.assertEqual(current, str(self.existing.id))
        self.service.resolve_current_person(str(self.existing.id))

        # Now finalize workflow - should return updated form data and redirect url
        updated_form_data, redirect_url = self.service.finalize_workflow()
        self.assertIsNotNone(updated_form_data)
        self.assertIn('authors', updated_form_data)

        # The first author should still be a CREATE: marker in resolved_form_data prior to processing
        pd = self.request.session.get('person_disambiguation')
        resolved = pd.get('resolved_form_data')
        self.assertIsInstance(resolved, dict)
        self.assertTrue(any(v.startswith('CREATE:') for v in resolved.get('authors', [])))

        # Process finalized workflows - should create the person and replace CREATE: with new id
        before_count = Person.objects.count()
        processed = self.service.process_finalized_workflows()
        after_count = Person.objects.count()
        self.assertTrue(processed)
        self.assertEqual(after_count, before_count + 1)

        # session top-level form_data should have been updated with new person id(s)
        form_data = self.request.session.get('form_data')
        self.assertIsNotNone(form_data)
        self.assertIn('authors', form_data)
        # First author should now be numeric id string
        self.assertTrue(form_data['authors'][0].isdigit())

    def test_extract_persons_needing_disambiguation(self):
        """Ensure extraction returns only names that require disambiguation."""
        data = {'authors': ['   ', str(self.existing.id), 'New Person', 'SKIP:Ignore Me']}
        extracted = self.service.extract_persons_needing_disambiguation(data, 'authors')
        # Should include only 'New Person' (non-empty, not resolved, not skipped)
        self.assertEqual(extracted, ['New Person'])

    def test_clear_all_reinitializes_namespace(self):
        # start a workflow to populate session
        self.service.start_workflow('authors', ['A B'], {'authors': ['A B']})
        self.assertTrue(self.request.session.get('person_disambiguation'))
        # clear all should remove and re-create the namespace
        self.service.clear_all()
        pd = self.request.session.get('person_disambiguation')
        self.assertIsNotNone(pd)
        self.assertIn('workflows', pd)
        self.assertIsNone(pd.get('current_index'))

    def test_is_workflow_active_and_finalized(self):
        # No workflow
        self.assertFalse(self.service.is_workflow_active())

        # With workflow
        person_names = ['John Smith', 'Jane Doe']
        self.service.start_workflow('authors', person_names, {}, '/test')
        self.assertTrue(self.service.is_workflow_active())

        # Completed workflow: set current_step to number of pending_persons
        pd_session = self.request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        workflow['current_step'] = len(workflow.get('pending_persons', []))
        self.assertFalse(self.service.is_workflow_active())
        self.assertTrue(self.service.is_workflow_finalized())

        # Invalid current_index
        pd_session['current_index'] = 5  # Out of range
        self.assertFalse(self.service.is_workflow_active())
        pd_session['current_index'] = None
        self.assertFalse(self.service.is_workflow_active())


class PersonDisambiguationServiceIntegrationTestCase(TestCase):
    """Integration tests for PersonDisambiguationService."""

    @classmethod
    def setUpTestData(cls):
        cls.test_user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass'
        )
        cls.person1 = Person.objects.create(first="John", last="Smith")
        cls.person2 = Person.objects.create(first="Jane", last="Doe")

    def setUp(self):
        factory = RequestFactory()
        self.request = factory.get('/')
        self.request.user = self.test_user
        # attach a real session via middleware
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(self.request)
        self.request.session.save()
        self.service = PersonDisambiguationService(self.request)

    def test_workflow_complete_cycle(self):
        original_data = {'authors': ['John Smith', 'Unknown Person', 'Jane Doe']}
        self.service.start_workflow('authors', ['John Smith', 'Unknown Person'], original_data, '/test')

        # Verify current person
        self.assertEqual(self.service.get_current_person(), 'John Smith')

        # Get matches for current person
        matches = self.service.get_matches_for_current_person()
        # Should find person1
        self.assertTrue(any(m['person'].pk == self.person1.pk for m in matches))

        # Resolve current person
        self.service.resolve_current_person(str(self.person1.pk))

        # Verify next person
        self.assertEqual(self.service.get_current_person(), 'Unknown Person')

        # Resolve next person as CREATE
        self.service.resolve_current_person('CREATE:New Person')

        # Workflow should be finalized now
        self.assertTrue(self.service.is_workflow_finalized())

        # Finalize workflow
        updated_data, redirect_url = self.service.finalize_workflow()

        # Check results
        self.assertEqual(updated_data['authors'][0], str(self.person1.pk))
        self.assertTrue(updated_data['authors'][1].startswith('CREATE:'))

        # After processing, the CREATE should become a numeric id
        processed = self.service.process_finalized_workflows()
        self.assertTrue(processed)
        form_data = self.request.session.get('form_data')
        self.assertTrue(form_data['authors'][1].isdigit())
