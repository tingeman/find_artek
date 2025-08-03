"""Form mixins for enhanced functionality."""

from django.shortcuts import redirect
from django.db.models import QuerySet
from django.forms import ValidationError
from publications.models import Person
from publications.forms.publication import AddEditReportForm, AddEditReportFinalSaveForm
from publications.workflows.person import extract_person_names, get_tag, remove_tags
from publications.utils import create_ordered_queryset
import json
import ast
import logging
logger = logging.getLogger(__name__)


class PersonWorkflowMixin:
    """Mixin for forms that need person disambiguation workflow"""
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Enhanced clean method that handles person workflow"""
        logger.debug("PersonWorkflowMixin.clean() called")
        logger.debug(f"Session keys: {list(self.request.session.keys()) if self.request else 'No request'}")
        logger.debug(f"Has updated_form_data in session: {'updated_form_data' in self.request.session if self.request else 'No request'}")
        
        # Clear workflow redirect FIRST if we have session data to process
        if self.request and 'updated_form_data' in self.request.session:
            if hasattr(self, '_workflow_redirect'):
                delattr(self, '_workflow_redirect')
                logger.debug("Cleared workflow redirect before processing session data")
        
        cleaned_data = super().clean()
        
        # Check if we have updated form data from completed workflow
        if self.request and 'updated_form_data' in self.request.session:
            updated_data = self.request.session.pop('updated_form_data')
            
            logger.debug(f"Restoring updated_form_data from workflow: {updated_data}")
            logger.debug(f"Session keys before workflow restoration: {list(self.request.session.keys())}")
            
            # Merge updated data into cleaned_data, converting tagged names to Person instances
            for field_name, value in updated_data.items():
                logger.debug(f"Processing field '{field_name}': {value} (type: {type(value)})")
                if field_name in self.fields:
                    # Special handling for person fields - convert IDs and CREATE markers to Person instances
                    if field_name in ['authors', 'supervisors'] and isinstance(value, list):
                        logger.debug(f"Processing person field '{field_name}' with list value: {value}")
                        
                        converted_persons = []
                        for item in value:
                            if isinstance(item, str):
                                # Check if it's a CREATE marker
                                if item.startswith('CREATE:'):
                                    person_name = item[7:]  # Remove 'CREATE:' prefix
                                    # Create new person
                                    try:
                                        person = Person(created_by=self.request.user, modified_by=self.request.user)
                                        person.set_names(person_name)
                                        person.save()
                                        converted_persons.append(person)
                                        logger.info(f"Created new person from CREATE marker: {person_name} -> {person}")
                                    except Exception as e:
                                        logger.error(f"Failed to create person from CREATE marker {person_name}: {e}")
                                        # Keep the original item for further processing
                                        converted_persons.append(item)
                                elif item.startswith('SKIP:'):
                                    # Keep the SKIP: prefix - this prevents workflow from triggering again
                                    converted_persons.append(item)
                                    logger.debug(f"Keeping skipped item with prefix: {item}")
                                elif item.isdigit():
                                    # It's a person ID
                                    try:
                                        person = Person.objects.get(id=int(item))
                                        converted_persons.append(person)
                                        logger.debug(f"Restored person from ID: {item} -> {person}")
                                    except Person.DoesNotExist:
                                        logger.warning(f"Person with ID {item} not found")
                                        # Keep the original item for further processing
                                        converted_persons.append(item)
                                else:
                                    # Some other string format - keep as string
                                    # This allows non-person data to pass through unchanged
                                    converted_persons.append(item)
                                    logger.debug(f"Keeping string item unchanged: {item}")
                            else:
                                # Already a Person instance or other type
                                converted_persons.append(item)
                        
                        # Convert to QuerySet if we have Person instances
                        if converted_persons and all(isinstance(p, Person) for p in converted_persons):
                            cleaned_data[field_name] = create_ordered_queryset(Person, [p.pk for p in converted_persons])
                            logger.debug(f"Converted {field_name} to QuerySet with {len(converted_persons)} persons")
                        else:
                            cleaned_data[field_name] = converted_persons
                            logger.debug(f"{field_name} still has unresolved data: {converted_persons}")
                    else:
                        # For all other fields, SKIP restoration - let Django handle them normally
                        # This prevents type conversion issues with fields like ModelChoiceField
                        logger.debug(f"Skipping non-person field {field_name} (value: {value}, type: {type(value)})")
                        pass
                        
            logger.debug(f"Final cleaned_data after workflow restoration: {cleaned_data}")
            
            # Clear any workflow redirect since we've processed the workflow data
            if hasattr(self, '_workflow_redirect'):
                delattr(self, '_workflow_redirect')
                logger.debug("Cleared workflow redirect after successful data restoration")
        
        return cleaned_data
    
    def clean_authors_with_workflow(self):
        """Enhanced clean_authors method with workflow support"""
        authors = self.cleaned_data.get('authors', [])
        
        # Check if disambiguation workflow is needed
        workflow_result = self.check_person_disambiguation_needed(['authors'])
        
        if workflow_result:
            field_name, person_names = workflow_result
            # Start workflow and return redirect response
            return self.start_person_workflow(field_name, person_names)
        
        return authors

    def clean_supervisors_with_workflow(self):
        """Enhanced clean_supervisors method with workflow support"""
        supervisors = self.cleaned_data.get('supervisors', [])
        
        # Check if disambiguation workflow is needed
        workflow_result = self.check_person_disambiguation_needed(['supervisors'])
        
        if workflow_result:
            field_name, person_names = workflow_result
            # Start workflow and return redirect response
            return self.start_person_workflow(field_name, person_names)
        
        return supervisors

    def clean_editors_with_workflow(self):
        """Enhanced clean_editors method with workflow support"""
        editors = self.cleaned_data.get('editors', [])
        
        # Check if disambiguation workflow is needed
        workflow_result = self.check_person_disambiguation_needed(['editors'])
        
        if workflow_result:
            field_name, person_names = workflow_result
            # Start workflow and return redirect response
            return self.start_person_workflow(field_name, person_names)
        
        return editors
    
    def check_person_disambiguation_needed(self, field_names):
        """
        Check if person disambiguation is needed for specified fields.
        Returns the first field that needs disambiguation, or None if all are resolved.
        """
        if not self.request:
            return None
        
        # Import here to avoid circular imports
        from publications.workflows.person import extract_person_names

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
                
                logger.debug(f"Raw field_data: {field_data}")
                
                # Process each item - simplified to handle the specific issue we've encountered
                processed_field_data = []
                for item in field_data:
                    # Normal case: add the item as-is if it's not a numeric ID
                    if isinstance(item, str) and item.isdigit():
                        # Numeric IDs don't need disambiguation
                        continue
                    else:
                        # Regular string or non-string - add to processed data
                        processed_field_data.append(item)
                
                logger.debug(f"Processed field_data: {processed_field_data}")
                
                # Nothing to disambiguate if empty
                if not processed_field_data:
                    logger.debug("No items to disambiguate, skipping")
                    continue
                
                logger.debug(f"Items needing disambiguation check: {processed_field_data}")
                
                # Check if any names need disambiguation
                names_needing_resolution = extract_person_names(
                    MockFormData(processed_field_data), field_name
                )
                
                logger.debug(f"Names needing resolution: {names_needing_resolution}")
                
                # No filtering needed - we've already handled this properly
                filtered_names = names_needing_resolution
                
                logger.debug(f"Names for disambiguation: {filtered_names}")
                
                if filtered_names:
                    return field_name, filtered_names
        
        return None
    
    def start_person_workflow(self, field_name, person_names):
        """Start person disambiguation workflow"""
        if not self.request:
            raise ValueError("Request object required for workflow")
        
        # Clear any existing workflow data to prevent interference
        if 'updated_form_data' in self.request.session:
            del self.request.session['updated_form_data']
            logger.debug("Cleared old workflow session data before starting new workflow")
        
        # Import here to avoid circular imports
        from publications.workflows.person import PersonWorkflowSession
        
        workflow = PersonWorkflowSession(self.request)
        
        # Store RAW POST data instead of cleaned data to avoid model instance serialization issues
        raw_form_data = dict(self.request.POST)
        
        # Convert QueryDict list values to simple values where appropriate
        simplified_form_data = {}
        for key, value_list in raw_form_data.items():
            if len(value_list) == 1:
                # Single value - store as string
                simplified_form_data[key] = value_list[0]
            else:
                # Multiple values - store as list
                simplified_form_data[key] = value_list
        
        logger.debug(f"Storing raw POST data for workflow: {simplified_form_data}")
        logger.debug(f"Starting workflow for field '{field_name}' with names: {person_names}")
        
        # Test JSON serialization to ensure it will work
        try:
            json.dumps(simplified_form_data)
            logger.debug("Raw POST data is JSON serializable")
        except (TypeError, ValueError) as e:
            logger.error(f"Raw POST data serialization failed: {e}")
            logger.error(f"Problematic data: {simplified_form_data}")
        
        workflow.start_workflow(field_name, person_names, simplified_form_data, self.request.path)
        
        return redirect('publications:disambiguate_person_step')


class MockFormData:
    """Mock form data object for extract_person_names function"""
    
    def __init__(self, data_list):
        self.data = data_list
    
    def getlist(self, field_name):
        return self.data
    
    def get(self, field_name, default=None):
        return self.data if self.data else default


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
            logger.debug(f"clean_authors: Already resolved QuerySet with {authors_data.count()} authors")
            return authors_data
        
        logger.debug(f"clean_authors: Processing authors_data: {authors_data}")
        
        # First, extract individual authors from the list (handling nested lists if necessary)
        processed_authors = []
        if isinstance(authors_data, list):
            for item in authors_data:
                # Handle string representation of list (our bug case)
                if isinstance(item, str) and item.startswith('[') and item.endswith(']'):
                    try:
                        parsed_items = ast.literal_eval(item)
                        if isinstance(parsed_items, list):
                            logger.debug(f"clean_authors: Parsed list from string: {parsed_items}")
                            processed_authors.extend(parsed_items)
                            continue
                    except (ValueError, SyntaxError) as e:
                        logger.warning(f"clean_authors: Failed to parse list string: {e}")
                        # Fall through to normal processing
                
                # Regular item - add as is
                processed_authors.append(item)
        else:
            # Not a list - keep as is
            processed_authors = authors_data
        
        logger.debug(f"clean_authors: Processed authors: {processed_authors}")
        
        # Replace the original data with processed data to ensure correct format
        if isinstance(authors_data, list) and processed_authors != authors_data:
            self.cleaned_data['authors'] = processed_authors
            authors_data = processed_authors
        
        # Now get workflow results if any names need disambiguation
        workflow_result = self.check_person_disambiguation_needed(['authors'])
        
        if workflow_result:
            field_name, names_needing_resolution = workflow_result
            if names_needing_resolution:
                logger.info(f"clean_authors: Found unresolved string data, triggering workflow for: {names_needing_resolution}")
                self._workflow_redirect = self.start_person_workflow(
                    'authors', names_needing_resolution
                )
                # Return the processed data - workflow will handle resolution
                return authors_data
        
        logger.debug(f"clean_authors: No workflow needed, returning: {authors_data}")
        return authors_data
    
    def clean_supervisors(self):
        """Enhanced clean_supervisors with workflow trigger only for string data"""
        # Call parent method first to get the data
        supervisors_data = super().clean_supervisors()
        
        # Only trigger workflow if we have string data (not QuerySet)
        # QuerySet means data is already resolved from previous workflow
        if isinstance(supervisors_data, QuerySet):
            logger.debug(f"clean_supervisors: Already resolved QuerySet with {supervisors_data.count()} supervisors")
            return supervisors_data
        
        # If we have list of strings, check for any that need disambiguation
        if isinstance(supervisors_data, list):
            # Get workflow results if any names need disambiguation
            workflow_result = self.check_person_disambiguation_needed(['supervisors'])
            
            if workflow_result:
                field_name, names_needing_resolution = workflow_result
                if names_needing_resolution:
                    logger.debug(f"clean_supervisors: Found unresolved string data, triggering workflow for: {names_needing_resolution}")
                    self._workflow_redirect = self.start_person_workflow(
                        'supervisors', names_needing_resolution
                    )
                    # Return the original data - workflow will handle resolution
                    return supervisors_data
            
            logger.debug(f"clean_supervisors: No names need disambiguation")
        
        logger.debug(f"clean_supervisors: No workflow needed, returning: {supervisors_data}")
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
        logger.debug(f"WorkflowAddEditReportFinalSaveForm:clean_authors: {self.cleaned_data.get('authors')}")
        
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
                return create_ordered_queryset(Person, processed_authors)
        
        return authors_data
    
    def clean_supervisors(self):
        """Enhanced clean_supervisors with automatic person creation"""
        logger.debug(f"WorkflowAddEditReportFinalSaveForm:clean_supervisors: {self.cleaned_data.get('supervisors')}")
        
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
                return create_ordered_queryset(Person, processed_supervisors)
        
        return supervisors_data
    
    def _process_person_name(self, name_string):
        """Process a person name string and return person PK"""
        
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
                logger.error(f"Error creating person {clean_name}: {e}")
                return None
        elif person_id and person_id != 'ldap':
            # Existing person ID
            try:
                person = Person.objects.get(id=person_id)
                return person.pk
            except Person.DoesNotExist:
                logger.warning(f"Person with ID {person_id} not found")
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
                logger.error(f"Error creating person {clean_name}: {e}")
                return None
        except Person.MultipleObjectsReturned:
            # Multiple matches - return first one
            person = Person.objects.filter(name__iexact=clean_name).first()
            return person.pk if person else None


def clean_authors_with_workflow(form_instance):
    """
    Standalone utility function for enhanced clean_authors method with workflow support.
    
    This is a utility function that can be called from any form's clean_authors method
    to add workflow support. For forms that inherit from PersonWorkflowMixin,
    use the clean_authors_with_workflow method instead.
    
    Args:
        form_instance: The form instance that should have PersonWorkflowMixin capabilities
    
    Returns:
        Either the processed authors data or a redirect response for workflow
    """
    if not hasattr(form_instance, 'check_person_disambiguation_needed'):
        raise ValueError("Form instance must have PersonWorkflowMixin capabilities")
    
    authors = form_instance.cleaned_data.get('authors', [])
    
    # Check if disambiguation workflow is needed
    workflow_result = form_instance.check_person_disambiguation_needed(['authors'])
    
    if workflow_result:
        field_name, names_needing_resolution = workflow_result
        if names_needing_resolution:
            logger.debug(f"clean_authors_with_workflow: Found names needing disambiguation: {names_needing_resolution}")
            # Start workflow and return redirect response
            return form_instance.start_person_workflow(field_name, names_needing_resolution)
    
    return authors


def clean_supervisors_with_workflow(form_instance):
    """
    Standalone utility function for enhanced clean_supervisors method with workflow support.
    
    This is a utility function that can be called from any form's clean_supervisors method
    to add workflow support. For forms that inherit from PersonWorkflowMixin,
    use the clean_supervisors_with_workflow method instead.
    
    Args:
        form_instance: The form instance that should have PersonWorkflowMixin capabilities
    
    Returns:
        Either the processed supervisors data or a redirect response for workflow
    """
    if not hasattr(form_instance, 'check_person_disambiguation_needed'):
        raise ValueError("Form instance must have PersonWorkflowMixin capabilities")
    
    supervisors = form_instance.cleaned_data.get('supervisors', [])
    
    # Check if disambiguation workflow is needed
    workflow_result = form_instance.check_person_disambiguation_needed(['supervisors'])
    
    if workflow_result:
        field_name, names_needing_resolution = workflow_result
        if names_needing_resolution:
            logger.debug(f"clean_supervisors_with_workflow: Found names needing disambiguation: {names_needing_resolution}")
            # Start workflow and return redirect response
            return form_instance.start_person_workflow(field_name, names_needing_resolution)
    
    return supervisors


def clean_editors_with_workflow(form_instance):
    """
    Standalone utility function for enhanced clean_editors method with workflow support.
    
    This is a utility function that can be called from any form's clean_editors method
    to add workflow support. For forms that inherit from PersonWorkflowMixin,
    use the clean_editors_with_workflow method instead.
    
    Args:
        form_instance: The form instance that should have PersonWorkflowMixin capabilities
    
    Returns:
        Either the processed editors data or a redirect response for workflow
    """
    if not hasattr(form_instance, 'check_person_disambiguation_needed'):
        raise ValueError("Form instance must have PersonWorkflowMixin capabilities")
    
    editors = form_instance.cleaned_data.get('editors', [])
    
    # Check if disambiguation workflow is needed
    workflow_result = form_instance.check_person_disambiguation_needed(['editors'])
    
    if workflow_result:
        field_name, names_needing_resolution = workflow_result
        if names_needing_resolution:
            logger.debug(f"clean_editors_with_workflow: Found names needing disambiguation: {names_needing_resolution}")
            # Start workflow and return redirect response
            return form_instance.start_person_workflow(field_name, names_needing_resolution)
    
    return editors
