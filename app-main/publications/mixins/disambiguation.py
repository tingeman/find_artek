
import logging
from django.shortcuts import render, redirect, reverse
from django.views.generic.base import ContextMixin


# Import utility functions that we'll need
from publications import models
from publications.utils_models import create_ordered_queryset
from publications.services.disambiguation import PersonDisambiguationService
from publications.utils.person_matching import MockFormData

logger = logging.getLogger(__name__)





class PersonDisambiguationFormMixin:
    """
    Mixin for forms that need person disambiguation.
    
    This mixin provides methods for handling person disambiguation workflow
    and integrates with the PersonDisambiguationService. It supports both single
    and multiple field disambiguation.
    
    Usage examples:
    ```
    def clean(self):
        cleaned_data = super().clean()
        # Your form validation logic here
        
        # Example with a single field
        workflow_redirect = self.start_disambiguation_workflow('authors')
        if workflow_redirect:
            self._workflow_redirect = workflow_redirect
            return cleaned_data
        
        # Example with multiple fields
        workflow_redirect = self.start_disambiguation_workflow(['authors', 'supervisors'])
        if workflow_redirect:
            self._workflow_redirect = workflow_redirect
        
        return cleaned_data
    ```
    
    In your form_valid method:
    ```
    def form_valid(self, form):
        if form.has_workflow_redirect():
            return form.get_workflow_redirect()
        # Continue with normal form processing...
    ```
    """
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)    # This calls the parent class's __init__ method
        
        # Initialize service if request is available
        self.person_service = None
        if self.request:
            self.person_service = PersonDisambiguationService(self.request)
            # Note: This just initializes the service
            # The start_workflow method must be called to initiate disambiguation

    # TODO: Explain how the mixin class works. How and when are the methods called?
    # TODO: Add more explanation to docstrings


    def is_edit_mode(self):
        """
        Check if the form is in edit mode (has an instance with a primary key).
        This allows the mixin to detect if we're editing an existing object or creating a new one.
        """
        editing = hasattr(self, 'instance') and self.instance and self.instance.pk is not None
        logger.debug(f'PersonDisambiguationMixin.is_edit_mode: editing={editing}')
        return editing

    def dispatch(self, request, *args, **kwargs):
        """
        Hook into dispatch to process any finalized workflows before rendering the form.
        """
        # Process any finalized workflows if this is a GET request
        if request.method == 'GET' and hasattr(self, 'person_service'):
            self.person_service.process_finalized_workflows()

        return super().dispatch(request, *args, **kwargs)


    def clean(self):
        """Process any finalized workflow data from session"""
        logger.debug('PersonDisambiguationMixin.clean: called')
        cleaned_data = super().clean()    # This calls the clean method of the parent class
        logger.debug(f'PersonDisambiguationMixin.clean: initial cleaned_data={cleaned_data}')
        # Skip if no request or service
        if not self.request or not self.person_service:
            logger.debug('PersonDisambiguationMixin.clean: no request or person_service, returning cleaned_data')
            return cleaned_data
        # Check if we have updated form data from finalized workflow
        if 'updated_form_data' in self.request.session:
            updated_data = self.request.session.pop('updated_form_data')
            updated_fields = self.request.session.get('workflow_updated_fields', [])
            logger.debug(f'PersonDisambiguationMixin.clean: found updated_form_data={updated_data}, updated_fields={updated_fields}')
            # Handle multiple fields (authors, supervisors, etc.)
            for field_name in updated_fields:
                if field_name in self.fields and field_name in updated_data:
                    logger.debug(f'PersonDisambiguationMixin.clean: processing field {field_name} with values {updated_data[field_name]}')
                    self._process_workflow_result(cleaned_data, field_name, updated_data[field_name])
                    logger.debug(f'PersonDisambiguationMixin.clean: after _process_workflow_result, cleaned_data[{field_name}]={cleaned_data.get(field_name)}')
            # Clean up the session
            if 'workflow_updated_fields' in self.request.session:
                del self.request.session['workflow_updated_fields']
                self.request.session.modified = True
        logger.debug(f'PersonDisambiguationMixin.clean: returning cleaned_data={cleaned_data}')
        return cleaned_data
    
    def _process_workflow_result(self, cleaned_data, field_name, resolved_values):
        """
        Update the form's cleaned_data for a person field with resolved person objects.

        This method processes the list of resolved values returned from the person disambiguation workflow
        and updates the form's cleaned_data for the specified field. It handles the following cases for each value:
        - If the value is a string starting with 'CREATE:', a new Person object is created with the given name.
        - If the value is a string representing an existing Person's primary key (ID), it is used directly.
        - If the value is a Person object (with a pk attribute), its primary key is used.

        The resulting list of person IDs is used to create an ordered queryset, which is assigned to cleaned_data[field_name].
        This ensures that the form field contains a proper queryset of Person objects for further processing or saving.

        Args:
            cleaned_data (dict): The form's cleaned_data dictionary to update in-place.
            field_name (str): The name of the person field being processed.
            resolved_values (list): List of resolved values, which may include:
                - Strings of the form 'CREATE:Name' (to create a new Person)
                - Strings representing existing Person IDs
                - Person objects (with a pk attribute)

        Side Effects:
            - May create new Person objects in the database if 'CREATE:' values are present.
            - Modifies cleaned_data in-place for the given field.
        """

        logger.debug(f'_process_workflow_result: field_name={field_name}, resolved_values={resolved_values}')
        person_ids = []
        for value in resolved_values:
            logger.debug(f'_process_workflow_result: processing value={value}')
            if isinstance(value, str):
                if value.startswith('CREATE:'):
                    # Create new person
                    person_name = value[7:]
                    logger.debug(f'_process_workflow_result: Creating new Person with name={person_name}')
                    person = models.Person(created_by=self.request.user, modified_by=self.request.user)
                    person.set_names(person_name)
                    person.save()
                    logger.debug(f'_process_workflow_result: Created Person id={person.pk}')
                    person_ids.append(person.pk)
                elif value.isdigit():
                    logger.debug(f'_process_workflow_result: Using existing Person id={value}')
                    # Existing person ID
                    person_ids.append(int(value))
            elif hasattr(value, 'pk'):
                logger.debug(f'_process_workflow_result: Using Person object with id={value.pk}')
                # Person object
                person_ids.append(value.pk)

        # Create queryset if we have person IDs
        if person_ids:
            logger.debug(f'_process_workflow_result: Creating ordered queryset for person_ids={person_ids}')
            cleaned_data[field_name] = create_ordered_queryset(models.Person, person_ids)
    
    def check_disambiguation_needed(self, field_name):
        """
        Check if person disambiguation is needed for a field.
        
        Args:
            field_name: Name of the field to check
            
        Returns:
            True if disambiguation is needed, False otherwise
        """
        if not self.request or not self.person_service:
            logger.debug(f"PersonDisambiguationFormMixin:check_disambiguation_needed({field_name}): No request or person_service")
            return False
            
        # Get field data from cleaned_data
        field_data = self.cleaned_data.get(field_name, [])

        logger.debug(f"PersonDisambiguationFormMixin:check_disambiguation_needed({field_name}): field_data={field_data} (type={type(field_data)})")

        # Skip if empty or already a QuerySet
        from django.db.models import QuerySet
        if not field_data or isinstance(field_data, QuerySet):
            logger.debug(f"PersonDisambiguationFormMixin:check_disambiguation_needed({field_name}): Empty or QuerySet - no disambiguation needed")
            return False
            
        # Check if any names need disambiguation
        names_needing_resolution = self.person_service.extract_persons_needing_disambiguation(
            MockFormData(field_data), field_name
        )

        logger.debug(f"PersonDisambiguationFormMixin:check_disambiguation_needed({field_name}): names_needing_resolution={names_needing_resolution}")
        return bool(names_needing_resolution)
        
    def check_any_disambiguation_needed(self, field_names):
        """
        Check if any of the given fields need person disambiguation.
        
        This is useful when your form has multiple person fields and you want
        to check if any of them need disambiguation.
        
        Args:
            field_names: List of field names to check
            
        Returns:
            True if any field needs disambiguation, False otherwise
        """
        if not self.request or not self.person_service:
            return False
            
        # Check each field
        for field_name in field_names:
            if self.check_disambiguation_needed(field_name):
                return True
                
        return False
    
    def start_disambiguation_workflow(self, field_names):
        """
        Start person disambiguation workflow for one or more fields.
        
        This method accepts either a single field name as a string or
        multiple field names as a list. It checks each field and starts
        disambiguation workflows for any fields that need it.
        
        Args:
            field_names: Either a single field name (str) or a list of field names
            
        Returns:
            Redirect response to disambiguation step or None if no workflow needed
        
        Examples:
            # For a single field
            workflow_redirect = self.start_disambiguation_workflow('authors')
            
            # For multiple fields
            workflow_redirect = self.start_disambiguation_workflow(['authors', 'supervisors'])
        """
        print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: Called with field_names={field_names}")
        
        if not self.request or not self.person_service:
            print("DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: No request or person_service available")
            return None
        
        # Handle both single field name (str) and list of field names
        if isinstance(field_names, str):
            print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: Converting single field name to list: [{field_names}]")
            field_names = [field_names]
        
        print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: cleaned_data keys={list(self.cleaned_data.keys())}")
        
        # Track if any workflows were started
        any_workflows_started = False
        
        # Check each field and start workflows as needed
        for field_name in field_names:
            field_data = self.cleaned_data.get(field_name, [])
            
            print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: {field_name} data={field_data} (type={type(field_data)})")
            logger.debug(f"PersonDisambiguationFormMixin:PersonDisambiguationFormMixin:start_disambiguation_workflow: field_name={field_name}, field_data={field_data} (type={type(field_data)})")

            # Skip empty fields or fields that are already QuerySets
            from django.db.models import QuerySet
            if not field_data or isinstance(field_data, QuerySet):
                print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: {field_name} is empty or QuerySet, skipping")
                continue
            
            # Extract names needing disambiguation
            print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: Creating MockFormData for {field_name} with data={field_data}")
            mock_form_data = MockFormData(field_data)
            print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: Calling extract_persons_needing_disambiguation for {field_name}")
            
            names_needing_resolution = self.person_service.extract_persons_needing_disambiguation(
                mock_form_data, field_name
            )

            print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: {field_name} names_needing_resolution={names_needing_resolution}")
            logger.debug(f"PersonDisambiguationFormMixin:PersonDisambiguationFormMixin:start_disambiguation_workflow: names_needing_resolution for {field_name}={names_needing_resolution}")

            if names_needing_resolution:
                # Start workflow for this field
                print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: Starting workflow for {field_name} with names={names_needing_resolution}")
                original_form_data = dict(self.request.POST)
                
                # Check if original_form_data is populated correctly
                print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: original_form_data keys={list(original_form_data.keys())}")
                print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: original_form_data[{field_name}]={original_form_data.get(field_name, 'NOT FOUND')}")
                
                if self.is_edit_mode():
                    review_url = reverse('publications:edit_report_review', kwargs={'pk': self.instance.pk})
                else:
                    review_url = reverse('publications:add_report_review')

                # TODO: review_url should be the same url for all fields that are submitted as workflows.

                self.person_service.start_workflow(
                    field_name,
                    names_needing_resolution,
                    original_form_data,
                    self.request.path,
                    review_url=review_url
                )
                any_workflows_started = True
                print(f"DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: Workflow started for {field_name}")
        
        # Redirect to disambiguation step if any workflows were started
        if any_workflows_started:
            print("DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: Workflow(s) started, returning redirect to disambiguate_person_step")
            logger.debug("PersonDisambiguationFormMixin:start_disambiguation_workflow: Workflows started, returning redirect")
            return redirect('publications:disambiguate_person_step')
        
        print("DEBUG PersonDisambiguationFormMixin:start_disambiguation_workflow: No workflows started, returning None")
        logger.debug("PersonDisambiguationFormMixin:start_disambiguation_workflow: No workflows started, returning None")
        return None
    
    def has_workflow_redirect(self):
        """
        Check if the form needs to redirect to a disambiguation workflow.
        
        This method should be called in the form's form_valid method to determine
        if normal form processing should continue or if the user should be redirected
        to the disambiguation workflow.
        
        Returns:
            True if the form needs to redirect to disambiguation, False otherwise
        
        Example usage:
        ```
        def form_valid(self, form):
            if form.has_workflow_redirect():
                return form.get_workflow_redirect()
            # Continue with normal form processing...
        ```
        """
        return hasattr(self, '_workflow_redirect') and self._workflow_redirect is not None
    
    def get_workflow_redirect(self):
        """
        Get the redirect response for the disambiguation workflow.
        
        This method should be called after has_workflow_redirect() returns True
        to get the actual redirect response.
        
        Returns:
            HttpResponseRedirect to the disambiguation workflow or None
        
        Example usage:
        ```
        def form_valid(self, form):
            if form.has_workflow_redirect():
                return form.get_workflow_redirect()
            # Continue with normal form processing...
        ```
        """
        return getattr(self, '_workflow_redirect', None)


