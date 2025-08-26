"""
Tests for the PersonDisambiguationService class in person_disambiguation.py
"""

import unittest
from unittest.mock import MagicMock, patch
from django.test import TestCase, RequestFactory
from django.http import HttpRequest
from django.contrib.auth.models import User
from django.urls import reverse
import ast

from publications.models import Person
from publications.workflows.person_disambiguation import (
    PersonDisambiguationService,
    PersonMatcher,
    MockFormData
)


class MockFormDataTestCase(TestCase):
    """Test the MockFormData class."""
    
    def test_getlist(self):
        """Test MockFormData.getlist returns the data regardless of field_name."""
        data = ["John Smith", "Jane Doe"]
        form_data = MockFormData(data)
        
        # Should return the data regardless of field_name
        self.assertEqual(form_data.getlist("authors"), data)
        self.assertEqual(form_data.getlist("irrelevant"), data)
    
    def test_get(self):
        """Test MockFormData.get returns the data with default handling."""
        data = ["John Smith", "Jane Doe"]
        form_data = MockFormData(data)
        
        # Should return the data regardless of field_name
        self.assertEqual(form_data.get("authors"), data)
        
        # Test with empty data and default
        empty_form = MockFormData([])
        self.assertEqual(empty_form.get("authors", "default"), [])
        
        # Test with None data and default
        none_form = MockFormData(None)
        self.assertEqual(none_form.get("authors", "default"), None)
        
        # Test with default value when data is None
        self.assertEqual(none_form.get("authors", "default"), None)


