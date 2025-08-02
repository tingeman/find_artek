"""
Enhanced form methods for handling person disambiguation workflow.
"""
from django.shortcuts import redirect
from django.contrib import messages
from publications.person_workflow import PersonWorkflowSession, extract_person_names


class PersonWorkflowMixin:
    """Mixin for forms that need person disambiguation workflow"""
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Enhanced clean method that handles person workflow"""
        cleaned_data = super().clean()
        
        # Check if we have updated form data from completed workflow
        if self.request and 'updated_form_data' in self.request.session:
            updated_data = self.request.session.pop('updated_form_data')
            
            # Merge updated data into cleaned_data
            for field_name, value in updated_data.items():
                if field_name in self.fields:
                    cleaned_data[field_name] = value
        
        return cleaned_data
    
    def check_person_disambiguation_needed(self, field_names):
        """
        Check if person disambiguation is needed for specified fields.
        Returns the first field that needs disambiguation, or None if all are resolved.
        """
        if not self.request:
            return None
        
        for field_name in field_names:
            if field_name in self.cleaned_data:
                field_data = self.cleaned_data[field_name]
                
                # Convert to list if it's a single value
                if isinstance(field_data, str):
                    field_data = [field_data]
                elif hasattr(field_data, '__iter__') and not isinstance(field_data, str):
                    field_data = list(field_data)
                else:
                    continue
                
                # Check if any names need disambiguation
                names_needing_resolution = extract_person_names(
                    MockFormData(field_data), field_name
                )
                
                if names_needing_resolution:
                    return field_name, names_needing_resolution
        
        return None
    
    def start_person_workflow(self, field_name, person_names):
        """Start person disambiguation workflow"""
        if not self.request:
            raise ValueError("Request object required for workflow")
        
        workflow = PersonWorkflowSession(self.request)
        
        # Convert form data to dict format for storage
        form_data_dict = {}
        for field_name_key, field in self.fields.items():
            if field_name_key in self.cleaned_data:
                value = self.cleaned_data[field_name_key]
                if hasattr(value, '__iter__') and not isinstance(value, str):
                    form_data_dict[field_name_key] = list(value)
                else:
                    form_data_dict[field_name_key] = value
        
        workflow.start_workflow(field_name, person_names, form_data_dict)
        
        return redirect('publications:disambiguate_person_step')


class MockFormData:
    """Mock form data object for extract_person_names function"""
    
    def __init__(self, data_list):
        self.data = data_list
    
    def getlist(self, field_name):
        return self.data
    
    def get(self, field_name, default=None):
        return self.data if self.data else default


def clean_authors_with_workflow(form_instance):
    """Enhanced clean_authors method with workflow support"""
    authors = form_instance.cleaned_data.get('authors', [])
    
    # Check if disambiguation workflow is needed
    workflow_result = form_instance.check_person_disambiguation_needed(['authors'])
    
    if workflow_result:
        field_name, person_names = workflow_result
        # Start workflow and return redirect response
        return form_instance.start_person_workflow(field_name, person_names)
    
    return authors


def clean_supervisors_with_workflow(form_instance):
    """Enhanced clean_supervisors method with workflow support"""
    supervisors = form_instance.cleaned_data.get('supervisors', [])
    
    # Check if disambiguation workflow is needed
    workflow_result = form_instance.check_person_disambiguation_needed(['supervisors'])
    
    if workflow_result:
        field_name, person_names = workflow_result
        # Start workflow and return redirect response
        return form_instance.start_person_workflow(field_name, person_names)
    
    return supervisors


def clean_editors_with_workflow(form_instance):
    """Enhanced clean_editors method with workflow support"""
    editors = form_instance.cleaned_data.get('editors', [])
    
    # Check if disambiguation workflow is needed
    workflow_result = form_instance.check_person_disambiguation_needed(['editors'])
    
    if workflow_result:
        field_name, person_names = workflow_result
        # Start workflow and return redirect response
        return form_instance.start_person_workflow(field_name, person_names)
    
    return editors
