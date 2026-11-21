"""Person disambiguation workflow functionality."""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models import QuerySet
from publications import utils_person
from publications.models import STUDY_NUMBER_RE, Person
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
        """The choices per field: {field_name: {typed name: pk, 'CREATE:<name>', 'LDAP:...' or
        'SKIP:<name>'}}"""
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


# --- DTU directory (AD/LDAP) lookup in the step (plan release-2026-7 T12) --------------------
#
# A typed study number or initials is also looked up in the DTU directory (USE_LDAP on). A hit
# that is not in the database yet is offered as an extra choice; choosing it stores the marker
# 'LDAP:<identifier>:<name>' (identifier: the entry's study number or initials; name: for the
# review page). Nothing is created before the report is saved: person_from_form_value asks the
# directory again and uses utils_person.get_or_create_person_from_ldap. A hit that is already
# in the database (same identifiers, as get_or_create_person_from_ldap matches them) is not
# offered as a new person: the database person is shown, marked as found in the directory.

DIRECTORY_PREFIX = 'LDAP:'
# Initials typed instead of a name: 2-6 ASCII letters and nothing else (no directory query for
# names with spaces, and nothing that would need escaping in an LDAP filter).
INITIALS_RE = re.compile(r'^[A-Za-z]{2,6}$')


class DirectoryLookupError(Exception):
    """The directory could not be asked (USE_LDAP off, or the lookup failed)."""


class DirectoryPersonError(ValueError):
    """A person chosen from the directory can't be fetched at save; the message is for the
    user (ReportFinalizeView shows it and saves nothing)."""


def directory_query(text):
    """The find_ldap_person arguments for a typed study number ({'name': ...}) or initials
    ({'initials': ...}), after removing tags; None for anything else (e.g. a full name)."""
    word = remove_tags(text or '').strip()
    if STUDY_NUMBER_RE.match(word):
        return {'name': word}
    if INITIALS_RE.match(word):
        return {'initials': word}
    return None


def _entry_value(entry, attribute):
    """An ldap3 entry attribute as a stripped string ('' if missing or empty)."""
    value = getattr(getattr(entry, attribute, None), 'value', None)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    return str(value).strip() if value else ''


def _ask_directory(query):
    """The directory entries for ``query``. Raises DirectoryLookupError when USE_LDAP is off
    or the lookup fails (one WARNING with the exception type only: no personal data)."""
    if not getattr(settings, 'USE_LDAP', False):
        raise DirectoryLookupError('DTU directory lookups are switched off')
    try:
        return list(utils_person.find_ldap_person(**query) or [])
    except Exception as exc:
        logger.warning('Person workflow: DTU directory lookup failed (%s)', type(exc).__name__)
        raise DirectoryLookupError('the DTU directory could not be reached') from exc


def _directory_hits(query, entries, user):
    """The usable entries (the searched identifier and a name) as dicts for the step page:
    identifier, name ('Given Surname'), position, department (no e-mail), ``person``: the
    Person in the database with the same identifiers (get_or_create_person_from_ldap without
    saving) or None, and the ldap3 ``entry``."""
    attribute = next(iter(query))
    hits = []
    for entry in entries:
        identifier = _entry_value(entry, attribute)
        name = ' '.join(part for part in (_entry_value(entry, 'givenName'),
                                          _entry_value(entry, 'sn')) if part)
        if not name or identifier.lower() != query[attribute].lower():
            continue
        info = utils_person.get_person_info_from_ldap_object(entry)
        person = utils_person.get_or_create_person_from_ldap(
            ldap_object=entry, user=user, save=False)[0]
        hits.append({
            'identifier': identifier,
            'name': name,
            'position': info.get('position', ''),
            'department': info.get('department', ''),
            'person': person if person.pk else None,
            'entry': entry,
        })
    return hits


def directory_hits(text, user):
    """The DTU directory entries for a typed study number or initials (_directory_hits);
    [] for other text, with USE_LDAP off, when the lookup fails, or without a hit."""
    query = directory_query(text)
    if query is None:
        return []
    try:
        return _directory_hits(query, _ask_directory(query), user)
    except DirectoryLookupError:
        return []


def directory_marker(identifier, name):
    """The report form value of a person chosen from the directory."""
    return f'{DIRECTORY_PREFIX}{identifier}:{name}'


def parse_directory_marker(value):
    """(identifier, name) of an 'LDAP:<identifier>:<name>' value, else None."""
    if not (isinstance(value, str) and value.startswith(DIRECTORY_PREFIX)):
        return None
    identifier, _, name = value[len(DIRECTORY_PREFIX):].partition(':')
    return identifier.strip(), name.strip()


