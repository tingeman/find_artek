"""Person disambiguation workflow functionality."""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from publications.models import Person
from publications.forms.person import AddPersonForm, PersonSelectForm
import re
import ast

import logging
logger = logging.getLogger(__name__)

class PersonWorkflowSession:
    """Manages person disambiguation workflow state in session"""
    
    def __init__(self, request):
        self.request = request
        self.session = request.session
        self._ensure_workflow_session()
    
    def _ensure_workflow_session(self):
        """Initialize workflow session if not exists"""
        if 'person_workflow' not in self.session:
            self.session['person_workflow'] = {
                'pending_persons': [],
                'resolved_persons': {},
                'original_form_data': {},
                'current_step': 0,
                'field_name': None
            }
    
    def start_workflow(self, field_name, person_names, original_form_data, source_url=None):
        """Start new workflow for a field"""
        self.session['person_workflow'] = {
            'pending_persons': person_names,
            'resolved_persons': {},
            'original_form_data': original_form_data,
            'current_step': 0,
            'field_name': field_name,
            'source_url': source_url or self.request.path
        }
        self.session.modified = True
    
    def get_current_person(self):
        """Get the current person being processed"""
        workflow = self.session['person_workflow']
        step = workflow['current_step']
        pending = workflow['pending_persons']
        
        if step < len(pending):
            return pending[step]
        return None
    
    def resolve_current_person(self, person_id_or_name):
        """Resolve current person and move to next"""
        workflow = self.session['person_workflow']
        current_person = self.get_current_person()
        
        if current_person:
            workflow['resolved_persons'][current_person] = person_id_or_name
            workflow['current_step'] += 1
            self.session.modified = True
    
    def is_complete(self):
        """Check if workflow is complete"""
        workflow = self.session['person_workflow']
        return workflow['current_step'] >= len(workflow['pending_persons'])
    
    def get_resolved_persons(self):
        """Get all resolved persons"""
        return self.session['person_workflow']['resolved_persons']
    
    def get_original_form_data(self):
        """Get original form data"""
        return self.session['person_workflow']['original_form_data']
    
    def get_field_name(self):
        """Get the field being processed"""
        return self.session['person_workflow']['field_name']
    
    def get_source_url(self):
        """Get the source URL to redirect back to"""
        return self.session['person_workflow'].get('source_url', '/publications/add/report/')
    
    def clear_workflow(self):
        """Clear workflow session"""
        if 'person_workflow' in self.session:
            del self.session['person_workflow']
            self.session.modified = True


def get_tag(string, tag_name):
    """Extract tag value from string like '[id:123]' -> 123"""
    pattern = r'\[' + tag_name + r':([^\]]+)\]'
    match = re.search(pattern, string)
    if match:
        value = match.group(1)
        if value == '0':
            return 0
        elif value == 'ldap':
            return 'ldap'
        else:
            try:
                return int(value)
            except ValueError:
                return None
    return None


def remove_tags(string):
    """Remove all tags like '[id:123]' from string"""
    return re.sub(r'\[[^\]]+\]', '', string).strip()


def get_person_matches(name_string):
    """
    Find person matches in database using comprehensive matching strategies.
    Returns dict with matches organized by confidence levels.
    """
    
    clean_name = remove_tags(name_string).strip()
    
    if not clean_name:
        return {'exact': [], 'relaxed': []}
    
    # Use the enhanced matching from forms
    form_instance = PersonSelectForm()
    all_matches = form_instance.get_person_matches(clean_name)
    
    # Organize matches by confidence level for backwards compatibility
    exact_matches = []
    relaxed_matches = []
    
    for match in all_matches:
        person = match['person']
        confidence = match['confidence']
        
        # High confidence matches (95%+) considered "exact"
        if confidence >= 0.95:
            exact_matches.append(person)
        # Medium to high confidence (60%+) considered "relaxed"
        elif confidence >= 0.6:
            relaxed_matches.append(person)
        # Low confidence matches not included to avoid clutter
    
    return {
        'exact': exact_matches,
        'relaxed': relaxed_matches,
        'all_matches': all_matches  # Include enhanced match data
    }


