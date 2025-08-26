import unittest
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.urls import reverse
from publications.models import Person
from publications.forms.publication_new_forms import (
    DisambiguationWorkflowAddEditReportForm, 
    DisambiguationWorkflowAddEditReportFinalSaveForm
)
from publications.workflows.person_disambiguation import (
    PersonDisambiguationService, 
    DisambiguatePersonStepView,
    CompletePersonWorkflowView
)


class MigrationValidationTests(TestCase):
    """Test cases to validate the new person disambiguation implementation"""
    
    def setUp(self):
        """Set up test environment"""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpassword'
        )
        # Create test persons
        self.person1 = Person.objects.create(
            first='John', last='Doe', created_by=self.user, modified_by=self.user
        )
        self.person2 = Person.objects.create(
            first='Jane', last='Smith', created_by=self.user, modified_by=self.user
        )
    
    def add_session_to_request(self, request):
        """Helper method to add session to a request"""
        middleware = SessionMiddleware(lambda request: None)
        middleware.process_request(request)
        request.session.save()
        
    def test_disambiguation_workflow_form_initialization(self):
        """Test that the new form initializes correctly"""
        request = self.factory.get('/')
        request.user = self.user
        self.add_session_to_request(request)
        
        form = DisambiguationWorkflowAddEditReportForm(request=request)
        self.assertIsNotNone(form.person_service)
        self.assertTrue(hasattr(form, 'has_workflow_redirect'))
        self.assertTrue(hasattr(form, 'get_workflow_redirect'))
    
    def test_disambiguation_workflow_redirect(self):
        """Test that the form triggers workflow redirect when needed"""
        # Create POST data with ambiguous person names
        post_data = {
            'title': 'Test Report',
            'type': 'report',
            'year': '2023',
            'authors': 'John Smith; Jane Doe',  # Ambiguous names
            'abstract': 'Test abstract'
        }
        
        request = self.factory.post('/', data=post_data)
        request.user = self.user
        self.add_session_to_request(request)
        
        form = DisambiguationWorkflowAddEditReportForm(request.POST, request=request)
        if form.is_valid():
            self.assertTrue(form.has_workflow_redirect())
            redirect_response = form.get_workflow_redirect()
            self.assertIsNotNone(redirect_response)
            self.assertEqual(redirect_response.url, reverse('publications:disambiguate_person_step'))
    
    def test_disambiguation_workflow_completion(self):
        """Test the disambiguation workflow completes successfully"""
        # Set up request
        request = self.factory.get('/')
        request.user = self.user
        self.add_session_to_request(request)
        
        # Initialize the service and start a workflow
        service = PersonDisambiguationService(request)
        service.start_workflow('authors', ['John Smith'], {'authors': ['John Smith']}, '/test/')
        
        # Resolve the person
        service.resolve_current_person(str(self.person1.pk))
        
        # Verify workflow is complete
        self.assertTrue(service.is_workflow_complete())
        
        # Complete the workflow
        updated_data, redirect_url = service.finalize_workflow()
        
        # Verify data is updated correctly
        self.assertIsNotNone(updated_data)
        self.assertEqual(updated_data.get('authors', [])[0], str(self.person1.pk))
    
    def test_disambiguate_step_view(self):
        """Test the DisambiguatePersonStepView class"""
        # Set up request
        request = self.factory.get(reverse('publications:disambiguate_person_step'))
        request.user = self.user
        self.add_session_to_request(request)
        
        # Initialize service and start workflow
        service = PersonDisambiguationService(request)
        service.start_workflow('authors', ['John Smith'], {'authors': ['John Smith']}, '/test/')
        
        # Call the view
        response = DisambiguatePersonStepView.as_view()(request)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
    
    def test_complete_workflow_view(self):
        """Test the CompletePersonWorkflowView class"""
        # Set up request
        request = self.factory.get(reverse('publications:complete_person_workflow'))
        request.user = self.user
        self.add_session_to_request(request)
        
        # Initialize service and start workflow
        service = PersonDisambiguationService(request)
        service.start_workflow('authors', ['John Smith'], {'authors': ['John Smith']}, '/test/')
        
        # Resolve the person
        service.resolve_current_person(str(self.person1.pk))
        
        # Call the view
        response = CompletePersonWorkflowView.as_view()(request)
        
        # Verify response is a redirect
        self.assertEqual(response.status_code, 302)


if __name__ == '__main__':
    unittest.main()