def person_from_directory(value, user):
    """The Person for an 'LDAP:' value, at save: the entry is fetched from the directory again
    and get_or_create_person_from_ldap reuses a person with the same identifiers or creates
    one (name parts, initials / id_number, position, department; created_by ``user``).
    Raises DirectoryPersonError, with a message for the user, when the identifier is not a
    study number or initials, the directory can't be asked, or it no longer has the entry."""
    identifier, name = parse_directory_marker(value)
    label = f'"{name}" ({identifier})' if name else f'"{identifier}"'
    query = directory_query(identifier)
    if query is None:
        raise DirectoryPersonError(
            f'{label} is not a study number or initials for the DTU directory.')
    try:
        hits = _directory_hits(query, _ask_directory(query), user)
    except DirectoryLookupError as exc:
        raise DirectoryPersonError(
            f'{label} could not be fetched: {exc}. Please try again later, or go back to the '
            'form and choose the person again.') from exc
    if not hits:
        raise DirectoryPersonError(
            f'{label} is no longer in the DTU directory. Please go back to the form and choose '
            'the person again.')
    return utils_person.get_or_create_person_from_ldap(ldap_object=hits[0]['entry'],
                                                       user=user)[0]


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
        # (CREATE:, or LDAP: for a person from the DTU directory)
        if name.startswith(('SKIP:', 'CREATE:', DIRECTORY_PREFIX)):
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

        elif action == 'select_directory':
            # A person from the DTU directory: asked again (the page may be old); created
            # when the report is saved (person_from_form_value), as for create_new.
            identifier = request.POST.get('directory_id', '')
            hit = next((h for h in directory_hits(current_person_name, request.user)
                        if h['identifier'] == identifier), None)
            if hit is None:
                messages.error(request, "The DTU directory entry is not available (any more). "
                                        "Please choose another option.")
            else:
                if hit['person'] is not None:
                    # In the database in the meantime: that person, not a duplicate.
                    workflow.resolve_current_person(str(hit['person'].pk))
                else:
                    workflow.resolve_current_person(directory_marker(hit['identifier'],
                                                                     hit['name']))
                    messages.success(request, f'"{hit["name"]}" will be added from the DTU '
                                              'directory when the report is saved.')
                if workflow.is_complete():
                    return redirect('publications:complete_person_workflow')
                return redirect('publications:disambiguate_person_step')

        # The former action 'skip' ("Use As-Is (Create Later)") is gone (decided 2026-11-19):
        # an author or supervisor needs a Person, so it did the same as 'create_new'. Any
        # other action shows the step again. SKIP: markers still in a session are read as
        # CREATE: (person_from_form_value).
    
    # GET request - show disambiguation form
    matches = get_person_matches(current_person_name)
    clean_name = remove_tags(current_person_name)
    exact_matches, relaxed_matches = list(matches['exact']), list(matches['relaxed'])

    # DTU directory hits (typed study number or initials): a new one is an extra choice; one
    # already in the database is that person (added to the matches if missing), marked.
    hits = directory_hits(current_person_name, request.user)
    directory_choices = [hit for hit in hits if hit['person'] is None]
    directory_person_ids = set()
    for hit in hits:
        person = hit['person']
        if person is not None:
            directory_person_ids.add(person.pk)
            if person not in exact_matches and person not in relaxed_matches:
                exact_matches.append(person)

    context = {
        'current_person_name': current_person_name,
        'clean_name': clean_name,
        'exact_matches': exact_matches,
        'relaxed_matches': relaxed_matches,
        'directory_choices': directory_choices,
        'directory_person_ids': directory_person_ids,
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


def person_review_label(value):
    """How the review page shows a person made when the report is saved: 'Name (new person)'
    for CREATE:/SKIP:, 'Name (identifier, from the DTU directory)' for LDAP:; None else."""
    directory = parse_directory_marker(value)
    if directory is not None:
        identifier, name = directory
        return f'{name or identifier} ({identifier}, from the DTU directory)'
    name = person_display_name(value)
    return None if name is None else f'{name} (new person)'


def match_flags(name):
    """The match flags of a link to a new person ``name`` (as the classic app set them), from
    the persons in the database that match the name. Call it before that person is created,
    so it doesn't match itself. exact_match: one or more exact matches; relaxed_match: relaxed
    matches but no exact one; multiple_match: more than one match of the kind that set the flag."""
    matches = get_person_matches(name)
    exact, relaxed = matches['exact'], matches['relaxed']
    return {
        'exact_match': bool(exact),
        'relaxed_match': bool(relaxed) and not exact,
        'multiple_match': len(exact) > 1 or (not exact and len(relaxed) > 1),
    }


def person_from_form_value(value, user, created):
    """The Person for a value of the report form data, and the match flags for its link:
    a pk (no flags, ``{}``), an 'LDAP:' marker (person_from_directory; no flags), or a
    'CREATE:<name>' / 'SKIP:<name>' marker from the workflow
    ("Create New Person"; SKIP: from older form data), for which a new person is created now
    (name parts parsed, created_by ``user``) and the flags come from match_flags.
    ``created`` maps the names already created in this save to (Person, flags), so a name typed
    as author and as supervisor is one person with the same flags. Raises ValueError for an
    unresolved name."""
    directory = parse_directory_marker(value)
    if directory is not None:
        # From the DTU directory (an existing person with the same identifiers is reused):
        # no match flags. Keyed by identifier, so the same entry as author and supervisor is
        # one person and asked once.
        key = DIRECTORY_PREFIX + directory[0].lower()
        if key not in created:
            created[key] = (person_from_directory(value, user), {})
        return created[key]
    name = person_display_name(value)
    if name is None:
        return Person.objects.get(pk=int(value)), {}
    if not name:
        raise ValueError(f'Empty person name in {value!r}')
    if name not in created:
        flags = match_flags(name)  # before the person exists
        person = Person(created_by=user, modified_by=user)
        person.set_names(name)  # saves
        created[name] = (person, flags)
    return created[name]