def extract_person_names(form_data, field_name):
    """
    Extract person names from form data that need disambiguation.
    
    Handles complex data structures including nested lists and string representations of lists.
    
    Args:
        form_data: Form data object with getlist method (request.POST) or any object
        field_name: Name of the field containing person data
    
    Returns:
        List of names that need disambiguation
    """
    names_needing_resolution = []
    processed_names = []
    
    # Debug information
    logger.debug(f"extract_person_names: processing {field_name}")
    if hasattr(form_data, 'getlist'):
        logger.debug(f"extract_person_names: form_data.getlist({field_name}) = {form_data.getlist(field_name)}")
    else:
        logger.debug(f"extract_person_names: form_data.get({field_name}) = {form_data.get(field_name, [])}")
    
    # Get the field values - could be list, single value, or object with getlist method
    if hasattr(form_data, 'getlist'):
        field_values = form_data.getlist(field_name)
    else:
        field_values = form_data.get(field_name, [])
    
    # Ensure we have a list to process
    if field_values is None:
        field_values = []
    elif isinstance(field_values, str):
        field_values = [field_values]
    
    logger.debug(f"extract_person_names: initial field_values = {field_values}")
    
    # Process field values to extract individual items from potential nested structures
    for value in field_values:
        if not value:
            continue
        # Handle string representation of lists
        if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
            try:
                # Attempt to parse as a list
                parsed_items = ast.literal_eval(value)
                if isinstance(parsed_items, list):
                    logger.debug(f"extract_person_names: parsed list from string: {parsed_items}")
                    # Process each item in the parsed list
                    for item in parsed_items:
                        processed_names.append(item)
                    continue  # Skip adding the original string
            except (ValueError, SyntaxError) as e:
                logger.warning(f"extract_person_names: failed to parse list string: {e}")
                # If parsing fails, treat as normal string
                processed_names.append(value)
        else:
            # Regular value
            processed_names.append(value)
    
    logger.debug(f"extract_person_names: processed_names = {processed_names}")
    
    # Now process each name for disambiguation
    for name in processed_names:
        if not name or not isinstance(name, str) or not name.strip():
            continue
        
        # Skip items that were explicitly skipped by user
        if name.startswith('SKIP:'):
            continue
            
        # Check if name already has an ID tag
        person_id = get_tag(name, 'id')
        
        if person_id == 0:
            # Person marked for creation - no disambiguation needed
            continue
        elif person_id and person_id != 'ldap':
            # Existing person ID - verify it exists
            try:
                Person.objects.get(id=person_id)
                logger.debug(f"extract_person_names: found existing person with ID tag: {person_id}")
                continue  # Valid existing person
            except Person.DoesNotExist:
                # Invalid ID, treat as new name
                logger.warning(f"extract_person_names: person with ID tag {person_id} not found")
                pass
                
        # If name is a numeric string, treat as PK and skip if valid
        if name.isdigit():
            try:
                person = Person.objects.get(id=int(name))
                logger.debug(f"extract_person_names: found existing person with ID: {name} ({person})")
                continue  # Valid existing person, no disambiguation needed
            except Person.DoesNotExist:
                logger.warning(f"extract_person_names: person with ID {name} not found")
                pass  # Not a valid PK, continue with disambiguation
        
        # No valid ID tag, check if disambiguation is needed
        matches = get_person_matches(name)
        if matches['exact'] or matches['relaxed']:
            # Has potential matches - needs disambiguation
            logger.info(f"extract_person_names: found matches for '{name}': {len(matches['exact'])} exact, {len(matches['relaxed'])} relaxed")
            names_needing_resolution.append(name)
        else:
            # No matches - will need to create new person
            logger.info(f"extract_person_names: no matches found for '{name}', will need to create")
            names_needing_resolution.append(name)
    
    logger.debug(f"extract_person_names: final names_needing_resolution = {names_needing_resolution}")
    return names_needing_resolution


