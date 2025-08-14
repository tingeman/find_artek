"""
Advanced person disambiguation workflow.

This module provides a cleaner implementation for the person disambiguation workflow
used throughout the application. It follows a more structured and maintainable approach
while maintaining the same functionality as the original implementation.

The module is designed to work in parallel with the original implementation, allowing
for easy comparison and switching between the two.

Note: This module deliberately avoids circular imports by not importing any workflow modules.
"""

import ast
import re
import logging
import string
from typing import List, Dict, Tuple, Optional, Union, Any, Set

from django.db.models import Q
from django.urls import reverse
from unidecode import unidecode

# Import utility functions that we'll need
from publications.utils_basic import dk_unidecode, CaseInsensitively
from publications import models
from publications.utils_person import NameNormalizer


# TODO: Figure out where these functions should live!
from publications.utils_person import find_ldap_person, get_or_create_person_from_ldap

logger = logging.getLogger(__name__)


class PersonMatcher:
    """
    A service class that provides methods for matching person names to existing database records.
    
    This class consolidates all the person matching logic into one place with a clear API.
    It supports various matching strategies including exact matches, relaxed character variants,
    and specialized matching (e.g., by email or ID number).
    
    Example usage:
        matcher = PersonMatcher()
        matches = matcher.find_matches("John Smith")
        best_match = matcher.get_best_match("John Smith")
    """
    
    def __init__(self, user=None, confidence_threshold: float = 0.5, use_ldap: bool = True):
        """
        Initialize the PersonMatcher with optional parameters.
        
        Args:
            confidence_threshold: Minimum confidence score (0-1) for a match to be considered valid
        """
        self.confidence_threshold = confidence_threshold
        self.normalizer = NameNormalizer
        self.user = user
        self.use_ldap = use_ldap
    
    def find_matches(self, searchstr: str) -> List[Dict[str, Any]]:
        """
        Find and rank potential matches for a person name or identifier.

        This method applies multiple matching strategies in order:
        - ID tag match (primary key)  ([id:123])
        - LDAP tag match (if enabled) ([ldap:thin] or [ldap:s123456])
        - Exact match on all name components
        - Exact match on first and last name
        - Relaxed match using normalized name components
        - Specialized matches (study number, initials, etc.)

        Each match is assigned a confidence score and a match type label.
        Results are filtered by confidence threshold, sorted by confidence,
        and deduplicated so only the highest-confidence match for each person is returned.

        Args:
            searchstr: The person name or identification string to match.

        Returns:
            List of dictionaries, each with:
                'person': Person object
                'confidence': float (0-1)
                'match_type': str (how the match was found)
        """
        if not searchstr or not isinstance(searchstr, str):
            return []

        tags = self.normalizer.get_tags(searchstr)
        emails = self.normalizer.get_emails(searchstr)
        clean_name = self.normalizer.clean_name(searchstr)
        name_components = self.normalizer.get_name_components(searchstr)
            
        # Initialize results list
        results = []
        
        # Try different matching strategies
        
        # 1. Try exact matches first (highest confidence)
        if 'id' in tags:
            # If the search string contains an id-tag, it represents the primary key
            try:
                person_id = int(tags['id'])
                person = models.Person.objects.get(pk=person_id)
                results.append({
                    'person': person,
                    'confidence': 1.0,
                    'match_type': 'exact_id'
                })
            except (ValueError, models.Person.DoesNotExist):
                pass

        if 'ldap' in tags and self.use_ldap:
            # If the search string contains an ldap-tag, try to find the person via LDAP

            try:
                ldap_obj = None
                if self._is_initials(tags['ldap']):
                    ldap_result = find_ldap_person(initials=tags['ldap'])
                elif self._is_studynumber(tags['ldap']):
                    ldap_result = find_ldap_person(name=tags['ldap'])
            except Exception as e:
                logger.error(f"Error finding LDAP person: {e}")

            if isinstance(ldap_result, list) and len(ldap_result) == 1:
                # ldap_result is a list, but it should have only one entry
                person = get_or_create_person_from_ldap(ldap_object=ldap_result[0], user=self.user, save=False)
                if person:
                    if person.pk:
                        # If a person with a primary key was found, it means that the person is already 
                        # in our own database, so we should update the information from LDAP
                        
                        # TODO: This is not implemented yet.
                        # person.update_from_ldap(ldap_object=ldap_result[0], user=self.user, save=True)
                        pass
                    elif person and not person.pk:
                        # If we did not find a person with a primary key, we should save the person to 
                        # our database
                        person.save()               

                    results.append({
                        'person': person,
                        'confidence': 1.0,
                        'match_type': 'ldap'
                    })

        exact_matches = self._match_by_namestring(clean_name, exact=True)
        for entry in exact_matches:
            results.append(entry)

        partial_matches = self._match_by_namestring(clean_name, exact=False)
        for entry in partial_matches:
            results.append(entry)
            
        # 2. Try relaxed matches with character variants
        relaxed_matches = self._match_by_relaxed_namestring(clean_name)
        for entry in relaxed_matches:
            results.append(entry)

        # 3. Try specialized matches (initials, studynumber etc.)
        if self._is_studynumber(clean_name):
            matches = self._match_by_studynumber(clean_name, self.user, use_ldap=self.use_ldap)
            for entry in matches:
                results.append(entry)
        elif self._is_initials(clean_name):
            matches = self._match_by_initials(clean_name, use_ldap=self.use_ldap)
            for entry in matches:
                results.append(entry)
        elif len(emails) > 0:
            for email in emails:
                matches = self._match_by_email(email)
                for entry in matches:
                    results.append(entry)

        # Filter by confidence threshold
        results = [r for r in results if r['confidence'] >= self.confidence_threshold]
        
        # Sort by confidence (descending)
        results.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Keep only the highest confidence result for each unique person
        unique_results = []
        seen_ids = set()
        for result in results:
            # results is sorted in descending order by confidence
            # so if we saw this person before, the current instance has lower confidence
            # and can be skipped
            person_id = result['person'].pk
            if person_id not in seen_ids:
                unique_results.append(result)
                seen_ids.add(person_id)

        return unique_results
        
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
    
    @classmethod
    def _is_studynumber(self, searchstr: str) -> bool:
        """
        Check if the search string is a study number.
        
        Args:
            searchstr: The string to check
            
        Returns:
            True if it matches the study number format, False otherwise
        """
        # Study numbers are typically 6 digits, optionally prefixed with 's'
        return bool(re.match(r'^(s)?\d{6}$', searchstr.strip(), re.IGNORECASE))
    
    @classmethod
    def _is_initials(self, searchstr: str) -> bool:
        """
        Check if the search string is likely initials.
        
        Args:
            searchstr: The string to check
            
        Returns:
            True if it matches the initials format, False otherwise
        """
        # Initials are typically 2-5 consecutive letters
        return bool(re.match(r'^[a-zA-Z]{2,5}$', searchstr.strip()))

    @classmethod
    def _is_email(self, searchstr: str) -> bool:
        """
        Check if the search string is an email address.
        
        Args:
            searchstr: The string to check
            
        Returns:
            True if it matches the email format, False otherwise
        """
        # Simple regex for email validation
        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', searchstr.strip()))

    # def _find_exact_namestring_matches(self, namestr: str, exact: bool = False) -> List[Person]:
    #     """
    #     Find matches for a name string using all name components and relaxed fields.
    #     Uses NameNormalizer.get_name_components to get field values, then searches similar to get_person.
    #     Args:
    #         name: Name string to match
    #         initials: Optional initials
    #         id_number: Optional id_number
    #         exact: If True, only exact matches on all components, otherwise only exact on first anlast

    #     Returns:
    #         List of Person objects matching the criteria
    #     """
    #     # Get all name components
    #     name_components = self.normalizer.get_name_components(namestr)

    #     # if 'first' and last are not in name_components, return empty list
    #     if not name_components.get('first') or not name_components.get('last'):
    #         return []

    #     # convert all component keys to __iexact
    #     # this ensures case-insensitive matching
    #     name_components = {k + '__iexact': v for k, v in name_components.items() if v}

    #     print(f"🔍 DEBUG: utils_person:get_person: {name_components}")
    #     persons = list(models.Person.objects.filter(**name_components)) if name_components else []

    #     if persons:
    #         # If we have an exact match, return it
    #         print("🔍 DEBUG:    Exact match found.")
    #         return persons
    #     else:
    #         print("🔍 DEBUG:    No Exact match found.")
        
    #     if not exact:
    #         # No exact match - we'll try relaxed match
    #         print('🔍 DEBUG:    Trying first-last match...')
    #         first_last_components = {
    #             'first__iexact': name_components['first'],
    #             'last__iexact': name_components['last']
    #         }
    #         persons = models.Person.objects.filter(**first_last_components)

    #         if not persons:
    #             # No first-last match
    #             print('🔍 DEBUG:    No first-last matches found.')

    #     return persons

    # def _find_relaxed_namestring_matches(self, name: str) -> List[Person]:
    #     """
    #     Find matches using relaxed criteria (character variants).
        
    #     Args:
    #         name: Name to match
            
    #     Returns:
    #         List of Person objects that match using relaxed criteria
    #     """

    #     # Use NameNormalizer to get relaxed components
    #     relaxed_components = self.normalizer.get_relaxed_name_components(name)
    #     first_relaxed = relaxed_components["first_relaxed"]
    #     last_relaxed = relaxed_components["last_relaxed"]
        
    #     if not first_relaxed and not last_relaxed:
    #         return []
        
    #     # Find persons with matching relaxed fields
    #     return list(Person.objects.filter(
    #         first_relaxed__iexact=first_relaxed,
    #         last_relaxed__iexact=last_relaxed
    #     ))

    def _match_by_initials(self, searchstr, use_ldap=False):
        """Get or create person from initials. Will use ldap lookup if possible."""
        results = []

        # See if it is in our own database
        persons = models.Person.objects.filter(
            initials__iexact=searchstr
        ).distinct()

        if persons:
            # If we have a match, return the first one
            results.append({
                'person': persons[0],
                'confidence': 1.0,
                'match_type': 'exact initials'
            })
        else:
            # If no match, try to find initials in the LDAP directory
            if use_ldap:
                ldap_result = find_ldap_person(initials=searchstr)
                if ldap_result:
                    person = get_or_create_person_from_ldap(
                        person=ldap_result[0],
                        user=self.user,
                        save=False
                    )
                    if person:
                        results.append({
                            'person': person,
                            'confidence': 1.0,
                            'match_type': 'ldap'
                        })
        
        return results

    def _match_by_studynumber(self, searchstr, user, use_ldap=False):
        """Get or create person from study number. Will use ldap lookup if possible."""
        results = []

        # See if it is in our own database
        persons = models.Person.objects.filter(
            id_number__iexact=searchstr
        ).distinct()

        if persons:
            # If we have a match, return the first one
            results.append({
                'person': persons[0],
                'confidence': 1.0,
                'match_type': 'exact study number'
            })
        else:
            # If no match, try to find study number in the LDAP directory
            if use_ldap:
                ldap_result = find_ldap_person(name=searchstr)
                if ldap_result:
                    person = get_or_create_person_from_ldap(
                        person=ldap_result[0],
                        user=self.user,
                        save=False
                    )
                    if person:
                        results.append({
                            'person': person,
                            'confidence': 1.0,
                            'match_type': 'ldap'
                        })
        
        return results

    def _match_by_email(self, searchstr: str) -> List[Dict[str, Any]]:
        """
        Find matches by email address.
        
        Args:
            searchstr: The string containing the email to match
            
        Returns:
            List of dictionaries with matching persons and their confidence scores
        """
        results = []
        
        # Extract email from the search string
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', searchstr)
        if not email_match:
            return results

    def _match_by_namestring(self, namestr: str, exact: bool = False) -> List[Dict[str, Any]]:
        """
        Find matches for a name string using all name components and relaxed fields.
        Uses NameNormalizer.get_name_components to get field values, then searches similar to get_person.
        Args:
            name: Name string to match
            initials: Optional initials
            id_number: Optional id_number
            exact: If True, only exact matches on all components, otherwise only exact on first anlast

        Returns:
            List of Person objects matching the criteria
        """
        # Get all name components
        name_components = self.normalizer.get_name_components(namestr)
        clean_name = self.normalizer.clean_name(namestr)


        results = []

        # convert all component keys to __iexact
        # this ensures case-insensitive matching
        name_components = {k + '__iexact': v for k, v in name_components.items() if v}
        print(f"🔍 DEBUG: PersonMatcher:namestring: {name_components}")
        
        
        if name_components.get('first__iexact') and name_components.get('last__iexact'):        
            # We can only do exact match if both first and last name are present.
            persons = list(models.Person.objects.filter(**name_components)) if name_components else []

            if persons:
                # If we have an exact match, add to results
                print("🔍 DEBUG:    Exact match found.")
                for person in persons:
                    results.append({
                        'person': person,
                        'confidence': 0.95,  # High confidence for exact match
                        'match_type': 'exact name'
                    })
                return results
            else:
                print("🔍 DEBUG:    No Exact match found.")

            for person in persons:
                match_confidence = 0.95  # Default confidence for exact match on all components
                results.append({
                    'person': person,
                    'confidence': match_confidence,
                    'match_type': 'exact name'
                })

        if not exact:
            # No exact match on all components, we will try just first and last name
            # This is a more relaxed match
            print('🔍 DEBUG:    Trying first-last match...')

            # Prepare first-last components for filtering
            # Include only first and last name components, and only if they are present and not empty
            first_last_components = {k: v for k, v in name_components.items() if v and k in ['first__iexact', 'last__iexact']}

            persons = models.Person.objects.filter(**first_last_components)

            if not persons:
                # No first-last match
                print('🔍 DEBUG:    No first-last matches found.')

            for person in persons:
                # Calculate confidence based on similarity
                person_name = person.get_full_name()
                
                # Simple string similarity check
                similarity = self._compute_name_similarity(clean_name, person_name)
                match_confidence = 0.9 * similarity

                results.append({
                    'person': person,
                    'confidence': match_confidence,
                    'match_type': 'first-last name'
                })

        return results

    def _match_by_relaxed_namestring(self, name: str, confidence_factor: float = 0.9) -> List[Dict[str, Any]]:
        """
        Find matches using relaxed criteria (character variants).
        (first letter of first name + full last name).
        
        Args:
            name: Name to match
            confidence: Base confidence score for this match type

        Returns:
            List of match dictionaries
        """

        # Use NameNormalizer to get relaxed components
        relaxed_components = self.normalizer.get_relaxed_name_components(name)
        first_relaxed = relaxed_components["first_relaxed"]
        last_relaxed = relaxed_components["last_relaxed"]
        
        results = []

        if not first_relaxed and not last_relaxed:
            # If we have no relaxed components, return empty results
            return results
            
        # Find persons with matching relaxed fields
        relaxed_persons = list(models.Person.objects.filter(
            first_relaxed__iexact=first_relaxed,
            last_relaxed__iexact=last_relaxed
        ))

        name_normalized = self.normalizer.normalize_name(name)
        
        for person in relaxed_persons:
            # Calculate confidence based on similarity
            person_name = f"{person.first} {person.last}"
            person_normalized = self.normalizer.normalize_name(person_name)
            
            # Simple string similarity check
            similarity = self._compute_name_similarity(name_normalized, person_normalized)
            match_confidence = confidence_factor * similarity
            
            results.append({
                'person': person,
                'confidence': match_confidence,
                'match_type': 'relaxed_name'
            })
            
        return results

   
    # def _match_by_relaxed_name(self, name: str, confidence: float = 0.8) -> List[Dict[str, Any]]:
    #     """
    #     Find matches using relaxed name comparison with character variants.
    #     This includes both traditional relaxed matching and initial-based matching
    #     (first letter of first name + full last name).
        
    #     Args:
    #         name: Name to match
    #         confidence: Base confidence score for this match type
            
    #     Returns:
    #         List of match dictionaries
    #     """
    #     results = []
        
    #     # Get relaxed name components
    #     relaxed_components = self.normalizer.get_relaxed_name_components(name)
    #     first_relaxed = relaxed_components["first_relaxed"]
    #     last_relaxed = relaxed_components["last_relaxed"]
        
    #     # Only proceed if we have something to match on
    #     if first_relaxed and last_relaxed:
    #         # Match using the relaxed fields in the database
    #         relaxed_persons = models.Person.objects.filter(
    #             first_relaxed__iexact=first_relaxed,
    #             last_relaxed__iexact=last_relaxed
    #         )
            
    #         name_normalized = self.normalizer.normalize_name(name)
            
    #         for person in relaxed_persons:
    #             # Calculate confidence based on similarity
    #             person_name = f"{person.first} {person.last}"
    #             person_normalized = self.normalizer.normalize_name(person_name)
                
    #             # Simple string similarity check
    #             similarity = self._compute_name_similarity(name_normalized, person_normalized)
    #             match_confidence = confidence * similarity
                
    #             results.append({
    #                 'person': person,
    #                 'confidence': match_confidence,
    #                 'match_type': 'relaxed_name'
    #             })
        
    #     # Add initial-based matching (first letter of first name + full last name)
    #     # This is now part of the relaxed matching strategy, not a separate method
    #     name_parts = name.split()
    #     if len(name_parts) >= 2:
    #         first_initial = name_parts[0][0].lower() if name_parts[0] else ''
    #         last = ' '.join(name_parts[1:])
            
    #         # Don't duplicate effort if we've already covered this with relaxed matching
    #         if not (first_initial == first_relaxed and last.lower() == last_relaxed.lower()):
    #             # Find people with matching first initial and last name
    #             initial_persons = models.Person.objects.filter(
    #                 first__istartswith=first_initial,
    #                 last_relaxed__iexact=self.normalizer.normalize_name(last)
    #             )
                
    #             for person in initial_persons:
    #                 # Check if we already have this person in results
    #                 if not any(r['person'].pk == person.pk for r in results):
    #                     # Apply slightly lower confidence for initial matching vs full relaxed matching
    #                     initial_match_confidence = confidence * 0.9
    #                     results.append({
    #                         'person': person,
    #                         'confidence': initial_match_confidence,
    #                         'match_type': 'initial_relaxed'
    #                     })
        
    #     return results
    
    def _match_by_specialized_fields(self, name: str) -> List[Dict[str, Any]]:
        """
        Find matches using specialized fields like email, ID numbers, etc.
        
        Args:
            name: Name string that might contain specialized identifiers
            
        Returns:
            List of match dictionaries
        """
        results = []
        
        # Check for email matches
        email_matches = self._match_by_email(name)
        results.extend(email_matches)
        
        # Check for ID number matches (both student and employee IDs)
        id_matches = self._match_by_id_number(name)
        results.extend(id_matches)
        
        return results
    
    def _match_by_email(self, name: str, confidence: float = 1.0) -> List[Dict[str, Any]]:
        """
        Match person by email if present in the name string.
        
        Args:
            name: Name string potentially containing an email
            confidence: Confidence score for this match type
            
        Returns:
            List of match dictionaries
        """
        results = []
        
        print(f"🔍 DEBUG: Matching by email in name: {name}")

        # Extract email using regex
        email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        email_match = email_pattern.search(name)
        
        if email_match:
            email = email_match.group(0).lower()
            email_persons = models.Person.objects.filter(email__iexact=email)
            
            for person in email_persons:
                results.append({
                    'person': person,
                    'confidence': confidence,
                    'match_type': 'email'
                })
        
        return results
    
    def _match_by_id_number(self, name: str, confidence: float = 0.95) -> List[Dict[str, Any]]:
        """
        Match person by ID number if present in the name string.
        
        Handles two distinct ID number formats:
        - Student IDs: starting with 's' followed by 5 digits
        - Employee IDs: 5-6 digits only
        
        Args:
            name: Name string potentially containing an ID number
            confidence: Confidence score for this match type
            
        Returns:
            List of match dictionaries
        """
        results = []
        
        # Extract student IDs (s followed by 5 digits)
        student_id_pattern = re.compile(r's\d{5}', re.IGNORECASE)
        student_id_match = student_id_pattern.search(name)
        
        if student_id_match:
            student_id = student_id_match.group(0).lower()
            student_persons = models.Person.objects.filter(id_number__iexact=student_id)
            
            for person in student_persons:
                results.append({
                    'person': person,
                    'confidence': confidence,
                    'match_type': 'student_id'
                })
        
        # Extract employee IDs (5-6 digits)
        # Avoid matching years or other numeric sequences
        employee_id_pattern = re.compile(r'\b\d{5,6}\b')
        employee_id_match = employee_id_pattern.search(name)
        
        if employee_id_match:
            employee_id = employee_id_match.group(0)
            # Skip if it looks like a year
            if not re.match(r'(19|20)\d{2}', employee_id):
                employee_persons = models.Person.objects.filter(id_number__exact=employee_id)
                
                for person in employee_persons:
                    results.append({
                        'person': person,
                        'confidence': confidence,
                        'match_type': 'employee_id'
                    })
        
        return results
    
    def _compute_name_similarity(self, name1: str, name2: str) -> float:
        """
        Compute a similarity score between two normalized name strings.
        
        Args:
            name1: First name string (normalized)
            name2: Second name string (normalized)
            
        Returns:
            Similarity score between 0 and 1
        """
        # Simple similarity calculation based on character overlap
        # This could be replaced with more sophisticated algorithms
        if not name1 or not name2:
            return 0.0
        
        # Convert to sets of words
        words1 = set(name1.lower().split())
        words2 = set(name2.lower().split())
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0.0
            
        return intersection / union


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
            matches = self.matcher.find_matches(name)   # TODO: Why do we do this?? output is not used...
            names_needing_resolution.append(name)
            
        return names_needing_resolution
    
    def _extract_raw_person_data(self, form_data, field_name):
        """Extract raw person data from form data, handling various formats"""

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
                    parsed_items = ast.literal_eval(value)   # TODO: What delimiters does this accept?
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
    
    def _get_tag(self, string, tag_name):
        """Extract tag value from string like '[id:123]' -> 123"""

        # TODO: We should only have one function/class that handles
        #       extraction of tags. Maybe call NameNormalizer?

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

        # TODO: We should only have one function/class that handles
        #       extraction of tags. Maybe call NameNormalizer?

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
        
        # TODO: This redirect logic seems problematic, as it is hard-coded
        #       Couldn't this logic live in the code from which the workflow
        #       is initiated, which could pass either the final redirect url
        #       or the reverse key and relevant kwargs...?

        # Determine specific redirect URL based on context
        if '/report/' in redirect_url and '/edit/' in redirect_url:
            match = re.search(r'/report/(\d+)/edit/', redirect_url)
            if match:
                publication_id = match.group(1)
                redirect_url = reverse('publications:edit_report_review', kwargs={'pk': publication_id})
        elif '/add/' in redirect_url:
            redirect_url = reverse('publications:add_report_review')
        
        # Clear workflow
        self.clear_workflow()
        
        return updated_form_data, redirect_url
    
    def clear_workflow(self):
        """Clear the workflow from session"""
        if 'person_workflow' in self.session:
            del self.session['person_workflow']
            self.session.modified = True