class BasePersonDisambiguationViewMixin(ContextMixin):
    """Base mixin with common functionality for person disambiguation."""
    
    def get_disambiguation_service(self):
        """Get the disambiguation service instance."""
        from publications.services.disambiguation import PersonDisambiguationService
        return PersonDisambiguationService(self.request)


class PersonDisambiguationViewReaderMixin(BasePersonDisambiguationViewMixin):
    """
    Mixin that reads person disambiguation workflow state without processing.
    Use this for forms and views that need to access disambiguation data
    but should not create new persons.
    """
    
    def get(self, request, *args, **kwargs):
        """
        Get method just checks workflow state without processing finalized workflows.
        """
        logger.debug("PersonDisambiguationReaderMixin: GET - not processing workflows")
        return super().get(request, *args, **kwargs)
        
    def post(self, request, *args, **kwargs):
        """
        Post method just checks workflow state without processing finalized workflows.
        """
        logger.debug("PersonDisambiguationReaderMixin: POST - not processing workflows")
        return super().post(request, *args, **kwargs)

class PersonDisambiguationViewProcessorMixin(BasePersonDisambiguationViewMixin):
    """
    Mixin that processes person disambiguation workflows.
    This creates new persons from any finalized workflows.
    Use this only on the view that should trigger person creation (ReportReviewView.post).
    """
    
    def get(self, request, *args, **kwargs):
        """
        Get method does not process workflows, just reads state.
        """
        logger.debug("PersonDisambiguationProcessorMixin: GET - not processing workflows")
        return super().get(request, *args, **kwargs)
        
    def post(self, request, *args, **kwargs):
        """
        Post method processes finalized workflows, creating new persons.
        """
        logger.debug("PersonDisambiguationProcessorMixin: POST - processing finalized workflows")
        service = self.get_disambiguation_service()
        
        # This will create any new Person objects marked with CREATE:
        if service.process_finalized_workflows():
            logger.debug("PersonDisambiguationProcessorMixin: Created new persons from disambiguation workflow")
        else:
            logger.debug("PersonDisambiguationProcessorMixin: No person creation needed")
        
        # Continue with normal POST processing
        try:
            response = super().post(request, *args, **kwargs)
        except Exception as e:
            print(f"🔍 DEBUG: Error occurred in ReportFinalizeView:post - {e}")
            pass
        return None
