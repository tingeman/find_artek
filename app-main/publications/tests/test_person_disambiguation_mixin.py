"""
Tests for the PersonDisambiguationMixin class in person_disambiguation.py
"""

import unittest
from unittest.mock import MagicMock, patch
from django.test import TestCase, RequestFactory
from django.http import HttpRequest, HttpResponseRedirect
from django.contrib.auth.models import User
from django.urls import reverse

from publications.models import Person
from publications.workflows.person_disambiguation import (
    PersonDisambiguationService,
    PersonDisambiguationMixin
)


class TestForm(PersonDisambiguationMixin):
    """A test form class that inherits from PersonDisambiguationMixin."""
    
    def __init__(self, *args, **kwargs):
        self.fields = {'authors': MagicMock(), 'supervisors': MagicMock()}
        self.cleaned_data = {}
        super().__init__(*args, **kwargs)


class PersonDisambiguationMixinTestCase(TestCase):
    """Test the PersonDisambiguationMixin class."""
    
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
        # Create a request factory
        self.factory = RequestFactory()
        
        # Create a test request
        self.request = self.factory.get('/')
        self.request.user = self.test_user
        
        # Initialize session
        self.request.session = {}
        
        # Create form
        self.form = TestForm(request=self.request)
    
    def test_init(self):
        """Test initialization with and without request."""
        # Test with request
        form_with_request = TestForm(request=self.request)
        self.assertIsNotNone(form_with_request.person_service)
        
        # Test without request
        form_without_request = TestForm()
        self.assertIsNone(form_without_request.person_service)
    
    @patch('publications.workflows.person_disambiguation.Person')
    @patch('publications.workflows.person_disambiguation.create_ordered_queryset')
    def test_process_workflow_result(self, mock_create_queryset, mock_person_class):
        """Test _process_workflow_result processes various value types."""
        cleaned_data = {}
        
        # Set up mocks
        mock_person = MagicMock()
        mock_person.pk = 999
        mock_person_class.return_value = mock_person
        
        # Test processing Person IDs
        self.form._process_workflow_result(cleaned_data, 'authors', [
            str(self.person1.pk),  # String ID
            self.person2,  # Person object
            'CREATE:New Person'  # Create new person
        ])
        
        # Check Person.save was called once (for the new person)
        self.assertEqual(mock_person.save.call_count, 1)
        
        # Check create_ordered_queryset was called with the right IDs
        # This should include the existing person IDs and the newly created one
        mock_create_queryset.assert_called_once()
        args = mock_create_queryset.call_args[0]
        self.assertEqual(args[0], mock_person_class)
        # The IDs should include the two existing persons and the new one
        self.assertEqual(len(args[1]), 3)
        self.assertIn(self.person1.pk, args[1])
        self.assertIn(self.person2.pk, args[1])
        self.assertIn(999, args[1])  # The mock new person ID
        
        # Check cleaned_data was updated
        self.assertEqual(cleaned_data['authors'], mock_create_queryset.return_value)
    
    def test_check_disambiguation_needed(self):
        """Test check_disambiguation_needed returns correct status."""
        # Set up form data
        self.form.cleaned_data = {
            'authors': ['John Smith', 'Unknown Person'],
            'supervisors': []
        }
        
        # Check with field needing disambiguation
        self.assertTrue(self.form.check_disambiguation_needed('authors'))
        
        # Check with empty field
        self.assertFalse(self.form.check_disambiguation_needed('supervisors'))
        
        # Check with QuerySet (already disambiguated)
        from django.db.models.query import QuerySet
        mock_queryset = MagicMock(spec=QuerySet)
        self.form.cleaned_data['authors'] = mock_queryset
        self.assertFalse(self.form.check_disambiguation_needed('authors'))
        
        # Check with no service
        form_without_service = TestForm()
        self.assertFalse(form_without_service.check_disambiguation_needed('authors'))
    
    def test_check_any_disambiguation_needed(self):
        """Test check_any_disambiguation_needed returns correct status."""
        # Set up form data
        self.form.cleaned_data = {
            'authors': ['John Smith', 'Unknown Person'],
            'supervisors': ['Jane Doe']
        }
        
        # Check with at least one field needing disambiguation
        self.assertTrue(self.form.check_any_disambiguation_needed(['authors', 'supervisors']))
        
        # Make authors not need disambiguation
        from django.db.models.query import QuerySet
        mock_queryset = MagicMock(spec=QuerySet)
        self.form.cleaned_data['authors'] = mock_queryset
        
        # Mock supervisors to not need disambiguation
        with patch.object(self.form, 'check_disambiguation_needed', return_value=False):
            self.assertFalse(self.form.check_any_disambiguation_needed(['authors', 'supervisors']))
        
        # Check with no service
        form_without_service = TestForm()
        self.assertFalse(form_without_service.check_any_disambiguation_needed(['authors']))
    
    def test_start_disambiguation_workflow_single_field(self):
        """Test start_disambiguation_workflow with a single field."""
        # Set up form data
        self.form.cleaned_data = {
            'authors': ['Unknown Person']
        }
        
        # Mock request POST data
        self.request.POST = {'authors': ['Unknown Person']}
        
        # Start workflow
        result = self.form.start_disambiguation_workflow('authors')
        
        # Should return redirect
        self.assertIsInstance(result, HttpResponseRedirect)
        self.assertEqual(result.url, reverse('publications:disambiguate_person_step'))
        
        # Check workflow was started
        service = PersonDisambiguationService(self.request)
        self.assertTrue(service.is_workflow_active())
        self.assertEqual(service.get_current_person(), 'Unknown Person')
    
    def test_start_disambiguation_workflow_multiple_fields(self):
        """Test start_disambiguation_workflow with multiple fields."""
        # Set up form data
        self.form.cleaned_data = {
            'authors': ['Unknown Author'],
            'supervisors': ['Unknown Supervisor']
        }
        
        # Mock request POST data
        self.request.POST = {
            'authors': ['Unknown Author'],
            'supervisors': ['Unknown Supervisor']
        }
        
        # Start workflow
        result = self.form.start_disambiguation_workflow(['authors', 'supervisors'])
        
        # Should return redirect
        self.assertIsInstance(result, HttpResponseRedirect)
        self.assertEqual(result.url, reverse('publications:disambiguate_person_step'))
        
        # Check workflows were started
        service = PersonDisambiguationService(self.request)
        self.assertTrue(service.is_workflow_active())
        
        # Should have 2 workflows
        pd_session = self.request.session['person_disambiguation']
        self.assertEqual(len(pd_session['workflows']), 2)
    
    def test_start_disambiguation_workflow_no_disambiguation_needed(self):
        """Test start_disambiguation_workflow when no disambiguation is needed."""
        # Set up form data with already resolved names
        self.form.cleaned_data = {
            'authors': [f'John Smith [id:{self.person1.pk}]']
        }
        
        # Start workflow
        result = self.form.start_disambiguation_workflow('authors')
        
        # Should return None (no redirect needed)
        self.assertIsNone(result)
        
        # No workflow should be active
        service = PersonDisambiguationService(self.request)
        self.assertFalse(service.is_workflow_active())
    
    def test_start_disambiguation_workflow_no_service(self):
        """Test start_disambiguation_workflow with no service."""
        form_without_service = TestForm()
        result = form_without_service.start_disambiguation_workflow('authors')
        self.assertIsNone(result)
    
    def test_has_workflow_redirect(self):
        """Test has_workflow_redirect returns correct status."""
        # No redirect
        self.assertFalse(self.form.has_workflow_redirect())
        
        # With redirect
        self.form._workflow_redirect = HttpResponseRedirect('/')
        self.assertTrue(self.form.has_workflow_redirect())
    
    def test_get_workflow_redirect(self):
        """Test get_workflow_redirect returns the redirect response."""
        # No redirect
        self.assertIsNone(self.form.get_workflow_redirect())
        
        # With redirect
        redirect = HttpResponseRedirect('/')
        self.form._workflow_redirect = redirect
        self.assertEqual(self.form.get_workflow_redirect(), redirect)
    
    def test_clean_with_workflow_data(self):
        """Test clean processes workflow data from session."""
        # Set up session with completed workflow data
        self.request.session['updated_form_data'] = {
            'authors': [str(self.person1.pk)],
            'supervisors': [str(self.person2.pk)]
        }
        self.request.session['workflow_updated_fields'] = ['authors', 'supervisors']
        
        # Create cleaned data
        cleaned_data = {}
        
        # Mock _process_workflow_result to track calls
        process_mock = MagicMock()
        self.form._process_workflow_result = process_mock
        
        # Call clean
        result = self.form.clean()
        
        # Check _process_workflow_result was called for each field
        self.assertEqual(process_mock.call_count, 2)
        calls = [tuple(call[0]) for call in process_mock.call_args_list]
        self.assertIn((cleaned_data, 'authors', [str(self.person1.pk)]), calls)
        self.assertIn((cleaned_data, 'supervisors', [str(self.person2.pk)]), calls)
        
        # Session keys should be cleared
        self.assertNotIn('updated_form_data', self.request.session)
        self.assertNotIn('workflow_updated_fields', self.request.session)
    
    def test_clean_no_workflow_data(self):
        """Test clean with no workflow data."""
        # Create cleaned data
        cleaned_data = {}
        
        # Mock super().clean to return cleaned_data
        with patch.object(PersonDisambiguationMixin, 'clean', return_value=cleaned_data):
            # Mock _process_workflow_result
            process_mock = MagicMock()
            self.form._process_workflow_result = process_mock
            
            # Call clean
            result = self.form.clean()
            
            # Check _process_workflow_result was not called
            process_mock.assert_not_called()
            
            # Result should be cleaned_data
            self.assertEqual(result, cleaned_data)
    
    def test_clean_no_service(self):
        """Test clean with no service."""
        form_without_service = TestForm()
        
        # Mock super().clean to return cleaned_data
        cleaned_data = {}
        with patch.object(PersonDisambiguationMixin, 'clean', return_value=cleaned_data):
            # Call clean
            result = form_without_service.clean()
            
            # Result should be cleaned_data
            self.assertEqual(result, cleaned_data)


