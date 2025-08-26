>>prompt

My person-disambiguation workflow has become very complex, and spread across several views, forms and helper modules (mixins, workflows etc.)

I would like to consolidate and improve the structure of the code, without changing the functionality.

I have started this process by implementing utils_person.NameNormalizer class and workflows.person_disambiguation.PersonMatcher class. And there is a boilerplate class for a PersonDisambiguationService (workflows.person_disambiguation.PersonDisambiguationService)

Please inspect the existing code in views, forms, mixins and workflow/person.py to understand the current implementation of the person disambiguation workflow.

Then suggest a strategy (building on the NameNormalizer, PersonMatcher and PersonDisambiguationService) for improving the code.








tingeman: My person-disambiguation workflow has become very complex, and spread across several views, forms and helper modules (mixins, workflows etc.)

I would like to consolidate and improve the structure of the code, without changing the functionality.

I have started this process by implementing utils_person.NameNormalizer class and workflows.person_disambiguation.PersonMatcher class. And there is a boilerplate class for a PersonDisambiguationService (workflows.person_disambiguation.PersonDisambiguationService)

Please inspect the existing code in views, forms, mixins and workflow/person.py to understand the current implementation of the person disambiguation workflow.

Then suggest a strategy (building on the NameNormalizer, PersonMatcher and PersonDisambiguationService) for improving the code.

GitHub Copilot: 

tingeman: My person-disambiguation workflow has become very complex, and spread across several views, forms and helper modules (mixins, workflows etc.)

I would like to consolidate and improve the structure of the code, without changing the functionality.

I have started this process by implementing utils_person.NameNormalizer class and workflows.person_disambiguation.PersonMatcher class. And there is a boilerplate class for a PersonDisambiguationService (workflows.person_disambiguation.PersonDisambiguationService)

Please inspect the existing code in views, forms, mixins and workflow/person.py to understand the current implementation of the person disambiguation workflow.

Then suggest a strategy (building on the NameNormalizer, PersonMatcher and PersonDisambiguationService) for improving the code.

GitHub Copilot: 

tingeman: My person-disambiguation workflow has become very complex, and spread across several views, forms and helper modules (mixins, workflows etc.)

I would like to consolidate and improve the structure of the code, without changing the functionality.

I have started this process by implementing utils_person.NameNormalizer class and workflows.person_disambiguation.PersonMatcher class. And there is a boilerplate class for a PersonDisambiguationService (workflows.person_disambiguation.PersonDisambiguationService)

Please inspect the existing code in views, forms, mixins and workflow/person.py to understand the current implementation of the person disambiguation workflow.

Then suggest a strategy (building on the NameNormalizer, PersonMatcher and PersonDisambiguationService) for improving the code.

GitHub Copilot: # Strategy for Consolidating Person Disambiguation Workflow

After reviewing your code, I can see you've begun improving the architecture with the `NameNormalizer`, `PersonMatcher`, and skeleton `PersonDisambiguationService` classes. The current implementation is spread across multiple components, with complex interactions between views, forms, mixins, and workflow modules.

## Current Architecture Issues

1. **Distributed Logic**: Person disambiguation code is scattered across multiple modules
2. **Complex Session Management**: State management through Django sessions is difficult to trace
3. **Inconsistent Patterns**: Different approaches for similar functionality
4. **Tight Coupling**: Forms, views, and workflow code are tightly interdependent

## Consolidation Strategy

I recommend building a cohesive service-based architecture with the `PersonDisambiguationService` as the central component:

### 1. Complete PersonDisambiguationService Implementation

Build out the `PersonDisambiguationService` as a comprehensive service for handling all person disambiguation:

tingeman: Done (see workflows/person_disambiguation.py)
tingeman: TODO still need to remove old service from workflows/person.py

