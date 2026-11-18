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
    
    def start_workflow(self, field_name, person_names, original_form_data, source_url=None,
                       target=None):
        """Start new workflow for a field.

        ``target`` is the report form the names were typed in ('add' or 'edit:<pk>',
        views.report_form_target); complete_person_workflow writes the choices into that
        form's session data."""
        self.session['person_workflow'] = {
            'pending_persons': list(person_names),
            'pending_fields': [field_name] * len(person_names),
            'resolved': [],
            'original_form_data': original_form_data,
            'current_step': 0,
            'field_name': field_name,
            'source_url': source_url or self.request.path,
            'target': target,
        }
        self.session.modified = True

    def add_names(self, field_name, person_names):
        """Add the names of another field of the same form (e.g. supervisors after authors)."""
        workflow = self.session['person_workflow']
        workflow['pending_persons'] += list(person_names)
        workflow['pending_fields'] += [field_name] * len(person_names)
        self.session.modified = True

    def get_current_field(self):
        """The field of the person being processed."""
        workflow = self.session['person_workflow']
        fields = workflow.get('pending_fields') or []
        step = workflow['current_step']
        return fields[step] if step < len(fields) else workflow.get('field_name')
    
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
            workflow.setdefault('resolved', []).append(
                [self.get_current_field(), current_person, person_id_or_name])
            workflow['current_step'] += 1
            self.session.modified = True
    
    def is_complete(self):
        """Check if workflow is complete"""
        workflow = self.session['person_workflow']
        return workflow['current_step'] >= len(workflow['pending_persons'])
    
    def get_resolved_persons(self):
        """The choices per field: {field_name: {typed name: pk, 'CREATE:<name>' or 'SKIP:<name>'}}"""
        resolved = {}
        for field_name, name, value in self.session['person_workflow'].get('resolved', []):
            resolved.setdefault(field_name, {})[name] = value
        return resolved

    def get_target(self):
        return self.session['person_workflow'].get('target')
    
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
        
        # Skip items that were explicitly skipped by user, or chosen to be created on save
        if name.startswith(('SKIP:', 'CREATE:')):
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
            # The new person is created when the report is saved, inside its transaction
            # (person_from_form_value), so an abandoned form or a failed save leaves none.
            person_name = remove_tags(current_person_name)
            if person_name:
                workflow.resolve_current_person(f"CREATE:{person_name}")
                messages.success(request, f'"{person_name}" will be created as a new person '
                                          'when the report is saved.')
                if workflow.is_complete():
                    return redirect('publications:complete_person_workflow')
                return redirect('publications:disambiguate_person_step')
            messages.error(request, "Empty name.")

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
        'field_name': workflow.get_current_field(),
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
    
    # Lazy import: views imports this module.
    from publications.views import get_report_form_data, store_report_form_data

    resolved = workflow.get_resolved_persons()
    target = workflow.get_target()
    workflow.clear_workflow()

    # Write the choices into the session data of the form the names were typed in
    # (add, or edit of one report); review and finalize read only that data.
    form_data = get_report_form_data(request.session, target) if target else None
    if form_data is None:
        messages.error(request, "The report form data is no longer in the session. "
                                "Please fill in the form again.")
        if target and target.startswith('edit:'):
            return redirect('publications:edit_report', pk=int(target.split(':', 1)[1]))
        return redirect('publications:add_report')
    for field_name, choices in resolved.items():
        values = form_data.get(field_name) or []
        if isinstance(values, str):
            values = [values]
        form_data[field_name] = [choices.get(value, value) for value in values]
    store_report_form_data(request.session, target, form_data)
    request.session.modified = True

    if target.startswith('edit:'):
        return redirect('publications:edit_report_review', pk=int(target.split(':', 1)[1]))
    return redirect('publications:add_report_review')


def person_display_name(value):
    """The name in a 'CREATE:<name>' / 'SKIP:<name>' value of the report form data, else None."""
    for prefix in ('CREATE:', 'SKIP:'):
        if isinstance(value, str) and value.startswith(prefix):
            return remove_tags(value[len(prefix):])
    return None


def person_from_form_value(value, user, created):
    """The Person for a value of the report form data: a pk, or a 'CREATE:<name>' /
    'SKIP:<name>' marker from the workflow ("Create New Person" / "Use As-Is (Create Later)"),
    for which a new person is created now (name parts parsed, created_by ``user``).
    ``created`` maps the names already created in this save to their Person, so a name typed
    as author and as supervisor is one person. Raises ValueError for an unresolved name."""
    name = person_display_name(value)
    if name is None:
        return Person.objects.get(pk=int(value))
    if not name:
        raise ValueError(f'Empty person name in {value!r}')
    if name not in created:
        person = Person(created_by=user, modified_by=user)
        person.set_names(name)  # saves
        created[name] = person
    return created[name]
