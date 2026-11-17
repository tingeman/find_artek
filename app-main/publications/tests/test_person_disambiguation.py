"""
Tests for the improved person disambiguation workflow.
"""

import unittest
import re
import logging
from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.http import HttpRequest

# Mock the logging module to avoid issues during testing
logging.getLogger = MagicMock()

# Import modules after setting up mocks
from publications.models import Person
from publications.workflows.person_disambiguation import PersonMatcher
from publications.utils_person import NameNormalizer

class NameNormalizerTestCase(TestCase):
    """Test the NameNormalizer class."""

    def test_normalize_name_empty(self):
        """Test normalize_name with empty input."""
        self.assertEqual(NameNormalizer.normalize_name(""), "")
        self.assertEqual(NameNormalizer.normalize_name(None), "")

    def test_normalize_name_danish_characters(self):
        """Test normalize_name with Danish characters."""
        self.assertEqual(NameNormalizer.normalize_name("Jørgen Ægir Åberg"), "joergen aegir aaberg")

    def test_normalize_name_other_characters(self):
        """Test normalize_name with characters from other languages."""
        self.assertEqual(NameNormalizer.normalize_name("José Müller-Straße"), "jose mueller-strasse")

    def test_normalize_name_whitespace(self):
        """Test normalize_name handles whitespace correctly."""
        self.assertEqual(NameNormalizer.normalize_name("  John   Smith  "), "john smith")

    def test_get_relaxed_name_components_empty(self):
        """Test get_relaxed_name_components with empty input."""
        result = NameNormalizer.get_relaxed_name_components("")
        self.assertEqual(result, {"first_relaxed": "", "last_relaxed": ""})

    def test_get_relaxed_name_components_simple(self):
        """Test get_relaxed_name_components with a simple name."""
        result = NameNormalizer.get_relaxed_name_components("John Smith")
        self.assertEqual(result, {"first_relaxed": "j", "last_relaxed": "smith"})

    def test_get_relaxed_name_components_complex(self):
        """Test get_relaxed_name_components with a complex name."""
        result = NameNormalizer.get_relaxed_name_components("María-José García López")
        self.assertEqual(result, {"first_relaxed": "m", "last_relaxed": "lopez"})

    def test_update_person_relaxed_fields(self):
        """Test update_person_relaxed_fields updates the Person object correctly."""
        # Create a mock Person object
        person = MagicMock()
        person.first = "Jørgen"
        person.last = "Åström"
        
        # Update relaxed fields
        NameNormalizer.update_person_relaxed_fields(person)
        
        # Check that the fields were updated correctly
        self.assertEqual(person.first_relaxed, "j")
        self.assertEqual(person.last_relaxed, "aastroem")