```python
class PersonDisambiguationService:
    """
    A service for handling the person disambiguation workflow.
    
    This service manages the state of the disambiguation workflow in the session
    and provides methods for resolving person name ambiguities.
    """
    
    def __init__(self, request):
        """Initialize with a request object to access the session."""
        self.request = request
        self.session = request.session
        self.matcher = PersonMatcher()
        self._ensure_workflow_session()
    
    def _ensure_workflow_session(self):
        """Initialize workflow session if not exists"""
        if 'person_workflow' not in self.session:
            self.session['person_workflow'] = {
                'pending_persons': [],
                'resolved_persons': {},
                'original_form_data': {},
                'current_step': 0,
                'field_name': None,
                'source_url': None
            }
    
    def start_workflow(self, field_name, person_names, original_form_data, source_url=None):
        """
        Start new disambiguation workflow for a field.
        
        Args:
            field_name: Name of the field containing person data (e.g., 'authors')
            person_names: List of person names to disambiguate
            original_form_data: Original form data to update with resolved persons
            source_url: URL to return to after workflow completion
        """
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
        """Get the current person name being processed"""
        workflow = self.session['person_workflow']
        step = workflow['current_step']
        pending = workflow['pending_persons']
        
        if step < len(pending):
            return pending[step]
        return None
    
    def get_current_step_info(self):
        """Get information about the current step"""
        workflow = self.session['person_workflow']
        current_step = workflow['current_step']
        total_steps = len(workflow['pending_persons'])
        
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
        workflow = self.session['person_workflow']
        current_person = self.get_current_person()
        
        if current_person:
            workflow['resolved_persons'][current_person] = resolution_data
            workflow['current_step'] += 1
            self.session.modified = True
    
    def is_workflow_active(self):
        """Check if a workflow is currently active"""
        return 'person_workflow' in self.session and self.session['person_workflow']['pending_persons']
    
    def is_workflow_complete(self):
        """Check if all steps in the workflow are complete"""
        if not self.is_workflow_active():
            return False
            
        workflow = self.session['person_workflow']
        return workflow['current_step'] >= len(workflow['pending_persons'])
    
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
            if self._is_already_resolved(name):
                continue
                
            # Check if matches exist
            matches = self.matcher.find_matches(name)
            names_needing_resolution.append(name)
            
        return names_needing_resolution
    
    def _extract_raw_person_data(self, form_data, field_name):
        """Extract raw person data from form data, handling various formats"""
        import ast
        
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
            
        # Process each value, handling potential nested structures
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
                    # If parsing fails, treat as normal string
                    processed_values.append(value)
            else:
                # Regular value
                processed_values.append(value)
                
        return processed_values
    
    def _is_already_resolved(self, name):
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
                from publications.models import Person
                Person.objects.get(id=id_tag)
                return True
            except Person.DoesNotExist:
                return False
                
        # Check if name is a numeric ID
        if name.isdigit():
            try:
                from publications.models import Person
                Person.objects.get(id=int(name))
                return True
            except Person.DoesNotExist:
                return False
                
        return False
    
    def _get_tag(self, string, tag_name):
        """Extract tag value from string like '[id:123]' -> 123"""
        import re
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
    
    def _remove_tags(self, string):
        """Remove all tags like '[id:123]' from string"""
        import re
        return re.sub(r'\[[^\]]+\]', '', string).strip()
    
    def update_form_data_with_resolved_persons(self):
        """
        Update form data with resolved persons.
        
        Returns:
            Updated form data dictionary
        """
        if not self.is_workflow_complete():
            return None
            
        workflow = self.session['person_workflow']
        resolved_persons = workflow['resolved_persons']
        original_form_data = workflow['original_form_data']
        field_name = workflow['field_name']
        
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
        Complete the workflow and prepare form data for form submission.
        
        Returns:
            Tuple of (updated_form_data, redirect_url)
        """
        if not self.is_workflow_complete():
            return None, None
            
        # Get updated form data
        updated_form_data = self.update_form_data_with_resolved_persons()
        
        # Store in session for the form to access
        self.request.session['updated_form_data'] = updated_form_data
        self.request.session['workflow_updated_field'] = self.session['person_workflow']['field_name']
        self.request.session.modified = True
        
        # Get redirect URL
        redirect_url = self.session['person_workflow']['source_url']
        
        # Determine specific redirect URL based on context
        import re
        if '/report/' in redirect_url and '/edit/' in redirect_url:
            match = re.search(r'/report/(\d+)/edit/', redirect_url)
            if match:
                publication_id = match.group(1)
                from django.urls import reverse
                redirect_url = reverse('publications:edit_report_review', kwargs={'pk': publication_id})
        elif '/add/' in redirect_url:
            from django.urls import reverse
            redirect_url = reverse('publications:add_report_review')
        
        # Clear workflow
        self.clear_workflow()
        
        return updated_form_data, redirect_url
    
    def clear_workflow(self):
        """Clear the workflow from session"""
        if 'person_workflow' in self.session:
            del self.session['person_workflow']
            self.session.modified = True
```