class PersonDisambiguationServiceTestCase(TestCase):
    """Test the PersonDisambiguationService class."""
    
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
            email="john.smith@example.com"
        )
        cls.person2 = Person.objects.create(
            first="Jane", 
            last="Doe",
            first_relaxed="J",
            last_relaxed="Doe",
            email="jane.doe@example.com"
        )
        cls.person3 = Person.objects.create(
            first="Michael", 
            last="Johnson",
            first_relaxed="M",
            last_relaxed="Johnson"
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
        
        # Create service
        self.service = PersonDisambiguationService(self.request)
    
    def test_init_ensures_session(self):
        """Test that initialization ensures workflow session."""
        # Session should be initialized
        self.assertIn('person_disambiguation', self.request.session)
        
        # Check the structure
        pd_session = self.request.session['person_disambiguation']
        self.assertIn('workflows', pd_session)
        self.assertIn('current_index', pd_session)
        self.assertIn('all_updated_form_data', pd_session)
    
    def test_start_workflow(self):
        """Test start_workflow correctly initializes a workflow."""
        field_name = 'authors'
        person_names = ['John Smith', 'Jane Doe']
        original_form_data = {'authors': person_names}
        source_url = '/test/url'
        
        # Start a workflow
        self.service.start_workflow(field_name, person_names, original_form_data, source_url)
        
        # Check workflow was added
        pd_session = self.request.session['person_disambiguation']
        self.assertEqual(len(pd_session['workflows']), 1)
        
        # Check workflow structure
        workflow = pd_session['workflows'][0]
        self.assertEqual(workflow['pending_persons'], person_names)
        self.assertEqual(workflow['field_name'], field_name)
        self.assertEqual(workflow['source_url'], source_url)
        self.assertEqual(workflow['original_form_data'], original_form_data)
        self.assertEqual(workflow['current_step'], 0)
    
    def test_get_current_person(self):
        """Test get_current_person returns the current person name."""
        # Set up workflow
        person_names = ['John Smith', 'Jane Doe']
        self.service.start_workflow('authors', person_names, {}, '/test')
        
        # Check current person
        self.assertEqual(self.service.get_current_person(), 'John Smith')
        
        # Advance to next person
        pd_session = self.request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        workflow['current_step'] = 1
        
        # Check current person after advancing
        self.assertEqual(self.service.get_current_person(), 'Jane Doe')
        
        # Advance beyond the end
        workflow['current_step'] = 2
        self.assertIsNone(self.service.get_current_person())
        
        # Set invalid current_index
        pd_session['current_index'] = None
        self.assertIsNone(self.service.get_current_person())
    
    def test_get_current_step_info(self):
        """Test get_current_step_info returns the correct progress information."""
        # Set up workflow
        person_names = ['John Smith', 'Jane Doe', 'Michael Johnson']
        self.service.start_workflow('authors', person_names, {}, '/test')
        
        # Check initial step info
        info = self.service.get_current_step_info()
        self.assertEqual(info['current_step'], 1)  # 1-based
        self.assertEqual(info['total_steps'], 3)
        self.assertEqual(info['progress_percent'], 0)
        
        # Advance to next person
        pd_session = self.request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        workflow['current_step'] = 1
        
        # Check updated step info
        info = self.service.get_current_step_info()
        self.assertEqual(info['current_step'], 2)
        self.assertEqual(info['total_steps'], 3)
        self.assertEqual(info['progress_percent'], 33)
        
        # Test with no workflow
        pd_session['current_index'] = None
        info = self.service.get_current_step_info()
        self.assertEqual(info['current_step'], 0)
        self.assertEqual(info['total_steps'], 0)
        self.assertEqual(info['progress_percent'], 0)
    
    def test_resolve_current_person(self):
        """Test resolve_current_person updates the workflow correctly."""
        # Set up workflow
        person_names = ['John Smith', 'Jane Doe']
        self.service.start_workflow('authors', person_names, {}, '/test')
        
        # Resolve the current person
        resolution_data = str(self.person1.pk)
        self.service.resolve_current_person(resolution_data)
        
        # Check workflow was updated
        pd_session = self.request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        self.assertEqual(workflow['current_step'], 1)
        self.assertEqual(workflow['resolved_persons']['John Smith'], resolution_data)
        
        # Test with invalid current_index
        pd_session['current_index'] = None
        self.service.resolve_current_person('test')
        # Should not crash and make no changes
        self.assertEqual(workflow['current_step'], 1)
    
    def test_is_workflow_active(self):
        """Test is_workflow_active returns correct status."""
        # No workflow
        self.assertFalse(self.service.is_workflow_active())
        
        # With workflow
        person_names = ['John Smith', 'Jane Doe']
        self.service.start_workflow('authors', person_names, {}, '/test')
        self.assertTrue(self.service.is_workflow_active())
        
        # Completed workflow
        pd_session = self.request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        workflow['current_step'] = 2  # Beyond end
        self.assertFalse(self.service.is_workflow_active())
        
        # Invalid current_index
        pd_session['current_index'] = 5  # Out of range
        self.assertFalse(self.service.is_workflow_active())
        
        pd_session['current_index'] = None
        self.assertFalse(self.service.is_workflow_active())
    
    def test_is_workflow_complete(self):
        """Test is_workflow_complete returns correct status."""
        # No workflow
        self.assertFalse(self.service.is_workflow_complete())
        
        # With workflow
        person_names = ['John Smith', 'Jane Doe']
        self.service.start_workflow('authors', person_names, {}, '/test')
        self.assertFalse(self.service.is_workflow_complete())
        
        # Completed workflow
        pd_session = self.request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        workflow['current_step'] = 2  # Beyond end
        self.assertTrue(self.service.is_workflow_complete())
        
        # Invalid current_index
        pd_session['current_index'] = None
        self.assertFalse(self.service.is_workflow_complete())
    
    def test_get_matches_for_current_person(self):
        """Test get_matches_for_current_person returns matches using PersonMatcher."""
        # Set up workflow with a name that will match
        self.service.start_workflow('authors', ['John Smith'], {}, '/test')
        
        # Get matches
        matches = self.service.get_matches_for_current_person()
        
        # Should find person1
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)
        
        # Test with no current person
        pd_session = self.request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        workflow['current_step'] = 1  # Beyond end
        self.assertEqual(self.service.get_matches_for_current_person(), [])
    
    def test_extract_persons_needing_disambiguation(self):
        """Test extract_persons_needing_disambiguation filters names correctly."""
        form_data = {'authors': ['John Smith', 'Unknown Person', 'SKIP:Skip Me']}
        
        # Extract persons
        names = self.service.extract_persons_needing_disambiguation(form_data, 'authors')
        
        # Should include Unknown Person but not John Smith (matches) or SKIP:Skip Me
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0], 'Unknown Person')

    def test_extract_raw_person_data(self):
        """Test _extract_raw_person_data handles various input formats."""
        # Test standard list format
        data1 = {'authors': ['John Smith', 'Jane Doe']}
        result1 = self.service._extract_raw_person_data(data1, 'authors')
        self.assertEqual(result1, ['John Smith', 'Jane Doe'])
        
        # Test string with comma delimiter
        data2 = {'authors': 'John Smith, Jane Doe'}
        result2 = self.service._extract_raw_person_data(data2, 'authors')
        self.assertEqual(result2, ['John Smith', 'Jane Doe'])
        
        # Test string with semicolon delimiter
        data3 = {'authors': 'John Smith; Jane Doe'}
        result3 = self.service._extract_raw_person_data(data3, 'authors')
        self.assertEqual(result3, ['John Smith', 'Jane Doe'])
        
        # Test mixed delimiters - should prefer semicolon
        data4 = {'authors': 'John Smith; Jane, Doe'}
        result4 = self.service._extract_raw_person_data(data4, 'authors')
        self.assertEqual(result4, ['John Smith', 'Jane, Doe'])
        
        # Test string representation of list
        data5 = {'authors': "['John Smith', 'Jane Doe']"}
        result5 = self.service._extract_raw_person_data(data5, 'authors')
        self.assertEqual(result5, ['John Smith', 'Jane Doe'])
        
        # Test with form-like object (getlist method)
        mock_form = MagicMock()
        mock_form.getlist.return_value = ['John Smith', 'Jane Doe']
        result6 = self.service._extract_raw_person_data(mock_form, 'authors')
        self.assertEqual(result6, ['John Smith', 'Jane Doe'])
        mock_form.getlist.assert_called_with('authors')
        
        # Test empty or None values
        data7 = {'authors': None}
        result7 = self.service._extract_raw_person_data(data7, 'authors')
        self.assertEqual(result7, [])
        
        data8 = {}
        result8 = self.service._extract_raw_person_data(data8, 'authors')
        self.assertEqual(result8, [])
    
    def test_is_already_resolved(self):
        """Test _is_already_resolved correctly identifies resolved names."""
        # SKIP prefix
        self.assertTrue(self.service._is_already_resolved('SKIP:John Smith'))
        
        # ID tag for existing person
        self.assertTrue(
            self.service._is_already_resolved(f'John Smith [id:{self.person1.pk}]')
        )
        
        # ID tag for non-existing person
        self.assertFalse(self.service._is_already_resolved('John Smith [id:999999]'))
        
        # ID=0 tag (marked for creation)
        self.assertTrue(self.service._is_already_resolved('John Smith [id:0]'))
        
        # Numeric ID
        self.assertTrue(self.service._is_already_resolved(str(self.person1.pk)))
        
        # Non-existent numeric ID
        self.assertFalse(self.service._is_already_resolved('999999'))
        
        # Regular name
        self.assertFalse(self.service._is_already_resolved('John Smith'))
    
    def test_get_tag(self):
        """Test _get_tag extracts tag values correctly."""
        # Basic tag
        self.assertEqual(self.service._get_tag('John Smith [id:123]', 'id'), 123)
        
        # String tag
        self.assertEqual(self.service._get_tag('John Smith [type:student]', 'type'), 'student')
        
        # Special values
        self.assertEqual(self.service._get_tag('John Smith [id:0]', 'id'), 0)
        self.assertEqual(self.service._get_tag('John Smith [id:ldap]', 'id'), 'ldap')
        
        # Missing tag
        self.assertIsNone(self.service._get_tag('John Smith', 'id'))
        self.assertIsNone(self.service._get_tag('John Smith [type:student]', 'id'))
    
    def test_remove_tags(self):
        """Test _remove_tags removes all tags from string."""
        self.assertEqual(self.service._remove_tags('John Smith [id:123]'), 'John Smith')
        self.assertEqual(
            self.service._remove_tags('John Smith [id:123] [type:student]'), 
            'John Smith'
        )
        self.assertEqual(self.service._remove_tags('John Smith'), 'John Smith')
    
    def test_update_form_data_with_resolved_persons(self):
        """Test update_form_data_with_resolved_persons builds updated form data."""
        # Set up completed workflow
        original_data = {'authors': ['John Smith', 'Unknown Person', 'Jane Doe']}
        self.service.start_workflow('authors', ['John Smith', 'Unknown Person'], original_data, '/test')
        
        pd_session = self.request.session['person_disambiguation']
        workflow = pd_session['workflows'][0]
        workflow['resolved_persons'] = {
            'John Smith': str(self.person1.pk),
            'Unknown Person': 'CREATE:New Person'
        }
        workflow['current_step'] = 2  # Mark as complete
        
        # Get updated form data
        updated_data = self.service.update_form_data_with_resolved_persons()
        
        # Check structure
        self.assertEqual(updated_data['authors'], [
            str(self.person1.pk),
            'CREATE:New Person',
            'Jane Doe'  # Unresolved value preserved
        ])
        
        # Test with incomplete workflow
        workflow['current_step'] = 1  # Not complete
        self.assertIsNone(self.service.update_form_data_with_resolved_persons())
    
    def test_finalize_workflow(self):
        """Test finalize_workflow updates session and returns form data with redirect."""
        # Set up multiple workflows
        original_data = {'authors': ['John Smith'], 'supervisors': ['Jane Doe']}
        self.service.start_workflow('authors', ['John Smith'], original_data, '/test')
        self.service.start_workflow('supervisors', ['Jane Doe'], original_data, '/test')
        
        pd_session = self.request.session['person_disambiguation']
        # Set current index to first workflow
        pd_session['current_index'] = 0
        
        # Complete first workflow
        workflow1 = pd_session['workflows'][0]
        workflow1['resolved_persons'] = {'John Smith': str(self.person1.pk)}
        workflow1['current_step'] = 1
        
        # Finalize
        updated_data, redirect_url = self.service.finalize_workflow()
        
        # Should advance to next workflow
        self.assertEqual(pd_session['current_index'], 1)
        self.assertEqual(redirect_url.url, reverse('publications:disambiguate_person_step'))
        self.assertIsNone(updated_data)  # Not all workflows complete
        
        # Now complete second workflow
        workflow2 = pd_session['workflows'][1]
        workflow2['resolved_persons'] = {'Jane Doe': str(self.person2.pk)}
        workflow2['current_step'] = 1
        
        # Finalize again
        updated_data, redirect_url = self.service.finalize_workflow()
        
        # Should return combined data and redirect to source
        self.assertEqual(updated_data['authors'], [str(self.person1.pk)])
        self.assertEqual(updated_data['supervisors'], [str(self.person2.pk)])
        self.assertEqual(redirect_url, '/test')
        
        # Check session data
        self.assertIn('updated_form_data', self.request.session)
        self.assertEqual(
            self.request.session['updated_form_data']['authors'], 
            [str(self.person1.pk)]
        )
        self.assertEqual(
            self.request.session['updated_form_data']['supervisors'], 
            [str(self.person2.pk)]
        )
        self.assertEqual(
            self.request.session['workflow_updated_fields'], 
            ['authors', 'supervisors']
        )
        
        # Test with incomplete workflow
        self.service.start_workflow('authors', ['John Smith'], original_data, '/test')
        self.assertEqual(self.service.finalize_workflow(), (None, None))
    
    def test_clear_single_workflow(self):
        """Test clear_single_workflow removes specific workflows."""
        # Set up multiple workflows
        self.service.start_workflow('authors', ['John Smith'], {}, '/test')
        self.service.start_workflow('supervisors', ['Jane Doe'], {}, '/test')
        self.service.start_workflow('editors', ['Michael Johnson'], {}, '/test')
        
        pd_session = self.request.session['person_disambiguation']
        self.assertEqual(len(pd_session['workflows']), 3)
        
        # Clear by field_name
        self.service.clear_single_workflow(field_name='supervisors')
        self.assertEqual(len(pd_session['workflows']), 2)
        fields = [wf['field_name'] for wf in pd_session['workflows']]
        self.assertEqual(fields, ['authors', 'editors'])
        
        # Clear by index
        self.service.clear_single_workflow(index=0)
        self.assertEqual(len(pd_session['workflows']), 1)
        self.assertEqual(pd_session['workflows'][0]['field_name'], 'editors')
        
        # Clear current (default)
        pd_session['current_index'] = 0
        self.service.clear_single_workflow()
        self.assertEqual(len(pd_session['workflows']), 0)
        
        # Test clearing non-existent workflow
        self.service.clear_single_workflow(field_name='not_found')
        # Should not crash
    
    def test_clear_workflow(self):
        """Test clear_workflow removes all workflow data."""
        # Set up some session data
        self.service.start_workflow('authors', ['John Smith'], {}, '/test')
        self.request.session['updated_form_data'] = {'test': 'data'}
        self.request.session['workflow_updated_fields'] = ['test']
        self.request.session['person_workflow'] = 'legacy'
        
        # Clear
        self.service.clear_workflow()
        
        # Check session cleared
        pd_session = self.request.session['person_disambiguation']
        self.assertEqual(pd_session['workflows'], [])
        self.assertEqual(pd_session['current_index'], 0)
        self.assertEqual(pd_session['all_updated_form_data'], {})
        
        # Legacy keys should be gone
        self.assertNotIn('updated_form_data', self.request.session)
        self.assertNotIn('workflow_updated_fields', self.request.session)
        self.assertNotIn('person_workflow', self.request.session)


