"""
Person-related forms for publications app.
"""

from django import forms
from django_select2 import forms as s2forms
from publications.models import Person
from pybtex.database import Person as PyBTeXPerson
from django.db.models import Q
import ast
import re


class PersonSelectForm(forms.Form):
    # An abstract class intended for subclassing
    class Meta:
        abstract = True

    person_type = None   # Define in subclass as "author" or "supervisor"

    def __init__(self, *args, persons=None, **kwargs):
        super().__init__(*args, **kwargs)

        if persons is not None:
            # Add a headline in the form, it should be pure text and not a field
            for i, person in enumerate(persons):
                if str(person).isnumeric():  # Assume it's a primary key, this formulation works with both int and str
                    person = Person.objects.get(pk=person)
                    self.fields[f'{self.person_type}_{i}'] = forms.ChoiceField(
                        label=f"{self.person_type.capitalize()} {i + 1}: Exact match on primary key",
                        widget=forms.RadioSelect,
                        choices=[(person.pk, person.get_full_name() + f" [pk:{person.pk}]")],
                        disabled=True,
                    )
                    self.fields[f'{self.person_type}_{i}'].initial = self.fields[f'{self.person_type}_{i}'].choices[0][0]
                else:  # Assume it's a name
                    self.fields[f'{self.person_type}_{i}'] = forms.ChoiceField(
                        label=f"{self.person_type.capitalize()} {i + 1}: Select matching person or create new",
                        choices=self.get_person_choices(person),
                        widget=forms.RadioSelect,
                        required=True,
                    )
                    # Add a "Create New" option
                    self.fields[f'{self.person_type}_{i}'].choices.insert(0, ('create_new', f'{person} (Create new Person)'))
                    # Set first option as selected
                    self.fields[f'{self.person_type}_{i}'].initial = self.fields[f'{self.person_type}_{i}'].choices[0][0]

    def get_person_choices(self, name):
        """Get person choices with enhanced matching and metadata display"""
        matches = self.get_person_matches(name)
        
        # Format choices with additional identifying information
        choices = []
        for match in matches:
            person = match['person']
            confidence = match['confidence']
            match_type = match['match_type']
            
            # Build display string with unique identifiers
            display_parts = [person.get_full_name()]
            
            # Add confidence indicator
            confidence_str = f"{confidence:.0%}"
            display_parts.append(f"({confidence_str})")
            
            # Add unique identifiers
            identifiers = []
            if person.pk:
                identifiers.append(f"pk:{person.pk}")
            if person.email:
                identifiers.append(f"email:{person.email}")
            if person.id_number:
                identifiers.append(f"id:{person.id_number}")
            
            if identifiers:
                display_parts.append(f"[{', '.join(identifiers)}]")
            
            # Add match type if not exact
            if match_type != 'exact_full':
                display_parts.append(f"({match_type})")
            
            display_string = ' '.join(display_parts)
            choices.append((person.pk, display_string))
        
        return choices

    def get_person_matches(self, name_string):
        """Get potential person matches using comprehensive matching strategies"""
        
        # Parse the name using PyBTeX
        parsed_person = PyBTeXPerson(name_string)
        
        # Extract components
        first = ' '.join(parsed_person.first()) if parsed_person.first() else ''
        middle = ' '.join(parsed_person.middle()) if parsed_person.middle() else ''
        prelast = ' '.join(parsed_person.prelast()) if parsed_person.prelast() else ''
        last = ' '.join(parsed_person.last()) if parsed_person.last() else ''
        lineage = ' '.join(parsed_person.lineage()) if parsed_person.lineage() else ''
        
        matches = []
        seen_ids = set()
        
        # Helper function to add match if not already seen
        def add_match(person, match_type, confidence, notes=''):
            if person.id not in seen_ids:
                seen_ids.add(person.id)
                matches.append({
                    'person': person,
                    'match_type': match_type,
                    'confidence': confidence,
                    'notes': notes,
                    'pk': person.pk,
                    'email': person.email,
                    'id_number': person.id_number
                })
        
        # Helper function for special character substitution
        def normalize_name(name):
            """Normalize special characters for matching"""
            substitutions = {
                'ø': 'oe', 'ö': 'oe', 'ü': 'ue', 'ä': 'ae', 'å': 'aa',
                'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
                'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a',
                'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
                'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o',
                'ú': 'u', 'ù': 'u', 'û': 'u',
                'ç': 'c', 'ñ': 'n'
            }
            normalized = name.lower()
            for char, replacement in substitutions.items():
                normalized = normalized.replace(char, replacement)
            return normalized
        
        # Helper function for alternative character substitutions
        def get_name_variants(name):
            """Get multiple variants of a name with different character substitutions"""
            variants = [name.lower()]
            
            # Danish/Norwegian specific substitutions
            variants.append(name.lower().replace('ø', 'oe'))
            variants.append(name.lower().replace('ø', 'o'))
            variants.append(name.lower().replace('æ', 'ae'))
            variants.append(name.lower().replace('æ', 'a'))
            variants.append(name.lower().replace('å', 'aa'))
            variants.append(name.lower().replace('å', 'a'))
            
            # Remove duplicates while preserving order
            seen = set()
            unique_variants = []
            for variant in variants:
                if variant not in seen:
                    seen.add(variant)
                    unique_variants.append(variant)
            
            return unique_variants
        
        # Helper function to check if names are truly identical (case-insensitive only)
        def are_names_identical(search_name, db_name):
            """Check if two names are exactly identical (case-insensitive only)"""
            return search_name.lower().strip() == db_name.lower().strip()
        
        # Helper function to check if names differ only by special characters
        def are_names_character_variants(search_name, db_name):
            """Check if two names differ only by special character substitutions"""
            if are_names_identical(search_name, db_name):
                return False  # They're identical, not variants
            
            # Normalize both and see if they match
            search_normalized = normalize_name(search_name)
            db_normalized = normalize_name(db_name)
            return search_normalized == db_normalized
        
        # Strategy 1: TRUE EXACT match on all name components (case-insensitive but no character substitution)
        if first and last:
            query = Q(first__iexact=first, last__iexact=last)
            if middle:
                query &= Q(middle__iexact=middle)
            if prelast:
                query &= Q(prelast__iexact=prelast)
            if lineage:
                query &= Q(lineage__iexact=lineage)
            
            potential_matches = Person.objects.filter(query)
            for person in potential_matches:
                # Check if it's truly identical (case-insensitive) vs character variant
                person_first = person.first or ''
                person_middle = person.middle or ''
                person_last = person.last or ''
                person_prelast = person.prelast or ''
                person_lineage = person.lineage or ''
                
                # Check if ALL components are case-identical (no character substitution)
                is_case_only_diff = (
                    are_names_identical(first, person_first) and
                    are_names_identical(middle, person_middle) and
                    are_names_identical(last, person_last) and
                    are_names_identical(prelast, person_prelast) and
                    are_names_identical(lineage, person_lineage)
                )
                
                # Check if any component is a character variant
                has_character_variants = (
                    are_names_character_variants(first, person_first) or
                    are_names_character_variants(middle, person_middle) or
                    are_names_character_variants(last, person_last) or
                    are_names_character_variants(prelast, person_prelast) or
                    are_names_character_variants(lineage, person_lineage)
                )
                
                if is_case_only_diff:
                    add_match(person, 'exact_full', 1.0, 'Exact match on all name components')
                elif has_character_variants:
                    add_match(person, 'normalized_full', 0.85, 'Character variant match (full name)')
        
        # Strategy 2: Exact match on first, middle, last (ignoring prelast/lineage)
        if first and last and not any(m['match_type'] in ['exact_full', 'normalized_full'] for m in matches):
            query = Q(first__iexact=first, last__iexact=last)
            if middle:
                query &= Q(middle__iexact=middle)
            
            potential_matches = Person.objects.filter(query)
            for person in potential_matches:
                # Check if core components are case-identical vs character variants
                person_first = person.first or ''
                person_middle = person.middle or ''
                person_last = person.last or ''
                
                is_case_only_diff = (
                    are_names_identical(first, person_first) and
                    are_names_identical(middle, person_middle) and
                    are_names_identical(last, person_last)
                )
                
                has_character_variants = (
                    are_names_character_variants(first, person_first) or
                    are_names_character_variants(middle, person_middle) or
                    are_names_character_variants(last, person_last)
                )
                
                if is_case_only_diff:
                    add_match(person, 'exact_core', 0.95, 'Exact match on core name components')
                elif has_character_variants:
                    add_match(person, 'normalized_core', 0.80, 'Character variant match (core names)')
        
        # Strategy 3: First + Last name matching (exact search)
        if first and last:
            first_last_matches = Person.objects.filter(
                Q(first__iexact=first) & Q(last__iexact=last)
            )
            for person in first_last_matches:
                person_first = person.first or ''
                person_last = person.last or ''
                
                first_is_case_identical = are_names_identical(first, person_first)
                last_is_case_identical = are_names_identical(last, person_last)
                
                first_is_character_variant = are_names_character_variants(first, person_first)
                last_is_character_variant = are_names_character_variants(last, person_last)
                
                if first_is_case_identical and last_is_case_identical:
                    add_match(person, 'exact_first_last', 0.90, 'Exact first + last name match')
                elif (first_is_character_variant or first_is_case_identical) and (last_is_character_variant or last_is_case_identical):
                    add_match(person, 'normalized_first_last', 0.85, 'First + last name character variant match')
        
        # Strategy 4: First + Middle name matching (when last name missing)
        if first and last and not middle:
            # Check if "last" could actually be a middle name
            first_middle_matches = Person.objects.filter(
                Q(first__iexact=first) & Q(middle__iexact=last)
            )
            for person in first_middle_matches:
                person_first = person.first or ''
                person_middle = person.middle or ''
                
                first_is_exact = are_names_identical(first, person_first)
                middle_is_exact = are_names_identical(last, person_middle)
                
                if first_is_exact and middle_is_exact:
                    add_match(person, 'exact_first_middle', 0.85, f'Exact first name + middle name "{last}" match')
        
        # Strategy 4b: First + Middle variant matching
        if first and last and not middle:
            first_variants = get_name_variants(first)
            last_variants = get_name_variants(last)
            
            for person in Person.objects.all():
                if person.id in seen_ids or not person.first or not person.middle:
                    continue
                
                person_first_variants = get_name_variants(person.first)
                person_middle_variants = get_name_variants(person.middle)
                
                # Check if search terms match first + middle with variants
                first_match = any(fv == pfv for fv in first_variants for pfv in person_first_variants)
                middle_match = any(lv == pmv for lv in last_variants for pmv in person_middle_variants)
                
                if first_match and middle_match:
                    add_match(person, 'normalized_first_middle', 0.82, f'First name + middle name variant match')
        
        # Strategy 5: Initial matching - first initial + middle + last
        if first and last:
            first_initial = first[0].upper()
            query = Q(first__istartswith=first_initial, last__iexact=last)
            if middle:
                query &= Q(middle__iexact=middle)
            
            initial_matches = Person.objects.filter(query)
            for person in initial_matches:
                # Check if last name is case-identical vs character variant
                person_last = person.last or ''
                person_middle = person.middle or ''
                
                last_is_case_identical = are_names_identical(last, person_last)
                middle_is_case_identical = are_names_identical(middle, person_middle) if middle else True
                
                last_is_character_variant = are_names_character_variants(last, person_last)
                middle_is_character_variant = are_names_character_variants(middle, person_middle) if middle else False
                
                if last_is_case_identical and middle_is_case_identical:
                    add_match(person, 'initial_match', 0.8, f'First initial "{first_initial}" + exact last name match')
                elif (last_is_character_variant or last_is_case_identical) and (middle_is_character_variant or middle_is_case_identical):
                    add_match(person, 'initial_variant', 0.75, f'First initial "{first_initial}" + character variant last name match')
        
        # Strategy 5b: Initial matching with middle name - first initial + middle + last
        if first and last:
            first_initial = first[0].upper()
            # Try matching where the provided "last" name is actually someone's middle name
            middle_matches = Person.objects.filter(
                Q(first__istartswith=first_initial) & Q(middle__iexact=last)
            )
            for person in middle_matches:
                person_middle = person.middle or ''
                middle_is_exact = are_names_identical(last, person_middle)
                
                if middle_is_exact:
                    add_match(person, 'initial_middle', 0.75, f'First initial "{first_initial}" + exact middle name "{last}" match')
        
        # Strategy 6: ID number matching (if name_string could be an ID)
        if re.match(r'^[a-zA-Z0-9]+$', name_string.strip()) and len(name_string.strip()) >= 3:
            id_matches = Person.objects.filter(id_number__iexact=name_string.strip())
            for person in id_matches:
                add_match(person, 'id_number', 0.9, f'ID number match: {person.id_number}')
        
        # Strategy 7: Special character normalization matching (for remaining cases)
        if first and last:
            first_variants = get_name_variants(first)
            last_variants = get_name_variants(last)
            
            # Find persons whose names match variants (but exclude already found matches)
            all_persons = Person.objects.all()
            for person in all_persons:
                if person.id in seen_ids:
                    continue
                    
                person_first_variants = get_name_variants(person.first) if person.first else ['']
                person_last_variants = get_name_variants(person.last) if person.last else ['']
                
                # Check for variant matches (only proceed if not already matched)
                first_match = any(fv in person_first_variants for fv in first_variants) or any(pfv in first_variants for pfv in person_first_variants)
                last_match = any(lv in person_last_variants for lv in last_variants) or any(plv in last_variants for plv in person_last_variants)
                
                if first_match and last_match:
                    # Check middle name too if provided
                    if middle:
                        middle_variants = get_name_variants(middle)
                        person_middle_variants = get_name_variants(person.middle) if person.middle else ['']
                        middle_match = any(mv in person_middle_variants for mv in middle_variants)
                        
                        if middle_match:
                            add_match(person, 'normalized_remaining', 0.70, 'Additional normalized character match (full)')
                    else:
                        add_match(person, 'normalized_remaining', 0.65, 'Additional normalized character match (core)')
        
        # Strategy 8: Last name only with first initial (broader search)
        if first and last and len(matches) < 5:
            first_initial = first[0].upper()
            broad_matches = Person.objects.filter(
                Q(first__istartswith=first_initial) & Q(last__icontains=last)
            )
            for person in broad_matches:
                add_match(person, 'broad_initial', 0.6, f'Broad search: "{first_initial}" + partial last name')
        
        # Strategy 9: Fuzzy matching on last name (lowest priority)
        if last and len(matches) < 8:
            # Split compound last names and search for parts
            last_parts = re.split(r'[-\s]+', last)
            for part in last_parts:
                if len(part) >= 3:  # Only search meaningful parts
                    fuzzy_matches = Person.objects.filter(last__icontains=part)
                    for person in fuzzy_matches:
                        add_match(person, 'fuzzy_last', 0.4, f'Fuzzy match on last name part: "{part}"')
        
        # Strategy 10: Email domain matching (if name_string looks like email)
        if '@' in name_string:
            email_matches = Person.objects.filter(email__iexact=name_string.strip())
            for person in email_matches:
                add_match(person, 'email_exact', 0.95, f'Email match: {person.email}')
        
        # Sort by confidence score (descending)
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Limit to top 15 matches to avoid overwhelming the user
        return matches[:15]

    # Is this method needed?
    # def get_selected_authors(self):
    #     selected_authors = []
    #     for key, value in self.cleaned_data.items():
    #         if key.startswith("author_"):
    #             selected_authors.append(value)
    #     return selected_authors