### 2. Create a Simplified WorkflowMixin

Replace the complex `PersonWorkflowMixin` with a simplified version that uses the service:

tingeman: DONE (see workflows/person_disambiguation.py)
tingeman: TODO still need to remove old mixin from forms/mixins.py


```python
class PersonDisambiguationMixin:
    """
    Mixin for forms that need person disambiguation.
    
    This mixin provides methods for handling person disambiguation workflow
    and integrates with the PersonDisambiguationService.
    """
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Initialize service if request is available
        self.person_service = None
        if self.request:
            from publications.workflows.person_disambiguation import PersonDisambiguationService
            self.person_service = PersonDisambiguationService(self.request)
    
    def clean(self):
        """Process any completed workflow data from session"""
        cleaned_data = super().clean()
        
        # Skip if no request or service
        if not self.request or not self.person_service:
            return cleaned_data
        
        # Check if we have updated form data from completed workflow
        if 'updated_form_data' in self.request.session:
            updated_data = self.request.session.pop('updated_form_data')
            field_name = self.request.session.get('workflow_updated_field')
            
            # Update the cleaned data with resolved person IDs
            if field_name in self.fields and field_name in updated_data:
                self._process_workflow_result(cleaned_data, field_name, updated_data[field_name])
        
        return cleaned_data
    
    def _process_workflow_result(self, cleaned_data, field_name, resolved_values):
        """Process resolved values from workflow and update cleaned_data"""
        # Convert string IDs to Person objects
        from publications.models import Person
        from publications.utils_models import create_ordered_queryset
        
        person_ids = []
        for value in resolved_values:
            if isinstance(value, str):
                if value.startswith('CREATE:'):
                    # Create new person
                    person_name = value[7:]
                    person = Person(created_by=self.request.user, modified_by=self.request.user)
                    person.set_names(person_name)
                    person.save()
                    person_ids.append(person.pk)
                elif value.isdigit():
                    # Existing person ID
                    person_ids.append(int(value))
            elif hasattr(value, 'pk'):
                # Person object
                person_ids.append(value.pk)
        
        # Create queryset if we have person IDs
        if person_ids:
            cleaned_data[field_name] = create_ordered_queryset(Person, person_ids)
    
    def check_disambiguation_needed(self, field_name):
        """
        Check if person disambiguation is needed for a field.
        
        Args:
            field_name: Name of the field to check
            
        Returns:
            True if disambiguation is needed, False otherwise
        """
        if not self.request or not self.person_service:
            return False
            
        # Get field data from cleaned_data
        field_data = self.cleaned_data.get(field_name, [])
        
        # Skip if empty or already a QuerySet
        from django.db.models import QuerySet
        if not field_data or isinstance(field_data, QuerySet):
            return False
            
        # Check if any names need disambiguation
        names_needing_resolution = self.person_service.extract_persons_needing_disambiguation(
            MockFormData(field_data), field_name
        )
        
        return bool(names_needing_resolution)
    
    def start_disambiguation_workflow(self, field_name):
        """
        Start person disambiguation workflow for a field.
        
        Args:
            field_name: Name of the field to disambiguate
            
        Returns:
            Redirect response to disambiguation step or None if no workflow needed
        """
        if not self.request or not self.person_service:
            return None
            
        # Get field data from cleaned_data
        field_data = self.cleaned_data.get(field_name, [])
        
        # Extract names needing disambiguation
        names_needing_resolution = self.person_service.extract_persons_needing_disambiguation(
            MockFormData(field_data), field_name
        )
        
        if not names_needing_resolution:
            return None
            
        # Start workflow
        self.person_service.start_workflow(
            field_name,
            names_needing_resolution,
            dict(self.request.POST),  # Use raw POST data
            self.request.path
        )
        
        # Return redirect to disambiguation step
        from django.shortcuts import redirect
        return redirect('publications:disambiguate_person_step')
    
    def has_workflow_redirect(self):
        """Check if form has a workflow redirect"""
        return hasattr(self, '_workflow_redirect') and self._workflow_redirect is not None
    
    def get_workflow_redirect(self):
        """Get the workflow redirect response"""
        return getattr(self, '_workflow_redirect', None)
```

