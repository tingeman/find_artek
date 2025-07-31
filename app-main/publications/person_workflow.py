"""
Multi-step person disambiguation workflow.
Session-based approach for handling person name resolution.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from publications.models import Person
from publications.forms import AddPersonForm
import re


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
    
    def start_workflow(self, field_name, person_names, original_form_data):
        """Start new workflow for a field"""
        self.session['person_workflow'] = {
            'pending_persons': person_names,
            'resolved_persons': {},
            'original_form_data': original_form_data,
            'current_step': 0,
            'field_name': field_name
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
    Find person matches in database.
    Returns dict with exact and relaxed matches.
    """
    clean_name = remove_tags(name_string).strip()
    
    if not clean_name:
        return {'exact': [], 'relaxed': []}
    
    # Try exact match first
    exact_matches = Person.objects.filter(name__iexact=clean_name)
    
    # Try relaxed match (split on common separators)
    relaxed_matches = []
    name_parts = re.split(r'[,\s]+', clean_name)
    if len(name_parts) >= 2:
        first_part = name_parts[0].strip()
        last_part = name_parts[-1].strip()
        
        relaxed_qs = Person.objects.filter(
            name__icontains=first_part
        ).filter(
            name__icontains=last_part
        ).exclude(
            id__in=[p.id for p in exact_matches]
        )
        relaxed_matches = list(relaxed_qs)
    
    return {
        'exact': list(exact_matches),
        'relaxed': relaxed_matches
    }


def extract_person_names(form_data, field_name):
    """Extract person names from form data that need disambiguation"""
    names_needing_resolution = []
    
    # Get the field values - could be list or single value
    field_values = form_data.getlist(field_name) if hasattr(form_data, 'getlist') else form_data.get(field_name, [])
    if isinstance(field_values, str):
        field_values = [field_values]
    
    for name in field_values:
        if not name or not name.strip():
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
                continue  # Valid existing person
            except Person.DoesNotExist:
                # Invalid ID, treat as new name
                pass
        
        # No valid ID tag, check if disambiguation is needed
        matches = get_person_matches(name)
        if matches['exact'] or matches['relaxed']:
            # Has potential matches - needs disambiguation
            names_needing_resolution.append(name)
        else:
            # No matches - will need to create new person
            names_needing_resolution.append(name)
    
    return names_needing_resolution


@login_required
def disambiguate_person_step(request):
    """Handle individual person disambiguation step"""
    workflow = PersonWorkflowSession(request)
    current_person_name = workflow.get_current_person()
    
    if not current_person_name:
        messages.error(request, "No person to disambiguate.")
        return redirect('publications:add_publication')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'select_existing':
            # User selected an existing person
            person_id = request.POST.get('person_id')
            try:
                person = Person.objects.get(id=person_id)
                # Tag the name with the selected person ID
                tagged_name = f"{remove_tags(current_person_name)} [id:{person.id}]"
                workflow.resolve_current_person(tagged_name)
                
                if workflow.is_complete():
                    return redirect('publications:complete_person_workflow')
                else:
                    return redirect('publications:disambiguate_person_step')
                    
            except Person.DoesNotExist:
                messages.error(request, "Selected person not found.")
        
        elif action == 'create_new':
            # User wants to create a new person
            person_name = remove_tags(current_person_name)
            
            # Create the person
            try:
                person = Person.objects.create(
                    name=person_name,
                    created_by=request.user,
                    modified_by=request.user
                )
                # Tag the name with new person ID
                tagged_name = f"{person_name} [id:{person.id}]"
                workflow.resolve_current_person(tagged_name)
                
                messages.success(request, f'Created new person: {person.name}')
                
                if workflow.is_complete():
                    return redirect('publications:complete_person_workflow')
                else:
                    return redirect('publications:disambiguate_person_step')
                    
            except ValidationError as e:
                messages.error(request, f"Error creating person: {e}")
        
        elif action == 'skip':
            # User wants to skip (use as-is, will create automatically)
            tagged_name = f"{remove_tags(current_person_name)} [id:0]"
            workflow.resolve_current_person(tagged_name)
            
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
        'field_name': workflow.get_field_name(),
        'step_number': workflow.session['person_workflow']['current_step'] + 1,
        'total_steps': len(workflow.session['person_workflow']['pending_persons'])
    }
    
    return render(request, 'publications/person_disambiguation_step.html', context)


@login_required
def complete_person_workflow(request):
    """Complete the person workflow and return to original form"""
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
    
    # Reconstruct the field with resolved person names
    original_names = original_form_data.getlist(field_name) if hasattr(original_form_data, 'getlist') else original_form_data.get(field_name, [])
    if isinstance(original_names, str):
        original_names = [original_names]
    
    for name in original_names:
        if name in resolved_persons:
            resolved_names.append(resolved_persons[name])
        else:
            resolved_names.append(name)  # Already resolved or doesn't need resolution
    
    updated_form_data[field_name] = resolved_names
    
    # Store updated form data in session for the main form
    request.session['updated_form_data'] = dict(updated_form_data)
    request.session.modified = True
    
    # Clear workflow
    workflow.clear_workflow()
    
    messages.success(request, f"Person disambiguation complete for {field_name}.")
    
    # Redirect back to the form that initiated the workflow
    return redirect('publications:add_publication')