@login_required
def disambiguate_person_step(request):
    """Handle individual person disambiguation step"""
    workflow = PersonWorkflowSession(request)
    current_person_name = workflow.get_current_person()
    
    if not current_person_name:
        messages.error(request, "No person to disambiguate.")
        return redirect('publications:add_report')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'select_existing':
            # User selected an existing person
            person_id = request.POST.get('person_id')
            try:
                person = Person.objects.get(id=person_id)
                # Store just the person ID for generic list handling
                workflow.resolve_current_person(str(person.id))
                
                if workflow.is_complete():
                    return redirect('publications:complete_person_workflow')
                else:
                    return redirect('publications:disambiguate_person_step')
                    
            except Person.DoesNotExist:
                messages.error(request, "Selected person not found.")
        
        elif action == 'create_new':
            # User wants to create a new person
            person_name = remove_tags(current_person_name)
            
            # Create the person using the AddPersonForm
            try:
                form = AddPersonForm({'name': person_name})
                if form.is_valid():
                    person = form.save(commit=False)
                    person.created_by = request.user
                    person.modified_by = request.user
                    person.save()
                    
                    # Store just the person ID for generic list handling
                    workflow.resolve_current_person(str(person.id))
                    
                    messages.success(request, f'Created new person: {person.get_full_name()}')
                    
                    if workflow.is_complete():
                        return redirect('publications:complete_person_workflow')
                    else:
                        return redirect('publications:disambiguate_person_step')
                else:
                    # If form validation fails, try basic creation
                    person = Person(created_by=request.user, modified_by=request.user)
                    person.set_names(person_name)
                    person.save()
                    
                    # Store just the person ID for generic list handling
                    workflow.resolve_current_person(str(person.id))
                    
                    messages.success(request, f'Created new person: {person.get_full_name()}')
                    
                    if workflow.is_complete():
                        return redirect('publications:complete_person_workflow')
                    else:
                        return redirect('publications:disambiguate_person_step')
                    
            except Exception as e:
                messages.error(request, f"Error creating person: {e}")
        
        elif action == 'skip':
            # User wants to skip (keep original string, don't treat as person)
            # Mark with SKIP: prefix so it won't trigger workflow again
            workflow.resolve_current_person(f"SKIP:{current_person_name}")
            
            if workflow.is_complete():
                return redirect('publications:complete_person_workflow')
            else:
                return redirect('publications:disambiguate_person_step')
    
    # GET request - show disambiguation form
    matches = get_person_matches(current_person_name)
    clean_name = remove_tags(current_person_name)
    
    context = {
        'current_person_name': current_person_name,
        'clean_name': clean_name,
        'exact_matches': matches['exact'],
        'relaxed_matches': matches['relaxed'],
        'all_matches': matches.get('all_matches', []),
        'field_name': workflow.get_field_name(),
        'step_number': workflow.session['person_workflow']['current_step'] + 1,
        'total_steps': len(workflow.session['person_workflow']['pending_persons'])
    }
    
    return render(request, 'publications/person_disambiguation_step.html', context)


@login_required
def complete_person_workflow(request):
    """Complete the person workflow and return to review form"""
    workflow = PersonWorkflowSession(request)
    
    if not workflow.is_complete():
        messages.error(request, "Workflow not complete.")
        return redirect('publications:disambiguate_person_step')
    
    # Get resolved data
    resolved_persons = workflow.get_resolved_persons()
    original_form_data = workflow.get_original_form_data()
    field_name = workflow.get_field_name()
    
    # Update form data with resolved persons
    updated_form_data = original_form_data.copy()
    resolved_names = []
    
    logger.debug(f"Original_form_data type: {type(original_form_data)}")
    logger.debug(f"Original_form_data: {original_form_data}")
    logger.debug(f"Resolved_persons mapping: {resolved_persons}")
    
    # Reconstruct the field with resolved person names
    original_names = original_form_data.getlist(field_name) if hasattr(original_form_data, 'getlist') else original_form_data.get(field_name, [])
    if isinstance(original_names, str):
        original_names = [original_names]
    
    for name in original_names:
        if name in resolved_persons:
            resolved_names.append(resolved_persons[name])
        else:
            resolved_names.append(name)  # Already resolved or doesn't need resolution
    
    # Always store as list, even for single values
    # This ensures consistency between authors and supervisors
    updated_form_data[field_name] = resolved_names
    
    # If we're dealing with supervisors, make sure it's a list
    # This is a special check because supervisors sometimes get stored as a string
    if field_name == 'supervisors' and not isinstance(updated_form_data[field_name], list):
        updated_form_data[field_name] = [updated_form_data[field_name]]
        logger.debug(f"Converted supervisors to list: {updated_form_data[field_name]}")
    
    logger.debug(f"updated_form_data before storing: {updated_form_data}")
    logger.debug(f"updated_form_data type: {type(updated_form_data)}")
    
    # Store updated form data in session - keep original structure intact
    # No field-specific logic needed since we only replaced ambiguous strings with IDs
    request.session['updated_form_data'] = dict(updated_form_data)
    request.session.modified = True
    
    # Get the source URL and determine publication ID for redirect
    source_url = workflow.get_source_url()
    
    # Clear workflow
    workflow.clear_workflow()
    
    messages.success(request, f"Person disambiguation complete for {field_name}.")
    
    # Determine redirect URL based on source
    if '/report/' in source_url and '/edit/' in source_url:
        # Extract publication ID from source URL
        match = re.search(r'/report/(\d+)/edit/', source_url)
        if match:
            publication_id = match.group(1)
            logger.debug(f"Redirecting to review view for publication {publication_id}")
            return redirect('publications:edit_report_review', pk=publication_id)
    elif '/add/' in source_url:
        logger.debug("Redirecting to add review view")
        return redirect('publications:add_report_review')
    
    # Fallback to original source URL for unknown cases
    logger.debug(f"Fallback redirect to original source: {source_url}")
    return redirect(source_url)