### 3. Simplified View for Disambiguation

Replace the current disambiguation view with a simplified version:


tingeman: TODO I want this as a class based view, like everything else. Is it identical to the existing view? No it is not identical... But should be refactored to class based view!
tingeman: TODO Where does this view live best? In views.py? In workflow/person_diambiguation.py?

```python
@login_required
def disambiguate_person_step(request):
    """
    Handle a single step in the person disambiguation workflow.
    
    This view shows the disambiguation form for the current person,
    processes selections, and advances to the next step or completes
    the workflow.
    """
    from publications.workflows.person_disambiguation import PersonDisambiguationService
    
    # Initialize service
    service = PersonDisambiguationService(request)
    # request contains session data, which holds information about any active disambiguation workflow.

    # Check if workflow is active
    if not service.is_workflow_active():
        messages.error(request, "No active disambiguation workflow.")
        return redirect('publications:add_report')    # TODO: where should we redirect to? I don't think it should be add_report...? The service should provide this information!
    
    # Get current person name
    current_person = service.get_current_person()
    if not current_person:
        messages.error(request, "No person to disambiguate.")
        return redirect('publications:add_report')    # TODO: where should we redirect to? I don't think it should be add_report...? The service should provide this information!
    
    # Process POST request
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'select_existing':
            # User selected an existing person
            person_id = request.POST.get('person_id')
            if person_id:
                service.resolve_current_person(person_id)
                
                if service.is_workflow_complete():
                    return redirect('publications:complete_person_workflow')
                else:
                    return redirect('publications:disambiguate_person_step')
            else:
                messages.error(request, "No person selected.")
        
        elif action == 'create_new':
            # User wants to create a new person
            from publications.models import Person
            
            person_name = service._remove_tags(current_person)
            try:
                # Create new person
                person = Person(created_by=request.user, modified_by=request.user)
                person.set_names(person_name)
                person.save()
                
                # Store CREATE: marker for form processing
                service.resolve_current_person(f"CREATE:{person_name}")
                
                messages.success(request, f'Created new person: {person.get_full_name()}')
                

                # TODO: Code deduplication needed, move this outside if-else block
                if service.is_workflow_complete():
                    return redirect('publications:complete_person_workflow')
                else:
                    return redirect('publications:disambiguate_person_step')
            except Exception as e:
                messages.error(request, f"Error creating person: {e}")
        
        elif action == 'skip':
            # User wants to skip this name
            service.resolve_current_person(f"SKIP:{current_person}")
            
            if service.is_workflow_complete():
                return redirect('publications:complete_person_workflow')
            else:
                return redirect('publications:disambiguate_person_step')
    
    # GET request - show disambiguation form
    matches = service.get_matches_for_current_person()
    clean_name = service._remove_tags(current_person)    # TODO: Shouldn't we use clean_name method of NameNormalizer? And this was already done somewhere in get_matches_for_current_person. Why do we have to do it again?

    step_info = service.get_current_step_info()
    
    context = {
        'current_person_name': current_person,
        'clean_name': clean_name,
        'matches': matches,
        'field_name': service.session['person_workflow']['field_name'],
        'step_number': step_info['current_step'],
        'total_steps': step_info['total_steps'],
        'progress_percent': step_info['progress_percent']
    }
    
    return render(request, 'publications/person_disambiguation_step.html', context)
```