class AuthorSelectForm(PersonSelectForm):
    person_type = "author"
    def __init__(self, *args, authors=None, **kwargs):
        super().__init__(*args, persons=authors, **kwargs)


class SupervisorSelectForm(PersonSelectForm):
    person_type = "supervisor"
    def __init__(self, *args, supervisors=None, **kwargs):
        super().__init__(*args, persons=supervisors, **kwargs)


class EditorSelectForm(PersonSelectForm):
    person_type = "editor"
    def __init__(self, *args, editors=None, **kwargs):
        super().__init__(*args, persons=editors, **kwargs)


class AddPersonForm(forms.ModelForm):
    """Form for creating new Person instances"""
    
    # Add a name field that will be processed by the Person model
    name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Full name (e.g., "John Doe" or "Doe, John")'
        }),
        help_text="Enter the person's full name. It will be automatically split into first, middle, and last name components."
    )
    
    class Meta:
        model = Person
        fields = ['email', 'institution', 'department']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'institution': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Institution'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department'}),
        }
    
    def save(self, commit=True):
        """Override save to handle the name field properly"""
        instance = super().save(commit=False)
        name = self.cleaned_data.get('name')
        if name:
            # The Person model will handle name parsing in its __init__ method
            # But since we're working with an existing instance, we need to call set_names
            instance.set_names(name, commit=False)
        
        if commit:
            instance.save()
        return instance
    