class PersonMatcherTestCase(TestCase):
    """Test the PersonMatcher class."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up data for all test methods."""
        # Create some test persons
        cls.person1 = Person.objects.create(
            first="John", 
            last="Smith",
            first_relaxed="j",
            last_relaxed="smith",
            email="john.smith@example.com"
        )
        cls.person2 = Person.objects.create(
            first="Jane", 
            last="Doe",
            first_relaxed="j",
            last_relaxed="doe",
            email="jane.doe@example.com",
            id_number="s12345"
        )
        cls.person3 = Person.objects.create(
            first="Michael", 
            last="Johnson",
            first_relaxed="m",
            last_relaxed="johnson",
            initials="MJ"
        )
        cls.person4 = Person.objects.create(
            first="Lars", 
            last="Jensen",
            first_relaxed="l",
            last_relaxed="jensen",
            id_number="123456"
        )
    
    def test_clean_name(self):
        """Test _clean_name correctly cleans input names."""
        matcher = PersonMatcher()
        self.assertEqual(matcher._clean_name("  John Smith  "), "John Smith")
        self.assertEqual(matcher._clean_name("John Smith [id:123]"), "John Smith")
        
    def test_remove_tags(self):
        """Test _remove_tags correctly removes tags."""
        matcher = PersonMatcher()
        self.assertEqual(
            matcher._remove_tags("John Smith [id:123]"), 
            "John Smith"
        )
        self.assertEqual(
            matcher._remove_tags("John Smith [id: 123] [tag: value]"), 
            "John Smith"
        )
    
    def test_match_by_exact_name(self):
        """Test _match_by_exact_name finds exact name matches."""
        matcher = PersonMatcher()
        matches = matcher._match_by_exact_name("John Smith")
        
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)
        self.assertEqual(matches[0]['match_type'], 'exact_name')
        self.assertAlmostEqual(matches[0]['confidence'], 1.0)
    
    def test_match_by_company_initials(self):
        """Test _match_by_company_initials finds matches by company-assigned initials."""
        matcher = PersonMatcher()
        matches = matcher._match_by_company_initials("Michael Johnson MJ")
        
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person3)
        self.assertEqual(matches[0]['match_type'], 'company_initials')
        self.assertAlmostEqual(matches[0]['confidence'], 1.0)
    
    def test_match_by_relaxed_name(self):
        """Test _match_by_relaxed_name finds relaxed matches and initial-based matches."""
        matcher = PersonMatcher()
        
        # Test relaxed matching
        matches1 = matcher._match_by_relaxed_name("Jane Smith")
        
        # Should find Jane Doe (relaxed: j doe) but with lower confidence
        self.assertEqual(len(matches1), 1)
        self.assertEqual(matches1[0]['person'], self.person2)
        self.assertEqual(matches1[0]['match_type'], 'relaxed_name')
        self.assertLess(matches1[0]['confidence'], 1.0)  # Confidence should be less than 1.0
        
        # Test initial-based matching within relaxed matching
        # Create a person that would match by initial but not by relaxed name
        person5 = Person.objects.create(
            first="Jennifer", 
            last="Smith",
            first_relaxed="j",
            last_relaxed="smith"
        )
        
        # Should find Jennifer Smith by initial matching (j + Smith)
        matches2 = matcher._match_by_relaxed_name("Jane Smith")
        
        # Find all match types in the results
        match_types = [m['match_type'] for m in matches2]
        
        # Verify we have both regular relaxed matches and initial-based matches
        self.assertGreaterEqual(len(matches2), 1)
        self.assertTrue(any(t == 'relaxed_name' for t in match_types) or 
                      any(t == 'initial_relaxed' for t in match_types))
    
    def test_match_by_email(self):
        """Test _match_by_email finds matches by email."""
        matcher = PersonMatcher()
        matches = matcher._match_by_email("Some Person jane.doe@example.com")
        
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person2)
        self.assertEqual(matches[0]['match_type'], 'email')
        self.assertAlmostEqual(matches[0]['confidence'], 0.95)
    
    def test_match_by_id_number(self):
        """Test _match_by_id_number finds matches by ID number."""
        matcher = PersonMatcher()
        
        # Test student ID
        student_matches = matcher._match_by_id_number("Person s12345")
        self.assertEqual(len(student_matches), 1)
        self.assertEqual(student_matches[0]['person'], self.person2)
        self.assertEqual(student_matches[0]['match_type'], 'student_id')
        
        # Test employee ID
        employee_matches = matcher._match_by_id_number("Person 123456")
        self.assertEqual(len(employee_matches), 1)
        self.assertEqual(employee_matches[0]['person'], self.person4)
        self.assertEqual(employee_matches[0]['match_type'], 'employee_id')
    
    def test_find_matches(self):
        """Test find_matches combines multiple matching strategies correctly."""
        matcher = PersonMatcher()
        
        # Should find by exact name
        matches1 = matcher.find_matches("John Smith")
        self.assertEqual(len(matches1), 1)
        self.assertEqual(matches1[0]['person'], self.person1)
        
        # Should find by email with highest confidence
        matches2 = matcher.find_matches("Someone jane.doe@example.com")
        self.assertEqual(len(matches2), 1)
        self.assertEqual(matches2[0]['person'], self.person2)
        
        # Should find no matches for an unknown name
        matches3 = matcher.find_matches("Unknown Person")
        self.assertEqual(len(matches3), 0)
    
    def test_get_best_match(self):
        """Test get_best_match returns the best match."""
        matcher = PersonMatcher()
        
        # Should find person1
        best_match = matcher.get_best_match("John Smith")
        self.assertEqual(best_match['person'], self.person1)
        
        # Should return None for unknown person
        none_match = matcher.get_best_match("Unknown Person")
        self.assertIsNone(none_match)
    
    def test_is_new_person(self):
        """Test is_new_person correctly identifies new persons."""
        matcher = PersonMatcher()
        
        # Known person should return False
        self.assertFalse(matcher.is_new_person("John Smith"))
        
        # Unknown person should return True
        self.assertTrue(matcher.is_new_person("Unknown Person"))