tingeman: TODO I want this as a class based view, like everything else. Is it identical to the existing view? No it is not identical... But should be refactored to class based view!
tingeman: TODO Where does this view live best? In views.py? In workflow/person_diambiguation.py?


```python
@login_required
def complete_person_workflow(request):
    """
    Complete the person disambiguation workflow.
    
    This view finalizes the workflow, updates the form data with
    resolved persons, and redirects back to the form.
    """
    from publications.workflows.person_disambiguation import PersonDisambiguationService
    
    # Initialize service
    service = PersonDisambiguationService(request)
    
    # Check if workflow is complete
    if not service.is_workflow_complete():
        messages.error(request, "Workflow not complete.")
        return redirect('publications:disambiguate_person_step')
    
    # Finalize workflow and get redirect URL
    updated_form_data, redirect_url = service.finalize_workflow()
    
    if not redirect_url:
        # Fallback to frontpage
        messages.error(request, "Error completing workflow.")
        return redirect('publications:frontpage')
    
    messages.success(request, "Person disambiguation complete.")
    return redirect(redirect_url)
```

### 4. Update Person Matcher Methods

Make sure the `PersonMatcher` class is fully implemented with comprehensive matching logic:

```python
class PersonMatcher:
    """
    A class for matching person names to database records.
    
    This class provides methods for finding potential matches for a person name,
    using a variety of matching strategies from exact matches to fuzzy matching.
    """
    
    def __init__(self):
        """Initialize with default settings"""
        from publications.utils_person import NameNormalizer
        self.normalizer = NameNormalizer()
        self.confidence_threshold = 0.5
    

    # tingeman: This method already exists
    def find_matches(self, searchstr: str) -> List[Dict[str, Any]]:
        """
        Find potential matches for a person name.
        
        Args:
            searchstr: The string to search for (name, ID, email, etc.)
            
        Returns:
            List of dictionaries with match information
        """
        # Initialize results
        results = []
        
        # Check for special formats
        if self._is_studynumber(searchstr):
            results.extend(self._match_by_studynumber(searchstr))
        elif self._is_initials(searchstr):
            results.extend(self._match_by_initials(searchstr))
        elif self._is_email(searchstr):
            results.extend(self._match_by_email(searchstr))
        
        # Always try name matching
        results.extend(self._match_by_namestring(searchstr))
        
        # Add relaxed name matching
        results.extend(self._match_by_relaxed_namestring(searchstr))
        
        # Filter by confidence threshold
        results = [r for r in results if r['confidence'] >= self.confidence_threshold]
        
        # Sort by confidence (descending)
        results.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Keep only the highest confidence result for each unique person
        unique_results = []
        seen_ids = set()
        for result in results:
            person_id = result['person'].pk
            if person_id not in seen_ids:
                seen_ids.add(person_id)
                unique_results.append(result)
        
        return unique_results
    
    # tingeman: This method already exists
    def get_best_match(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get the best match for a given person name.
        
        Args:
            name: The person name to match
            
        Returns:
            Dictionary with best match info or None if no match found
        """
        matches = self.find_matches(name)
        return matches[0] if matches else None
    
    # tingeman: This method already exists.
    def is_new_person(self, name: str) -> bool:
        """
        Check if a name likely refers to a new person (no good matches).
        
        Args:
            name: The person name to check
            
        Returns:
            True if the person is likely new, False otherwise
        """
        best_match = self.get_best_match(name)
        # If no match or low confidence match, it's likely a new person
        return not best_match or best_match['confidence'] < 0.8
```

