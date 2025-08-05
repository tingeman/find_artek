"""
AJAX views for person disambiguation and creation.
Based on the legacy Django 1.6 implementation.
"""
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from publications.models import Person
from publications.forms import AddPersonForm
import re


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


def get_person_matches(name_string, exact=True, relaxed=True):
    """
    Find person matches in database.
    Returns (queryset, match_type) tuple.
    """
    clean_name = remove_tags(name_string).strip()
    
    if not clean_name:
        return (Person.objects.none(), None)
    
    # Try exact match first
    if exact:
        exact_matches = Person.objects.filter(name__iexact=clean_name)
        if exact_matches.exists():
            return (exact_matches, 'db_exact')
    
    # Try relaxed match (split on common separators)
    if relaxed:
        name_parts = re.split(r'[,\s]+', clean_name)
        if len(name_parts) >= 2:
            # Try matching first and last name components
            first_part = name_parts[0].strip()
            last_part = name_parts[-1].strip()
            
            relaxed_matches = Person.objects.filter(
                name__icontains=first_part
            ).filter(
                name__icontains=last_part
            )
            
            if relaxed_matches.exists():
                return (relaxed_matches, 'db_relaxed')
    
    return (Person.objects.none(), None)


@require_http_methods(["GET"])
@login_required
def check_person_ajax(request):
    """
    AJAX endpoint to check person names and provide disambiguation options.
    Based on legacy check_person_ajax view.
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'AJAX requests only'}, status=400)
    
    def process_field(field_name):
        """Process a field (authors, supervisors, etc.) and return disambiguation data"""
        persons_needing_choice = []
        
        for name in request.GET.getlist(f'{field_name}[]'):
            if not name.strip():
                continue
                
            # Check if name has an ID tag
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
            
            # No valid ID tag, need to check for matches
            matches, match_type = get_person_matches(name)
            
            if match_type:
                # Found matches - need user choice
                person_data = {
                    'name': name,
                    'p_exact': list(matches) if match_type == 'db_exact' else [],
                    'p_relaxed': list(matches) if match_type == 'db_relaxed' else [],
                    'p_ldap': []  # LDAP not implemented in modern version
                }
                persons_needing_choice.append(person_data)
            else:
                # No matches - will create new person
                person_data = {
                    'name': name,
                    'p_exact': [],
                    'p_relaxed': [],
                    'p_ldap': []
                }
                persons_needing_choice.append(person_data)
        
        if persons_needing_choice:
            # Render disambiguation form
            context = {
                'name_field': field_name,
                'persons': persons_needing_choice
            }
            html = render_to_string(
                'publications/ajax/choose_person_form.html',
                {'data': context},
                request=request
            )
            return {'html': html, 'message': 'choice_needed'}
        else:
            # All persons are valid
            return {'html': '', 'message': 'ok'}
    
    response = {}
    
    # Process each field type
    if 'authors[]' in request.GET:
        response['authors'] = process_field('authors')
    if 'supervisors[]' in request.GET:
        response['supervisors'] = process_field('supervisors')
    if 'editors[]' in request.GET:
        response['editors'] = process_field('editors')
    
    if not response:
        return JsonResponse({'error': 'No person fields specified'}, status=400)
    
    return JsonResponse(response)


@require_http_methods(["POST"])
@login_required
def add_person_ajax(request):
    """
    AJAX endpoint to create new persons.
    Based on legacy add_person_ajax view.
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'AJAX requests only'}, status=400)
    
    form = AddPersonForm(request.POST)
    
    if form.is_valid():
        person = form.save(commit=False)
        person.created_by = request.user
        person.modified_by = request.user
        person.save()
        
        return JsonResponse({
            'success': f'Person "{person.name}" created successfully with ID {person.id}',
            'person_id': person.id,
            'person_name': person.name
        })
    else:
        return JsonResponse({
            'error': 'Form validation failed',
            'errors': form.errors
        }, status=400)
