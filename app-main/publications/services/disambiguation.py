import logging
import ast

from django.shortcuts import render, redirect

from publications import models
from publications.utils.person_matching import PersonMatcher

logger = logging.getLogger(__name__)



class PersonDisambiguationService:
    """
    A service for handling the person disambiguation workflow.
    
    This service manages the state of the disambiguation workflow in the session
    and provides methods for resolving person name ambiguities.
    
    All workflow state is stored in a single session key 'person_disambiguation'
    to avoid key collisions with other workflows.
    """
    
    def __init__(self, request):
        """Initialize with a request object to access the session."""
        self.request = request
        self.session = request.session
        self.matcher = PersonMatcher()
        self._ensure_workflow_session()
        
        # Debug the current state
        pd = self.session.get('person_disambiguation', {})
        workflows = pd.get('workflows', [])
        current_index = pd.get('current_index')
        logger.debug(f"PersonDisambiguationService.__init__: Found {len(workflows)} workflows, current_index={current_index}")
        
        # Log details of each workflow
        for i, wf in enumerate(workflows):
            pending = wf.get('pending_persons', [])
            step = wf.get('current_step', 0)
            field = wf.get('field_name', 'unknown')
            is_complete = step >= len(pending)
            logger.debug(f"    Workflow {i}: field={field}, step={step}/{len(pending)}, complete={is_complete}, pending={pending}")

    @staticmethod
    def _split_person_list(value: str) -> list:
        """
        Split a string containing person names by ';' or ',' delimiters.
        If ';' is present, only split on ';'. Otherwise, split on ','.
        Strips whitespace from each item and ignores empty results.
        """
        if not isinstance(value, str):
            return [value]
        if ';' in value:
            items = [v.strip() for v in value.split(';')]
        else:
            items = [v.strip() for v in value.split(',')]
        return [v for v in items if v]

    def _get_tag(self, string, tag_name):
        """Extract tag value from string like '[id:123]' -> 123, using NameNormalizer."""
        tags = self.matcher.normalizer.get_tags(string)
        if tag_name not in tags:
            return None
        value = tags[tag_name]
        if value == '0':
            return 0
        elif value == 'ldap':
            return 'ldap'
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    
    def _remove_tags(self, string):
        """Remove all tags like '[id:123]' from string, using NameNormalizer."""
        return self.matcher.normalizer.remove_tags(string)
    

    def _ensure_workflow_session(self):
        """
        Initialize workflow session if not exists
        
        The person_disambiguation namespace contains:
        - workflows: List of workflow dictionaries
        - current_index: Index of the current workflow being processed
        - resolved_field_values: Dict mapping field names to their resolved values
        - resolved_form_data: Complete form data with all resolved fields (added after processing)
        - workflow_updated_fields: List of field names that have been updated
        
        Note: All session storage is kept within this namespace for better organization.
        """
        if 'person_disambiguation' not in self.session:
            self.session['person_disambiguation'] = {
                'workflows': [],
                'current_index': None,  # Set to None initially, will be set when starting a workflow
                'original_form_data': None,
                'resolved_field_values': {},
                'resolved_form_data': {},        # Complete form data with resolved fields
                'workflow_updated_fields': [],   # List of field names that were updated
            }

    def _get_session_data(self):
        """Return the canonical person_disambiguation dict from the session.

        Ensures the namespace exists and returns it. Use this instead of
        accessing self.session['person_disambiguation'] or get(...).
        """
        self._ensure_workflow_session()
        return self.session['person_disambiguation']

    def _save(self):
        """Mark the session as modified so Django will save it."""
        # Using Django session API: setting modified ensures the session is saved.
        self.session.modified = True

    def _current_workflow(self):
        """Return a tuple (workflow_dict, index) for the current workflow or (None, None)."""
        pd = self._get_session_data()
        idx = pd.get('current_index')
        workflows = pd.get('workflows', [])
        if idx is None or idx < 0 or idx >= len(workflows):
            return None, None
        return workflows[idx], idx

    def is_workflow_active(self, id=None, workflow=None):
        """
        Check a person disambiguation workflow is currently active.
        If neither id nor workflow is provided, checks the current workflow.
        
        Args:
            id: Optional index of the workflow to check. 
            workflow: Optional workflow dictionary to check directly. If provided, 'id' is ignored.
        Returns:
            True if there is at least one workflow with unresolved persons, False otherwise.
        """
        pd = self._get_session_data()
        workflows = pd.get('workflows', [])
        current_index = pd.get('current_index', None)

        if workflow is not None:
            # Check specific workflow provided
            if 'pending_persons' not in workflow or 'current_step' not in workflow:
                return False
        elif id is not None:
            # Check specific workflow by index
            if id < 0 or id >= len(workflows):
                return False
            workflow = workflows[id]
        else:
            if not workflows:
                return False
            if current_index is None:
                return False
            if current_index < 0 or current_index >= len(workflows):
                return False
            workflow = workflows[current_index]

        pending = workflow.get('pending_persons', [])
        current_step = workflow.get('current_step', 0)
        return current_step < len(pending)

    def is_workflow_finalized(self, id=None, workflow=None):
        """
        Check if all steps in a particular workflow are complete.
        If neither id nor workflow is provided, checks the current active workflow.

        Args:
            id: Optional index of the workflow to check. If None, checks the current active workflow.
            workflow: Optional workflow dictionary to check directly. If provided, 'id' is ignored.
        """
        return not self.is_workflow_active(id=id, workflow=workflow)

    def is_name_resolved(self, name):
        """Check if a name is already resolved and doesn't need disambiguation"""
        # Check for skip marker
        if name.startswith('SKIP:'):
            return True
            
        # Check for ID tag
        id_tag = self._get_tag(name, 'id')
        if id_tag == 0:
            # Marked for creation - no disambiguation needed
            return True
        elif id_tag and id_tag != 'ldap':
            # Check if ID exists
            try:
                models.Person.objects.get(id=id_tag)
                return True
            except models.Person.DoesNotExist:
                return False
                
        # Check if name is a numeric ID
        if name.isdigit():
            try:
                models.Person.objects.get(id=int(name))
                return True
            except models.Person.DoesNotExist:
                return False
                
        return False

    def get_resolved_form_data(self):
        """
        Merge all updated fields into the original form data.
        Returns the resolved form data dict.
        """
        pd = self._get_session_data()

        # Ensure resolved_field_values exists
        pd.setdefault('resolved_field_values', {})

        workflows = pd.get('workflows', [])
        if not workflows:
            return {}

        # Otherwise, rebuild it from the field values
        resolved_form_data = (pd.get('original_form_data') or {}).copy()
        for wf in workflows:
            field = wf.get('field_name')
            if field in pd.get('resolved_field_values', {}):
                resolved_form_data[field] = pd['resolved_field_values'][field]

        logger.debug("Built resolved form data from resolved_field_values")
        return resolved_form_data
    
        
    def store_resolved_form_data_in_session(self, resolved_form_data):
        """Store the resolved form data and updated fields in the session.

        All data is stored within the 'person_disambiguation' namespace.

        Finally the session form_data is updated (top-level) so views can pick it up.
        """
        pd = self._get_session_data()
        workflows = pd.get('workflows', [])

        # Store within the person_disambiguation namespace only
        pd['resolved_form_data'] = resolved_form_data
        pd['workflow_updated_fields'] = [wf.get('field_name') for wf in workflows]

        # Update session form_data (top-level) so views can pick it up
        self.request.session['form_data'] = resolved_form_data

        self._save()
        logger.debug("Stored resolved_form_data in person_disambiguation namespace and session form_data")


    def start_workflow(self, field_name, person_names, original_form_data, source_url=None, review_url=None):
        """
        Start new disambiguation workflow for a field.
        
        Args:
            field_name: Name of the field containing person data (e.g., 'authors')
            person_names: List of person names to disambiguate
            original_form_data: Original form data to update with resolved persons
            source_url: URL to return to after workflow is finalized
            review_url: URL to redirect to when disambiguation is complete
        """
        pd = self._get_session_data()

        # Store original_form_data only if not already present
        if pd.get('original_form_data') is None:
            pd['original_form_data'] = original_form_data

        pd.setdefault('workflows', []).append({
            'pending_persons': person_names,
            'resolved_persons': {},
            'current_step': 0,
            'field_name': field_name,
            'source_url': source_url or self.request.path,
            'review_url': review_url or self.request.path,
        })

        # Only set current_index if it's None (no active workflow)
        # This allows multiple workflows to be queued but processes them one at a time
        if pd.get('current_index') is None:
            pd['current_index'] = 0
            logger.debug(f"PersonDisambiguationService:start_workflow: Set current_index to {pd['current_index']}")
            logger.debug(f"PersonDisambiguationService:start_workflow: Started workflow for {field_name} with {len(person_names)} persons")
        else:
            logger.debug(f"PersonDisambiguationService:start_workflow: Added workflow for {field_name} with {len(person_names)} persons (queue position: {len(pd['workflows'])-1})")

        self._save()


    def _extract_raw_person_data(self, form_data, field_name):
        """
        Extract a list of person names from form-like data for a given field.

        This method is designed to work with any object that implements the form/QueryDict API
        (i.e., has getlist/get methods), such as Django forms, QueryDicts, or the internal MockFormData.
        It ensures that the returned value is always a flat list of strings, regardless of whether the
        input is a list, a string, or a more complex structure (e.g., a stringified list).

        Rationale:
            By using a form-like interface, this method can be reused for both real Django forms and
            for test/mock data, keeping the extraction logic generic and robust. This avoids the need
            for type checks and branching logic elsewhere in the workflow code.

        Args:
            form_data: An object with getlist/get methods (e.g., QueryDict, MockFormData, or similar),
                       or a dict-like object containing field values.
            field_name: The name of the field to extract person data from.

        Returns:
            A flat list of person name strings, suitable for further disambiguation processing.
        """

        # Get field values from form data
        if hasattr(form_data, 'getlist'):
            field_values = form_data.getlist(field_name)
        else:
            field_values = form_data.get(field_name, [])
            
        # Ensure we have a list
        if field_values is None:
            field_values = []
        elif isinstance(field_values, str):
            field_values = [field_values]
            
        # Process each value, handling potential nested structures and delimiters
        processed_values = []
        for value in field_values:
            if not value:
                continue
            # Handle string representation of lists
            if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
                try:
                    parsed_items = ast.literal_eval(value)
                    if isinstance(parsed_items, list):
                        processed_values.extend(parsed_items)
                        continue
                except (ValueError, SyntaxError):
                    pass  # Fallback to delimiter splitting below
            # Handle delimited strings (either ';' or ',')
            if isinstance(value, str) and (',' in value or ';' in value):
                processed_values.extend(self._split_person_list(value))
            else:
                processed_values.append(value)
        return processed_values


    def get_current_person(self):
        """Get the current person name being processed"""
        wf, idx = self._current_workflow()
        if wf is None:
            return None

        step = wf.get('current_step', 0)
        pending = wf.get('pending_persons', [])
        if step < len(pending):
            return pending[step]
        return None
    
    def get_current_step_info(self):
        """Get information about the current step"""
        wf, idx = self._current_workflow()
        if wf is None:
            return {'current_step': 0, 'total_steps': 0, 'progress_percent': 0}

        current_step = wf.get('current_step', 0)
        total_steps = len(wf.get('pending_persons', []))
        return {
            'current_step': current_step + 1,  # 1-based for display
            'total_steps': total_steps,
            'progress_percent': int((current_step / total_steps) * 100) if total_steps > 0 else 0
        }
    
    def resolve_current_person(self, resolution_data):
        """
        Resolve the current person and advance to the next step.
        
        Args:
            resolution_data: The resolved person data (ID, new person data, or skip marker)
        """
        logger.debug(f'PersonDisambiguationService:resolve_current_person: Called with resolution_data={resolution_data}')

        wf, idx = self._current_workflow()
        if wf is None:
            logger.debug('PersonDisambiguationService:resolve_current_person: No current workflow, returning')
            return

        current_person = self.get_current_person()

        if current_person:
            logger.debug(f'PersonDisambiguationService:resolve_current_person: Setting resolved_persons[{current_person}] = {resolution_data}')
            wf.setdefault('resolved_persons', {})[current_person] = resolution_data
            wf['current_step'] = wf.get('current_step', 0) + 1
            logger.debug(f'PersonDisambiguationService:resolve_current_person: Incremented current_step to {wf["current_step"]}')
            self._save()
        else:
            logger.debug('PersonDisambiguationService:resolve_current_person: No current person to resolve')
        
    def advance_to_next_workflow(self):
        """
        Move to the next workflow in the queue after finalizing the current one.
        Returns True if there was a next workflow to move to, False otherwise.
        """
        pd = self._get_session_data()
        workflows = pd.get('workflows', [])
        if not workflows:
            return False

        current_index = pd.get('current_index')
        if current_index is None:
            # No active workflow, start with the first one if any
            if workflows:
                pd['current_index'] = 0
                self._save()
                logger.debug(f"PersonDisambiguationService:advance_to_next_workflow: No current_index, setting to 0")
                return True
            logger.debug(f"PersonDisambiguationService:advance_to_next_workflow: No workflows available")
            return False

        # Check if there are more workflows after this one
        next_index = current_index + 1
        if next_index < len(workflows):
            pd['current_index'] = next_index
            self._save()
            logger.debug(f"PersonDisambiguationService:advance_to_next_workflow: Moving from workflow {current_index} to {next_index}")
            return True

        logger.debug("PersonDisambiguationService:advance_to_next_workflow: No more workflows available")
        return False

    def has_finalized_workflows(self):
        """
        Returns True if there is at least one finalized workflow in the session.
        """
        pd = self._get_session_data()
        workflows = pd.get('workflows', [])
        if not workflows:
            return False
        # A workflow is finalized if its current_step >= number of pending_persons
        for wf in workflows:
            if self.is_workflow_finalized(workflow=wf):
                return True
        return False
        
    def get_matches_for_current_person(self):
        """Get matches for the current person using PersonMatcher"""
        current_person = self.get_current_person()
        if not current_person:
            return []
            
        # Use PersonMatcher to find matches
        return self.matcher.find_matches(current_person)
    
    def extract_persons_needing_disambiguation(self, form_data, field_name):
        """
        Extract person names from form data that need disambiguation.
        
        Args:
            form_data: Form data containing person names
            field_name: Name of the field containing person data
            
        Returns:
            List of person names that need disambiguation
        """
        # Extract raw person data from form
        person_data = self._extract_raw_person_data(form_data, field_name)
        
        # Filter to names needing disambiguation
        names_needing_resolution = []
        for name in person_data:
            # Skip empty strings or non-string values
            if not name or not isinstance(name, str) or not name.strip():
                continue
                
            # Skip already resolved names (with SKIP: prefix or valid IDs)
            if self.is_name_resolved(name):
                continue
            
            names_needing_resolution.append(name)
            
        return names_needing_resolution
    

    def update_form_data_with_resolved_persons(self):
        """
        Update form data with resolved persons.
        
        Returns:
            Updated form data dictionary
        """
        if not self.is_workflow_finalized():
            return None
        pd = self._get_session_data()
        wf, idx = self._current_workflow()
        if wf is None:
            return None
        resolved_persons = wf.get('resolved_persons', {})
        original_form_data = pd.get('original_form_data')
        field_name = wf.get('field_name')
        
        # Create a copy of the original form data
        updated_form_data = original_form_data.copy()
        
        # Extract original field values
        original_values = self._extract_raw_person_data(original_form_data, field_name)
        
        # Replace with resolved values
        resolved_values = []
        for value in original_values:
            if value in resolved_persons:
                resolved_values.append(resolved_persons[value])
            else:
                resolved_values.append(value)
                
        # Update the form data
        updated_form_data[field_name] = resolved_values
        
        return updated_form_data
    
    def finalize_workflow(self):
        """
        Finalize the workflow and prepare form data for form submission.
        
        Returns:
            Tuple of (updated_form_data, redirect_url)
        """
        if not self.is_workflow_finalized():
            return None, None

        # Get the current workflow
        pd = self._get_session_data()
        wf, current_index = self._current_workflow()
        if wf is None:
            return None, None
        workflow = wf
        logger.debug(f"PersonDisambiguationService:finalize_workflow: Finalizing workflow {current_index} for field {workflow.get('field_name')}")

        # Get updated form data
        updated_form_data = self.update_form_data_with_resolved_persons()
        if updated_form_data is None:
            return None, None

        # Store updated data for this field in the session
        pd.setdefault('resolved_field_values', {})[workflow.get('field_name')] = updated_form_data[workflow.get('field_name')]
        self._save()
        logger.debug(f"PersonDisambiguationService:finalize_workflow: Stored resolved data for field {workflow.get('field_name')}")

        # Check if there are more workflows to process
        if self.advance_to_next_workflow():
            logger.debug(f"PersonDisambiguationService:finalize_workflow: Advanced to next workflow, redirecting to disambiguation step")
            # Redirect to the next disambiguation step
            return None, redirect('publications:disambiguate_person_step').url

        logger.debug(f"PersonDisambiguationService:finalize_workflow: All workflows complete")

        # Choose redirect_url: prefer review_url, then source_url
        redirect_url = workflow.get('review_url') or workflow.get('source_url')
        logger.debug(f'PersonDisambiguationService:finalize_workflow: redirect_url={redirect_url}')

        resolved_form_data = self.get_resolved_form_data()
        self.store_resolved_form_data_in_session(resolved_form_data)

        return updated_form_data, redirect_url

    # Removed compatibility method get_form_data() as part of standardization
        
    def process_finalized_workflows(self):
        """
        Process any finalized workflows in the session.
        Creates new Person objects for any 'CREATE:' markers.
        Returns True if any processing was done, False otherwise.
        """

        logger.debug("PersonDisambiguationService:process_finalized_workflows: called")

        if not self.has_finalized_workflows():
            logger.debug("PersonDisambiguationService:process_finalized_workflows: No finalized workflows found.")
            return False

        resolved_form_data = self.get_resolved_form_data()
        logger.debug(f"PersonDisambiguationService:process_finalized_workflows: resolved_form_data={resolved_form_data}")
        if not resolved_form_data:
            logger.debug("PersonDisambiguationService:process_finalized_workflows: No resolved_form_data found.")
            return False

        changes_made = False

        # Process each field that might contain persons
        person_fields = ['authors', 'supervisors', 'editors']
        for field_name in person_fields:
            if field_name not in resolved_form_data:
                logger.debug(f"PersonDisambiguationService:process_finalized_workflows: Field '{field_name}' not in resolved_form_data.")
                continue

            field_value = resolved_form_data[field_name]
            logger.debug(f"PersonDisambiguationService:process_finalized_workflows: Checking field '{field_name}' with value {field_value}")
            for i, value in enumerate(field_value):
                logger.debug(f"PersonDisambiguationService:process_finalized_workflows: Checking value '{value}' at index {i} in field '{field_name}'")
                if isinstance(value, str) and value.startswith('CREATE:'):
                    person_name = value[7:]  # Remove 'CREATE:' prefix
                    logger.debug(f"PersonDisambiguationService:process_finalized_workflows: Found CREATE marker for '{person_name}' in field '{field_name}' at index {i}")

                    # Create the person
                    from publications.models import Person
                    new_person = Person.objects.create(name=person_name)
                    logger.debug(f"PersonDisambiguationService:process_finalized_workflows: Created new person: {new_person.get_full_name()} (ID: {new_person.pk})")

                    # Replace the CREATE: marker with the new person's ID
                    field_value[i] = str(new_person.id)
                    changes_made = True

        if changes_made:
            logger.debug("PersonDisambiguationService:process_finalized_workflows: Changes made, updating session form_data.")
            # Store the updated form data with the new person IDs
            self.store_resolved_form_data_in_session(resolved_form_data)
            # Clear finalized workflows after processing
            self.clear_finalized_workflows()
            logger.debug("PersonDisambiguationService:process_finalized_workflows: Cleared finalized workflows after processing.")
        else:
            logger.debug("PersonDisambiguationService:process_finalized_workflows: No CREATE markers found, no changes made.")

        return changes_made

    # Session management helpers and workflow cleanup
    def clear_finalized_workflows(self):
        """Remove finalized workflows and reset indices as needed."""
        pd = self._get_session_data()
        workflows = pd.get('workflows', [])

        incomplete_workflows = [wf for wf in workflows if not self.is_workflow_finalized(workflow=wf)]
        pd['workflows'] = incomplete_workflows
        pd['current_index'] = 0 if incomplete_workflows else None
        self._save()

        # Clear resolved form data since it's no longer valid
        pd.pop('resolved_form_data', None)
        pd.pop('workflow_updated_fields', None)
        self._save()

    def clear_single_workflow(self, field_name=None, index=None):
        """Remove one workflow by field_name or index. If none given, removes current."""
        pd = self._get_session_data()
        workflows = pd.get('workflows', [])

        # Determine which workflow to remove
        if field_name is not None:
            target_index = next((i for i, wf in enumerate(workflows) if wf.get('field_name') == field_name), None)
            if target_index is None:
                return  # No workflow for this field_name
        elif index is not None:
            target_index = index
        else:
            target_index = pd.get('current_index', None)

        if not workflows or target_index is None:
            return

        if 0 <= target_index < len(workflows):
            workflows.pop(target_index)
            pd['current_index'] = next((i for i, wf in enumerate(workflows) if not self.is_workflow_finalized(wf)), None)
            self._save()
        else:
            raise ValueError("Invalid workflow index")

    def clear_all(self):
        """Clear the entire person_disambiguation namespace from session."""
        if 'person_disambiguation' in self.session:
            del self.session['person_disambiguation']
        self._ensure_workflow_session()
        self._save()
        logger.debug("PersonDisambiguationService:clear_session_data: Canceled all disambiguation workflows and cleared session data")

    def clear_workflows_only(self):
        """Clear only workflows but preserve original_form_data for returning to the form."""
        self._ensure_workflow_session()
        pd = self._get_session_data()
        original_form_data = pd.get('original_form_data', None)
        # Reset the namespace but put original_form_data back
        self.clear_all()
        pd = self._get_session_data()
        pd['original_form_data'] = original_form_data
        self._save()
        return True