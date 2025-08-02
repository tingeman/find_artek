"""
Enhanced forms with multi-step person disambiguation workflow.
This integrates the workflow system with existing forms.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import QuerySet
from .forms import AddEditReportForm, AddEditReportFinalSaveForm, PersonWorkflowMixin
from .person_workflow import extract_person_names
import ast


class WorkflowAddEditReportForm(PersonWorkflowMixin, AddEditReportForm):
    """
    Enhanced AddEditReportForm with person disambiguation workflow.
    
    This form will automatically redirect to the disambiguation workflow
    when person names need to be resolved.
    """
    
    def clean_authors(self):
        """Enhanced clean_authors with workflow trigger only for string data"""
        # Call parent method first to get the data
        authors_data = super().clean_authors()
        
        # Only trigger workflow if we have string data (not QuerySet)
        # QuerySet means data is already resolved from previous workflow
        if isinstance(authors_data, QuerySet):
            print(f"clean_authors: Already resolved QuerySet with {authors_data.count()} authors")
            return authors_data
        
        # If we have list of strings, trigger workflow
        if isinstance(authors_data, list) and any(isinstance(item, str) and not item.isnumeric() for item in authors_data):
            print(f"clean_authors: Found unresolved string data, triggering workflow: {authors_data}")
            self._workflow_redirect = self.start_person_workflow(
                'authors', authors_data
            )
            # Return the original data - workflow will handle resolution
            return authors_data
        
        print(f"clean_authors: No workflow needed, returning: {authors_data}")
        return authors_data
    
    def clean_supervisors(self):
        """Enhanced clean_supervisors with workflow trigger only for string data"""
        # Call parent method first to get the data
        supervisors_data = super().clean_supervisors()
        
        # Only trigger workflow if we have string data (not QuerySet)
        # QuerySet means data is already resolved from previous workflow
        if isinstance(supervisors_data, QuerySet):
            print(f"clean_supervisors: Already resolved QuerySet with {supervisors_data.count()} supervisors")
            return supervisors_data
        
        # If we have list of strings, trigger workflow
        if isinstance(supervisors_data, list) and any(isinstance(item, str) and not item.isnumeric() for item in supervisors_data):
            print(f"clean_supervisors: Found unresolved string data, triggering workflow: {supervisors_data}")
            self._workflow_redirect = self.start_person_workflow(
                'supervisors', supervisors_data
            )
            # Return the original data - workflow will handle resolution
            return supervisors_data
        
        print(f"clean_supervisors: No workflow needed, returning: {supervisors_data}")
        return supervisors_data
    
    def has_workflow_redirect(self):
        """Check if form needs to redirect to workflow"""
        return hasattr(self, '_workflow_redirect')
    
    def get_workflow_redirect(self):
        """Get the workflow redirect response"""
        return getattr(self, '_workflow_redirect', None)


class WorkflowAddEditReportFinalSaveForm(PersonWorkflowMixin, AddEditReportFinalSaveForm):
    """
    Enhanced final save form with workflow support.
    This handles the final save after all persons are resolved.
    """
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean_authors(self):
        """Enhanced clean_authors with automatic person creation"""
        print(f"WorkflowAddEditReportFinalSaveForm:clean_authors: {self.cleaned_data.get('authors')}")
        
        # Call parent method first
        authors_data = super().clean_authors()
        
        # If authors_data contains string names (not just PKs), process them
        if isinstance(authors_data, list) and any(not str(item).isnumeric() for item in authors_data):
            processed_authors = []
            
            for item in authors_data:
                if str(item).isnumeric():
                    # It's a PK, keep as is
                    processed_authors.append(int(item))
                else:
                    # It's a name string, check for tags or create person
                    processed_name = self._process_person_name(str(item))
                    if processed_name:
                        processed_authors.append(processed_name)
            
            # Convert back to queryset if we have PKs
            if processed_authors and all(isinstance(pk, int) for pk in processed_authors):
                from .forms import create_ordered_queryset
                from .models import Person
                return create_ordered_queryset(Person, processed_authors)
        
        return authors_data
    
    def clean_supervisors(self):
        """Enhanced clean_supervisors with automatic person creation"""
        print(f"WorkflowAddEditReportFinalSaveForm:clean_supervisors: {self.cleaned_data.get('supervisors')}")
        
        # Call parent method first
        supervisors_data = super().clean_supervisors()
        
        # If supervisors_data contains string names (not just PKs), process them
        if isinstance(supervisors_data, list) and any(not str(item).isnumeric() for item in supervisors_data):
            processed_supervisors = []
            
            for item in supervisors_data:
                if str(item).isnumeric():
                    # It's a PK, keep as is
                    processed_supervisors.append(int(item))
                else:
                    # It's a name string, check for tags or create person
                    processed_name = self._process_person_name(str(item))
                    if processed_name:
                        processed_supervisors.append(processed_name)
            
            # Convert back to queryset if we have PKs
            if processed_supervisors and all(isinstance(pk, int) for pk in processed_supervisors):
                from .forms import create_ordered_queryset
                from .models import Person
                return create_ordered_queryset(Person, processed_supervisors)
        
        return supervisors_data
    
    def _process_person_name(self, name_string):
        """Process a person name string and return person PK"""
        from .person_workflow import get_tag, remove_tags
        from .models import Person
        
        # Check if name has ID tag
        person_id = get_tag(name_string, 'id')
        
        if person_id == 0:
            # Create new person
            clean_name = remove_tags(name_string)
            try:
                person = Person.objects.create(
                    name=clean_name,
                    created_by=self.request.user if self.request else None,
                    modified_by=self.request.user if self.request else None
                )
                return person.pk
            except Exception as e:
                print(f"Error creating person {clean_name}: {e}")
                return None
        elif person_id and person_id != 'ldap':
            # Existing person ID
            try:
                person = Person.objects.get(id=person_id)
                return person.pk
            except Person.DoesNotExist:
                print(f"Person with ID {person_id} not found")
                return None
        
        # Fallback - try to find existing person or create new one
        clean_name = remove_tags(name_string)
        try:
            person = Person.objects.get(name__iexact=clean_name)
            return person.pk
        except Person.DoesNotExist:
            # Create new person
            try:
                person = Person.objects.create(
                    name=clean_name,
                    created_by=self.request.user if self.request else None,
                    modified_by=self.request.user if self.request else None
                )
                return person.pk
            except Exception as e:
                print(f"Error creating person {clean_name}: {e}")
                return None
        except Person.MultipleObjectsReturned:
            # Multiple matches - return first one
            person = Person.objects.filter(name__iexact=clean_name).first()
            return person.pk if person else None
