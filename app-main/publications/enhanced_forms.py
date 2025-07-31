"""
Enhanced forms with multi-step person disambiguation workflow.
This integrates the workflow system with existing forms.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import QuerySet
from .forms import AddEditReportForm, AddEditReportFinalSaveForm
from .workflow_forms import PersonWorkflowMixin
from .person_workflow import extract_person_names
import ast


class WorkflowAddEditReportForm(PersonWorkflowMixin, AddEditReportForm):
    """
    Enhanced AddEditReportForm with person disambiguation workflow.
    
    This form will automatically redirect to the disambiguation workflow
    when person names need to be resolved.
    """
    
    def __init__(self, *args, **kwargs):
        # Extract request object before passing to parent
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Enhanced clean method that triggers workflow if needed"""
        cleaned_data = super().clean()
        
        # Check if we need to start person disambiguation workflow
        person_fields = ['authors', 'supervisors']
        
        for field_name in person_fields:
            if field_name in cleaned_data:
                field_data = cleaned_data[field_name]
                
                # Skip if already a QuerySet (persons are resolved)
                if isinstance(field_data, QuerySet):
                    continue
                
                # Convert the field data to the format expected by extract_person_names
                if field_data:
                    # Handle the complex data formats from HeavySelect2TagWidget
                    if isinstance(field_data, list):
                        names_to_check = [str(item) for item in field_data]
                    elif isinstance(field_data, str):
                        try:
                            parsed_data = ast.literal_eval(field_data)
                            names_to_check = [str(item) for item in parsed_data]
                        except (ValueError, SyntaxError):
                            names_to_check = [field_data]
                    else:
                        names_to_check = [str(field_data)]
                    
                    # Filter out numeric IDs (already resolved)
                    names_needing_resolution = []
                    for name in names_to_check:
                        if not str(name).isnumeric():
                            names_needing_resolution.append(name)
                    
                    if names_needing_resolution:
                        # Start workflow for this field
                        workflow_result = self.start_person_workflow(
                            field_name, names_needing_resolution
                        )
                        # This will be a redirect response
                        # We need to handle this in the view, not here
                        # For now, we'll store it in the form for the view to handle
                        self._workflow_redirect = workflow_result
                        break
        
        return cleaned_data
    
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