### 5. Template Updates

Update the person disambiguation template to work with the new service:

tingeman: TODO needs checking/updating of template.


```html
{% extends "publications/base.html" %}

{% block content %}
<div class="container">
    <h1>Person Disambiguation</h1>
    
    <div class="progress mb-3">
        <div class="progress-bar" role="progressbar" style="width: {{ progress_percent }}%;" 
             aria-valuenow="{{ progress_percent }}" aria-valuemin="0" aria-valuemax="100">
            Step {{ step_number }} of {{ total_steps }}
        </div>
    </div>
    
    <div class="card mb-4">
        <div class="card-header">
            <h5>Resolving: {{ field_name|title }}</h5>
        </div>
        <div class="card-body">
            <h3>{{ clean_name }}</h3>
            <p class="text-muted">Please select an existing person, create a new person, or skip this name.</p>
            
            <form method="post" action="{% url 'publications:disambiguate_person_step' %}">
                {% csrf_token %}
                
                {% if matches %}
                <div class="mb-4">
                    <h4>Potential Matches</h4>
                    <div class="list-group">
                        {% for match in matches %}
                        <div class="list-group-item">
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="person_id" 
                                       id="person_{{ match.person.pk }}" value="{{ match.person.pk }}">
                                <label class="form-check-label" for="person_{{ match.person.pk }}">
                                    <strong>{{ match.person.get_full_name }}</strong>
                                    <span class="badge bg-primary">{{ match.confidence|floatformat:0 }}%</span>
                                    <small class="text-muted">({{ match.match_type }})</small>
                                    {% if match.person.email %}
                                    <br><small>Email: {{ match.person.email }}</small>
                                    {% endif %}
                                    {% if match.person.id_number %}
                                    <br><small>ID: {{ match.person.id_number }}</small>
                                    {% endif %}
                                </label>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                    
                    <button type="submit" name="action" value="select_existing" 
                            class="btn btn-primary mt-3">
                        Select Existing Person
                    </button>
                </div>
                {% else %}
                <div class="alert alert-info">
                    No matching persons found in the database.
                </div>
                {% endif %}
                
                <div class="card mb-3">
                    <div class="card-header">
                        <h5>Create New Person</h5>
                    </div>
                    <div class="card-body">
                        <p>Create a new person with name: <strong>{{ clean_name }}</strong></p>
                        <button type="submit" name="action" value="create_new" 
                                class="btn btn-success">
                            Create New Person
                        </button>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <h5>Skip This Name</h5>
                    </div>
                    <div class="card-body">
                        <p>If this isn't a person or you want to handle it manually later.</p>
                        <button type="submit" name="action" value="skip" 
                                class="btn btn-secondary">
                            Skip
                        </button>
                    </div>
                </div>
            </form>
        </div>
    </div>
</div>
{% endblock %}
```

### 6. Form Integration

Update your report forms to use the new simplified mixin:

tingeman: TODO is this a full form implementation? No, I think not...

```python
from publications.forms.mixins import PersonDisambiguationMixin

class WorkflowAddEditReportForm(PersonDisambiguationMixin, AddEditReportForm):
    """
    Enhanced AddEditReportForm with person disambiguation workflow.
    """
    
    # TODO: how does this work in practice...?
    #       - clean_authors is called and initiates workflow for authors field?


    def clean_authors(self):
        """Enhanced clean_authors with workflow support"""
        authors_data = super().clean_authors()
        
        # Skip if no service
        if not hasattr(self, 'person_service') or not self.person_service:
            return authors_data
        
        # TODO: Consider if we should always just start the workflow.
        #       It could just return None for the redirect url if nothing to do.

        # Check if disambiguation is needed
        if self.check_disambiguation_needed('authors'):
            self._workflow_redirect = self.start_disambiguation_workflow('authors')
            # If disambiguation is needed, _workflow_redirect holds the redirect to the disambiguation view

        return authors_data
    
    def clean_supervisors(self):
        """Enhanced clean_supervisors with workflow support"""
        supervisors_data = super().clean_supervisors()
        
        # Skip if no service
        if not hasattr(self, 'person_service') or not self.person_service:
            return supervisors_data
        
        # TODO: Will this new call to start_disambiguation_workflow overwrite the session data for person_workflow
        #       and thus loose the state of the author workflow?

        # TODO: Where/when is the _workflow_redirect attribute accessed?

        # Check if disambiguation is needed
        if self.check_disambiguation_needed('supervisors'):
            self._workflow_redirect = self.start_disambiguation_workflow('supervisors')
        
        return supervisors_data
```

