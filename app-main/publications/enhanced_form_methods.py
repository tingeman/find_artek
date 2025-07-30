"""
Enhanced form cleaning methods that integrate with the AJAX person disambiguation workflow.
Add these methods to your AddEditReportForm class.
"""

import re
import ast
from django.core.exceptions import ValidationError
from django.contrib import messages


def parse_person_entry(self, entry_str):
    """
    Parse a person entry that might be:
    - A numeric ID: "123"
    - A tagged name: "John Doe [id:456]" 
    - A new person tag: "Jane Smith [id:0]"
    - A plain name: "Bob Johnson"
    
    Returns tuple: (person_obj_or_name, needs_creation)
    """
    entry_str = str(entry_str).strip()
    
    # Check for ID tag like [id:123] or [id:0]
    id_match = re.search(r'\[id:([^\]]+)\]', entry_str)
    
    if id_match:
        id_value = id_match.group(1)
        clean_name = re.sub(r'\[id:[^\]]+\]', '', entry_str).strip()
        
        if id_value == '0':
            # New person to be created
            return (clean_name, True)
        elif id_value.isdigit():
            # Existing person by ID
            try:
                person = Person.objects.get(id=int(id_value))
                return (person, False)
            except Person.DoesNotExist:
                # ID doesn't exist, treat as new person
                return (clean_name, True)
        else:
            # Invalid ID format, treat as new person
            return (clean_name, True)
    
    # Check if it's a plain numeric ID
    if entry_str.isdigit():
        try:
            person = Person.objects.get(id=int(entry_str))
            return (person, False)
        except Person.DoesNotExist:
            raise ValidationError(f"Person with ID {entry_str} does not exist.")
    
    # Plain name without tags - this indicates disambiguation is needed
    return (entry_str, True)


def process_person_field(self, field_data, field_name):
    """
    Process a person field (authors/supervisors) that may contain a mix of:
    - Existing person IDs
    - Names with ID tags from disambiguation
    - Plain names that need disambiguation
    
    Returns: (QuerySet of existing persons, list of names needing creation)
    """
    if not field_data:
        return Person.objects.none(), []
    
    # Parse the input data
    if isinstance(field_data, list):
        entries = [str(item) for item in field_data]
    elif isinstance(field_data, str):
        try:
            # Try to parse as list representation
            entries = ast.literal_eval(field_data)
            if not isinstance(entries, list):
                entries = [str(field_data)]
        except (ValueError, SyntaxError):
            # Split on common separators
            entries = re.split(r'[;&\n]', field_data)
            entries = [e.strip() for e in entries if e.strip()]
    else:
        entries = [str(field_data)]
    
    existing_persons = []
    names_to_create = []
    needs_disambiguation = []
    
    for entry in entries:
        if not entry.strip():
            continue
            
        person_or_name, needs_creation = self.parse_person_entry(entry)
        
        if needs_creation:
            if isinstance(person_or_name, str):
                # Check if this is a plain name that needs disambiguation
                if '[id:' not in entry:
                    needs_disambiguation.append(person_or_name)
                else:
                    # This is a name marked for creation [id:0]
                    names_to_create.append(person_or_name)
        else:
            existing_persons.append(person_or_name)
    
    # If there are names needing disambiguation, raise a special error
    if needs_disambiguation:
        error_msg = (
            f"The following names in {field_name} need disambiguation: "
            f"{', '.join(needs_disambiguation)}. Please use the 'Process Persons' "
            f"button to resolve ambiguous names before submitting."
        )
        raise ValidationError(error_msg, code='disambiguation_needed')
    
    # Create QuerySet for existing persons
    if existing_persons:
        person_ids = [p.id for p in existing_persons]
        existing_queryset = Person.objects.filter(id__in=person_ids)
        # Preserve order
        existing_queryset = create_ordered_queryset(Person, person_ids)
    else:
        existing_queryset = Person.objects.none()
    
    return existing_queryset, names_to_create


def clean_authors(self):
    """Enhanced clean_authors that handles AJAX disambiguation workflow"""
    print(f"AddEditReportForm:clean_authors: {self.cleaned_data['authors']}")
    
    try:
        existing_persons, names_to_create = self.process_person_field(
            self.cleaned_data['authors'], 'authors'
        )
        
        # Store names that need creation for later processing
        if names_to_create:
            self._authors_to_create = names_to_create
            print(f"Authors to create: {names_to_create}")
        
        print(f"Existing authors: {list(existing_persons)}")
        return existing_persons
        
    except ValidationError as e:
        if e.code == 'disambiguation_needed':
            # Add a helpful message about using the Process Persons button
            print(f"Disambiguation needed for authors: {e.message}")
            raise
        else:
            raise


def clean_supervisors(self):
    """Enhanced clean_supervisors that handles AJAX disambiguation workflow"""
    print(f"AddEditReportForm:clean_supervisors: {self.cleaned_data['supervisors']}")
    
    try:
        existing_persons, names_to_create = self.process_person_field(
            self.cleaned_data['supervisors'], 'supervisors'
        )
        
        # Store names that need creation for later processing
        if names_to_create:
            self._supervisors_to_create = names_to_create
            print(f"Supervisors to create: {names_to_create}")
        
        print(f"Existing supervisors: {list(existing_persons)}")
        return existing_persons
        
    except ValidationError as e:
        if e.code == 'disambiguation_needed':
            print(f"Disambiguation needed for supervisors: {e.message}")
            raise
        else:
            raise


def save(self, commit=True):
    """Enhanced save method that creates new persons when needed"""
    # Create any new persons that were marked for creation
    if hasattr(self, '_authors_to_create'):
        for name in self._authors_to_create:
            person, created = Person.objects.get_or_create(
                name=name,
                defaults={
                    'created_by': self.request.user if hasattr(self, 'request') else None,
                    'modified_by': self.request.user if hasattr(self, 'request') else None,
                }
            )
            if created:
                print(f"Created new author: {person}")
                # Add to the authors relationship
                if commit:
                    # We need to handle this after the main object is saved
                    if not hasattr(self, '_new_authors'):
                        self._new_authors = []
                    self._new_authors.append(person)
    
    if hasattr(self, '_supervisors_to_create'):
        for name in self._supervisors_to_create:
            person, created = Person.objects.get_or_create(
                name=name,
                defaults={
                    'created_by': self.request.user if hasattr(self, 'request') else None,
                    'modified_by': self.request.user if hasattr(self, 'request') else None,
                }
            )
            if created:
                print(f"Created new supervisor: {person}")
                if commit:
                    if not hasattr(self, '_new_supervisors'):
                        self._new_supervisors = []
                    self._new_supervisors.append(person)
    
    # Call the original save method
    instance = super().save(commit=commit)
    
    # Add the newly created persons to the relationships
    if commit:
        if hasattr(self, '_new_authors'):
            for person in self._new_authors:
                instance.authors.add(person)
                
        if hasattr(self, '_new_supervisors'):
            for person in self._new_supervisors:
                instance.supervisors.add(person)
    
    return instance