class PersonHeavySelect2TagWidget(s2forms.HeavySelect2TagWidget):

    def __init__(self, *args, **kwargs):
        """
        Initialize the widget with proper django-select2 patterns.
        Remove the unused initial_data parameter since Django handles initial values.
        """
        super().__init__(*args, **kwargs)

    def format_value(self, value):
        """
        Convert the initial value (list of PKs) to the format expected by Select2.
        This is crucial for preselection to work properly.
        """
        print(f"PersonHeavySelect2TagWidget:format_value: {value}")
        
        if value is None or value == '':
            return []  # Return empty list instead of None
            
        # Handle different input formats
        if isinstance(value, (list, tuple)):
            # List of PKs - convert to Person objects for display
            pks = [int(pk) for pk in value if str(pk).isdigit()]
            if pks:
                persons = Person.objects.filter(pk__in=pks)
                # Return list of PKs as strings (Select2 expects string values)
                return [str(person.pk) for person in persons]
            else:
                return []  # Return empty list if no valid PKs
        elif isinstance(value, str) and value:
            try:
                # Try to parse as list representation
                parsed_value = ast.literal_eval(value)
                if isinstance(parsed_value, (list, tuple)):
                    return self.format_value(parsed_value)
                else:
                    return [str(value)]
            except (ValueError, SyntaxError):
                # Single value
                return [str(value)]
        elif hasattr(value, '__iter__'):
            # QuerySet or other iterable
            try:
                return [str(item.pk if hasattr(item, 'pk') else item) for item in value]
            except:
                return []  # Return empty list if iteration fails
        else:
            # Single value
            return [str(value)]
            
        return []  # Return empty list as fallback instead of None

    def value_from_datadict(self, data, files, name):
        """
        Extract and format the value from form submission data.
        """
        value = super().value_from_datadict(data, files, name)
        print(f"PersonHeavySelect2TagWidget:value_from_datadict: {value}")
        return value

    def get_context(self, name, value, attrs):
        """Get the context for rendering the widget.
        Ensure that preselected values are properly included in the context.
        """
        context = super().get_context(name, value, attrs)
        
        # Don't clear optgroups - they're needed for preselection display
        # The commented line was interfering with preselection:
        # context['widget']['optgroups'] = []
        
        print(f"PersonHeavySelect2TagWidget:get_context: name={name}, value={value}")
        return context

    def value_new(self, value):
        """Handle creation of new Person objects."""
        print(f'In PersonHeavySelect2TagWidget:value_new: {value}')
        # names = value.split()
        # first = names[0]
        # last = names[-1] if len(names) > 1 else ""
        # middle = " ".join(names[1:-1]) if len(names) > 2 else ""
        # return Person.objects.create(first=first, middle=middle, last=last).pk
        return 9999

