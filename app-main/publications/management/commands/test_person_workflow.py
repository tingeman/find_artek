"""
Test the multi-step person disambiguation workflow.

This test script demonstrates how the workflow handles various person name scenarios.
Run with: python manage.py test_person_workflow
"""

from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import User
from publications.models import Person, Publication
from publications.enhanced_forms import WorkflowAddEditReportForm
from publications.person_workflow import PersonWorkflowSession, get_person_matches


class Command(BaseCommand):
    help = 'Test the person disambiguation workflow'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test persons and data',
        )

    def handle(self, *args, **options):
        if options['create_test_data']:
            self.create_test_data()
        
        self.test_person_matching()
        self.test_workflow_session()
        self.test_form_integration()

    def create_test_data(self):
        """Create test persons for testing"""
        self.stdout.write('Creating test data...')
        
        # Create test persons with similar names
        test_persons = [
            'John Smith',
            'John A. Smith', 
            'John Andrew Smith',
            'Jane Doe',
            'Jane M. Doe',
            'Anders Hansen',
            'Anders P. Hansen'
        ]
        
        for name in test_persons:
            person, created = Person.objects.get_or_create(
                name=name,
                defaults={'created_by': None, 'modified_by': None}
            )
            if created:
                self.stdout.write(f'  Created: {person.name}')
            else:
                self.stdout.write(f'  Exists: {person.name}')

    def test_person_matching(self):
        """Test person matching functionality"""
        self.stdout.write('\n=== Testing Person Matching ===')
        
        test_cases = [
            'John Smith',           # Should find exact matches
            'john smith',           # Case insensitive
            'Jane Doe',            # Should find exact matches  
            'John A Smith',        # Should find relaxed matches
            'Unknown Person',      # Should find no matches
            'Anders Hansen'        # Should find exact matches
        ]
        
        for test_name in test_cases:
            matches = get_person_matches(test_name)
            exact_count = len(matches['exact'])
            relaxed_count = len(matches['relaxed'])
            
            self.stdout.write(f'  "{test_name}":')
            self.stdout.write(f'    Exact matches: {exact_count}')
            if exact_count > 0:
                for person in matches['exact']:
                    self.stdout.write(f'      - {person.name}')
            self.stdout.write(f'    Relaxed matches: {relaxed_count}')
            if relaxed_count > 0:
                for person in matches['relaxed']:
                    self.stdout.write(f'      - {person.name}')

    def test_workflow_session(self):
        """Test workflow session management"""
        self.stdout.write('\n=== Testing Workflow Session ===')
        
        # Create a mock request with a real session
        factory = RequestFactory()
        request = factory.post('/')
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()

        workflow = PersonWorkflowSession(request)

        # Test starting workflow
        test_persons = ['John Smith', 'Unknown Author', 'Jane Doe']
        test_form_data = {'title': 'Test Report', 'authors': test_persons}

        workflow.start_workflow('authors', test_persons, test_form_data)

        self.stdout.write(f'  Started workflow for field: {workflow.get_field_name()}')
        self.stdout.write(f'  Total persons to process: {len(test_persons)}')

        # Test workflow steps
        step = 0
        while not workflow.is_complete():
            step += 1
            current_person = workflow.get_current_person()
            self.stdout.write(f'  Step {step}: Processing "{current_person}"')

            # Simulate user choice (auto-resolve for test)
            if 'Smith' in current_person:
                # Simulate selecting existing person
                workflow.resolve_current_person(f'{current_person} [id:1]')
                self.stdout.write(f'    -> Resolved to existing person')
            else:
                # Simulate creating new person
                workflow.resolve_current_person(f'{current_person} [id:0]')
                self.stdout.write(f'    -> Marked for creation')

        self.stdout.write(f'  Workflow completed!')
        self.stdout.write(f'  Resolved persons: {workflow.get_resolved_persons()}')

    def test_form_integration(self):
        """Test form integration with workflow"""
        self.stdout.write('\n=== Testing Form Integration ===')
        
        # Create a mock request with a real session
        factory = RequestFactory()
        request = factory.post('/', {
            'title': 'Test Publication',
            'authors': ['John Smith', 'New Author Name'],
            'year': '2024',
            'type': 'report'
        })
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()
        request.user = User.objects.first() or self.create_test_user()
        
        form = WorkflowAddEditReportForm(request.POST, request=request)
        
        self.stdout.write(f'  Form created with workflow support')
        self.stdout.write(f'  Form data: {dict(request.POST)}')
        
        if form.is_valid():
            self.stdout.write(f'  Form is valid')
            if form.has_workflow_redirect():
                self.stdout.write(f'  -> Workflow redirect needed')
            else:
                self.stdout.write(f'  -> No workflow needed, ready to save')
        else:
            self.stdout.write(f'  Form has errors: {form.errors}')

    def create_test_user(self):
        """Create a test user if none exists"""
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        if created:
            user.set_password('testpass')
            user.save()
        return user