## Implementation Plan

1. **Phase 1**: Complete the `PersonDisambiguationService` implementation
2. **Phase 2**: Create the simplified `PersonDisambiguationMixin`
3. **Phase 3**: Update the disambiguation views
4. **Phase 4**: Update forms to use the new mixin
5. **Phase 5**: Test thoroughly with real data
6. **Phase 6**: Clean up legacy code once the new system is verified

## Benefits of This Approach

1. **Centralized Logic**: All disambiguation code in the service class
2. **Cleaner Interface**: Simple, consistent API for views and forms
3. **Reduced Coupling**: Service handles all session management details
4. **Maintainability**: Easier to modify, test, and extend
5. **Future-Proofing**: Could evolve into a Django app or third-party package

This approach maintains all existing functionality while significantly improving code organization. The `PersonDisambiguationService` becomes the central component, with forms and views as simple clients of the service.

tingeman: Please explain in simple terms (without code) the flow of the suggested disambiguation workflow.
Which views/classes/functions are responsible for what, and in which order?

GitHub Copilot: # Person Disambiguation Workflow Flow

Here's a simple explanation of the suggested workflow without code:

## Key Components

1. **PersonDisambiguationService** - The central service that manages the entire workflow
2. **PersonMatcher** - Responsible for finding potential matches for person names
3. **NameNormalizer** - Handles name standardization and character normalization
4. **PersonDisambiguationMixin** - Connects forms to the disambiguation service
5. **Disambiguation Views** - Handle user interface for resolving ambiguous names

## Flow of the Workflow

### 1. Form Submission
- User submits a form containing person names (authors, supervisors, etc.)
- The form (with PersonDisambiguationMixin) processes the submission

### 2. Ambiguity Detection
- The form's clean methods check if any person names need disambiguation
- PersonDisambiguationMixin calls the service's `extract_persons_needing_disambiguation` method
- If ambiguous names are found, the form saves the current state and redirects to disambiguation

### 3. Disambiguation Interface
- The `disambiguate_person_step` view displays options for the current ambiguous name
- PersonMatcher finds potential matches in the database
- User is presented with three options:
  - Select an existing person from matches
  - Create a new person record
  - Skip this name

### 4. Step-by-Step Resolution
- For each ambiguous name, the user makes a selection
- The service stores each decision in the session
- After each decision, the view redirects to either:
  - The next ambiguous name (if more exist)
  - The completion view (if all names are resolved)

### 5. Workflow Completion
- The `complete_person_workflow` view finalizes the process
- The service updates the original form data with resolved person selections
- User is redirected back to the original form
- The form resumes processing with the disambiguated person data

### 6. Form Completion
- The form processes the now-unambiguous data
- Normal form validation and submission continues

## Order of Operations

1. Form is submitted → `clean_authors`/`clean_supervisors` methods called
2. Mixin detects ambiguity → Starts workflow → Redirects to disambiguation
3. User resolves names one by one through the disambiguation interface
4. After all names are resolved → Workflow completes → Returns to form
5. Form processes the resolved data and completes submission

This service-based approach centralizes the disambiguation logic in the PersonDisambiguationService, with other components having clear, focused responsibilities. The workflow maintains state in the session between steps, allowing for a seamless user experience across multiple HTTP requests.