class PersonDisambiguationServiceIntegrationTestCase(TestCase):
    """Integration tests for PersonDisambiguationService."""
    
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
    
    def test_workflow_complete_cycle(self):
        """Test a complete disambiguation workflow cycle."""
        # Create a request
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.test_user
        request.session = {}
        
        # Create service
        service = PersonDisambiguationService(request)
        
        # Start workflow
        original_data = {'authors': ['John Smith', 'Unknown Person', 'Jane Doe']}
        service.start_workflow('authors', ['John Smith', 'Unknown Person'], original_data, '/test')
        
        # Verify current person
        self.assertEqual(service.get_current_person(), 'John Smith')
        
        # Get matches for current person
        matches = service.get_matches_for_current_person()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)
        
        # Resolve current person
        service.resolve_current_person(str(self.person1.pk))
        
        # Verify next person
        self.assertEqual(service.get_current_person(), 'Unknown Person')
        
        # Resolve next person
        service.resolve_current_person('CREATE:New Person')
        
        # Workflow should be complete
        self.assertTrue(service.is_workflow_complete())
        
        # Finalize workflow
        updated_data, redirect_url = service.finalize_workflow()
        
        # Check results
        self.assertEqual(updated_data['authors'], [
            str(self.person1.pk),
            'CREATE:New Person',
            'Jane Doe'
        ])
        
        # Session should be updated
        self.assertEqual(
            request.session['updated_form_data']['authors'], 
            [str(self.person1.pk), 'CREATE:New Person', 'Jane Doe']
        )
        self.assertEqual(
            request.session['workflow_updated_fields'], 
            ['authors']
        )
