"""
Tests for the DisambiguatePersonStepView and CompletePersonWorkflowView classes in person_disambiguation.py
"""

import unittest
from unittest.mock import MagicMock, patch
from django.test import TestCase, RequestFactory, Client
from django.http import HttpRequest, HttpResponseRedirect
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib.messages.storage.fallback import FallbackStorage

from publications.models import Person
from publications.workflows.person_disambiguation import (
    PersonDisambiguationService,
    DisambiguatePersonStepView,
    CompletePersonWorkflowView
)


class DisambiguatePersonStepViewTestCase(TestCase):
    """Test the DisambiguatePersonStepView class."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up data for all test methods."""
        # Create test user
        cls.test_user = User.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='testpass'
        )
        
        # Create some test persons
        cls.person1 = Person.objects.create(
            first="John", 
            last="Smith",
            first_relaxed="J",
            last_relaxed="Smith",
        )
        cls.person2 = Person.objects.create(
            first="Jane", 
            last="Doe",
            first_relaxed="J",
            last_relaxed="Doe",
        )
    
    def setUp(self):
        """Set up for each test."""
        # Create client and login
        self.client = Client()
        self.client.force_login(self.test_user)
        
        # Create factory for more complex requests
        self.factory = RequestFactory()
    
    def _setup_session_with_workflow(self, request):
        """Helper to set up session with active workflow."""
        request.session = {}
        service = PersonDisambiguationService(request)
        service.start_workflow('authors', ['John Smith', 'Unknown Person'], {'authors': ['John Smith', 'Unknown Person']}, '/')
        
        # Set up messages framework
        setattr(request, '_messages', FallbackStorage(request))
        
        return service
    
    @patch('publications.workflows.person_disambiguation.PersonDisambiguationService.get_matches_for_current_person')
    def test_get_with_active_workflow(self, mock_get_matches):
        """Test get method with active workflow."""
        # Set up mock matches
        mock_get_matches.return_value = [
            {'person': self.person1, 'confidence': 1.0, 'match_type': 'exact'}
        ]
        
        # Create request
        request = self.factory.get(reverse('publications:disambiguate_person_step'))
        request.user = self.test_user
        
        # Set up session with workflow
        service = self._setup_session_with_workflow(request)
        
        # Create view and call get
        view = DisambiguatePersonStepView()
        response = view.get(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertIn('John Smith', response.content.decode())
        
    def test_get_no_workflow(self):
        """Test get method with no active workflow."""
        # Create request with empty session
        request = self.factory.get(reverse('publications:disambiguate_person_step'))
        request.user = self.test_user
        request.session = {}
        
        # Set up messages framework
        setattr(request, '_messages', FallbackStorage(request))
        
        # Create view and call get
        view = DisambiguatePersonStepView()
        response = view.get(request)
        
        # Should redirect to frontpage
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('publications:frontpage'))
    
    def test_get_with_invalid_step(self):
        """Test get method with workflow but invalid step."""
        # Create request
        request = self.factory.get(reverse('publications:disambiguate_person_step'))
        request.user = self.test_user
        
        # Set up session with workflow
        service = self._setup_session_with_workflow(request)
        
        # Set invalid step
        pd_session = request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        workflow['current_step'] = 999  # Beyond the number of persons
        
        # Create view and call get
        view = DisambiguatePersonStepView()
        response = view.get(request)
        
        # Should redirect to source URL
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
    
    def test_post_select_existing(self):
        """Test post method with select_existing action."""
        # Create request
        request = self.factory.post(
            reverse('publications:disambiguate_person_step'),
            {'action': 'select_existing', 'person_id': self.person1.pk}
        )
        request.user = self.test_user
        
        # Set up session with workflow
        service = self._setup_session_with_workflow(request)
        
        # Create view and call post
        view = DisambiguatePersonStepView()
        response = view.post(request)
        
        # Check workflow was updated
        pd_session = request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        self.assertEqual(workflow['current_step'], 1)  # Advanced to next person
        self.assertEqual(workflow['resolved_persons']['John Smith'], str(self.person1.pk))
        
        # Check response - should re-render the page for the next person
        self.assertEqual(response.status_code, 200)
    
    def test_post_create_new(self):
        """Test post method with create_new action."""
        # Create request
        request = self.factory.post(
            reverse('publications:disambiguate_person_step'),
            {'action': 'create_new', 'person_name': 'John Smith'}
        )
        request.user = self.test_user
        
        # Set up session with workflow
        service = self._setup_session_with_workflow(request)
        
        # Create view and call post
        view = DisambiguatePersonStepView()
        response = view.post(request)
        
        # Check workflow was updated
        pd_session = request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        self.assertEqual(workflow['current_step'], 1)  # Advanced to next person
        self.assertEqual(workflow['resolved_persons']['John Smith'], 'CREATE:John Smith')
        
        # Check response - should re-render the page for the next person
        self.assertEqual(response.status_code, 200)
    
    def test_post_skip(self):
        """Test post method with skip action."""
        # Create request
        request = self.factory.post(
            reverse('publications:disambiguate_person_step'),
            {'action': 'skip'}
        )
        request.user = self.test_user
        
        # Set up session with workflow
        service = self._setup_session_with_workflow(request)
        
        # Create view and call post
        view = DisambiguatePersonStepView()
        response = view.post(request)
        
        # Check workflow was updated
        pd_session = request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        self.assertEqual(workflow['current_step'], 1)  # Advanced to next person
        self.assertEqual(workflow['resolved_persons']['John Smith'], 'SKIP:John Smith')
        
        # Check response - should re-render the page for the next person
        self.assertEqual(response.status_code, 200)
    
    def test_post_no_workflow(self):
        """Test post method with no active workflow."""
        # Create request with empty session
        request = self.factory.post(
            reverse('publications:disambiguate_person_step'),
            {'action': 'select_existing', 'person_id': self.person1.pk}
        )
        request.user = self.test_user
        request.session = {}
        
        # Set up messages framework
        setattr(request, '_messages', FallbackStorage(request))
        
        # Create view and call post
        view = DisambiguatePersonStepView()
        response = view.post(request)
        
        # Should redirect to frontpage
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('publications:frontpage'))
    
    def test_post_invalid_action(self):
        """Test post method with invalid action."""
        # Create request
        request = self.factory.post(
            reverse('publications:disambiguate_person_step'),
            {'action': 'invalid_action'}
        )
        request.user = self.test_user
        
        # Set up session with workflow
        service = self._setup_session_with_workflow(request)
        
        # Create view and call post
        view = DisambiguatePersonStepView()
        response = view.post(request)
        
        # Should re-render the page without advancing
        self.assertEqual(response.status_code, 200)
        pd_session = request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        self.assertEqual(workflow['current_step'], 0)  # Not advanced
        self.assertEqual(workflow['resolved_persons'], {})  # Not resolved