class PersonDisambiguationMixinIntegrationTestCase(TestCase):
    """Integration tests for PersonDisambiguationMixin."""
    
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
    
    def test_form_workflow_integration(self):
        """Test integration between the form mixin and disambiguation service."""
        # Create a request
        factory = RequestFactory()
        request = factory.post('/')
        request.user = self.test_user
        request.session = {}
        request.POST = {
            'authors': ['John Smith', 'Unknown Person'],
            'supervisors': ['Jane Doe']
        }
        
        # Create form
        form = TestForm(request=request)
        form.cleaned_data = {
            'authors': ['John Smith', 'Unknown Person'],
            'supervisors': ['Jane Doe']
        }
        
        # Start disambiguation workflow
        redirect = form.start_disambiguation_workflow(['authors', 'supervisors'])
        
        # Should have a redirect
        self.assertIsNotNone(redirect)
        
        # Workflow should be active
        service = PersonDisambiguationService(request)
        self.assertTrue(service.is_workflow_active())
        
        # Get current person
        current_person = service.get_current_person()
        
        # Resolve all persons in all workflows
        while service.is_workflow_active():
            current_person = service.get_current_person()
            # Resolve based on name
            if current_person == 'John Smith':
                service.resolve_current_person(str(self.person1.pk))
            elif current_person == 'Unknown Person':
                service.resolve_current_person('CREATE:New Person')
            elif current_person == 'Jane Doe':
                service.resolve_current_person(str(self.person2.pk))
            else:
                # Unexpected person
                self.fail(f"Unexpected person: {current_person}")
        
        # Complete the workflow
        updated_data, redirect_url = service.finalize_workflow()
        
        # Session should be updated with form data
        self.assertIn('updated_form_data', request.session)
        self.assertIn('workflow_updated_fields', request.session)
        
        # Create a new form instance to test clean method
        new_form = TestForm(request=request)
        new_form.cleaned_data = {}
        
        # Clean should process the workflow results
        result = new_form.clean()
        
        # Check that person objects were created/retrieved
        from django.db.models.query import QuerySet
        self.assertIsInstance(result.get('authors'), QuerySet)
        self.assertIsInstance(result.get('supervisors'), QuerySet)