class CompletePersonWorkflowViewTestCase(TestCase):
    """Test the CompletePersonWorkflowView class."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up data for all test methods."""
        # Create test user
        cls.test_user = User.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='testpass'
        )
        
        # Create some test persons
        cls.person1 = Person.objects.create(
            first="John", 
            last="Smith",
            first_relaxed="J",
            last_relaxed="Smith",
        )
    
    def setUp(self):
        """Set up for each test."""
        # Create client and login
        self.client = Client()
        self.client.force_login(self.test_user)
        
        # Create factory for more complex requests
        self.factory = RequestFactory()
    
    def _setup_session_with_completed_workflow(self, request):
        """Helper to set up session with completed workflow."""
        request.session = {}
        service = PersonDisambiguationService(request)
        service.start_workflow('authors', ['John Smith'], {'authors': ['John Smith']}, '/test')
        
        # Complete workflow
        pd_session = request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        workflow['resolved_persons'] = {'John Smith': str(self.person1.pk)}
        workflow['current_step'] = 1  # Mark as complete
        
        # Set up messages framework
        setattr(request, '_messages', FallbackStorage(request))
        
        return service
    
    @patch('publications.workflows.person_disambiguation.PersonDisambiguationService.finalize_workflow')
    def test_get(self, mock_finalize):
        """Test get method."""
        # Set up mock finalize_workflow
        mock_finalize.return_value = ({'authors': [str(self.person1.pk)]}, '/test')
        
        # Create request
        request = self.factory.get(reverse('publications:complete_person_workflow'))
        request.user = self.test_user
        
        # Set up session with completed workflow
        service = self._setup_session_with_completed_workflow(request)
        
        # Create view and call get
        view = CompletePersonWorkflowView()
        response = view.get(request)
        
        # Check finalize_workflow was called
        mock_finalize.assert_called_once()
        
        # Should redirect to source URL
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/test')
    
    def test_get_no_workflow(self):
        """Test get method with no workflow."""
        # Create request with empty session
        request = self.factory.get(reverse('publications:complete_person_workflow'))
        request.user = self.test_user
        request.session = {}
        
        # Set up messages framework
        setattr(request, '_messages', FallbackStorage(request))
        
        # Create view and call get
        view = CompletePersonWorkflowView()
        response = view.get(request)
        
        # Should redirect to frontpage
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('publications:frontpage'))
    
    def test_get_incomplete_workflow(self):
        """Test get method with incomplete workflow."""
        # Create request
        request = self.factory.get(reverse('publications:complete_person_workflow'))
        request.user = self.test_user
        request.session = {}
        
        # Set up session with incomplete workflow
        service = PersonDisambiguationService(request)
        service.start_workflow('authors', ['John Smith'], {'authors': ['John Smith']}, '/test')
        
        # Set up messages framework
        setattr(request, '_messages', FallbackStorage(request))
        
        # Create view and call get
        view = CompletePersonWorkflowView()
        response = view.get(request)
        
        # Should redirect to disambiguation step
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('publications:disambiguate_person_step'))
    
    def test_integration_complete_workflow(self):
        """Integration test for workflow completion."""
        # Create request
        request = self.factory.get(reverse('publications:complete_person_workflow'))
        request.user = self.test_user
        
        # Set up session with completed workflow
        service = self._setup_session_with_completed_workflow(request)
        
        # Create view and call get
        view = CompletePersonWorkflowView()
        response = view.get(request)
        
        # Should redirect to source URL
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/test')
        
        # Session should have updated form data
        self.assertIn('updated_form_data', request.session)
        self.assertEqual(request.session['updated_form_data']['authors'], [str(self.person1.pk)])
        self.assertEqual(request.session['workflow_updated_fields'], ['authors'])
        
        # Workflow should be cleared
        self.assertEqual(request.session['person_disambiguation']['workflows'], [])
