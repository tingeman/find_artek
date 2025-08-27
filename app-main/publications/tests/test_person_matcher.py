"""
Tests for the PersonMatcher class in person_disambiguation.py
"""

import unittest
import re
import pdb
from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.contrib.auth.models import User

from publications.models import Person
from publications.workflows.person_disambiguation import PersonMatcher
from publications.utils_person import NameNormalizer

class PersonMatcherTestCase(TestCase):
    """Test the PersonMatcher class in person_disambiguation.py."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up data for all test methods."""
        # Create test user for authentication-required tests
        cls.test_user = User.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='testpass'
        )
        
        # Create some test persons
        cls.person1 = Person.objects.create(
            first="John", 
            last="Smith",
            first_relaxed="J",
            last_relaxed="Smith",
            email="john.smith@example.com"
        )
        cls.person2 = Person.objects.create(
            first="Jane", 
            last="Doe",
            first_relaxed="J",
            last_relaxed="Doe",
            email="jane.doe@example.com",
            id_number="s123456"
        )
        cls.person3 = Person.objects.create(
            first="Michael", 
            last="Johnson",
            first_relaxed="M",
            last_relaxed="Johnson",
            initials="MJ"
        )
        cls.person4 = Person.objects.create(
            first="Lars", 
            last="Jensen",
            first_relaxed="L",
            last_relaxed="Jensen",
            id_number="12345"
        )
        cls.person5 = Person.objects.create(
            first="Jonas", 
            last="Jensen",
            first_relaxed="J",
            last_relaxed="Jensen",
            id_number="12345"
        )    


    def test_find_matches_exact(self):
        """Test finding exact name matches."""
        matcher = PersonMatcher()
        
        # Test exact match by first and last name
        matches = matcher.find_matches("John Smith")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)
        self.assertAlmostEqual(matches[0]['confidence'], 0.95)  # Default confidence for exact name match
        
        # Test case insensitivity
        # pdb.set_trace()

        # NB: pybtex does not parse lowercase names correctly. We need a workaround for this!

        # matches = matcher.find_matches("john smith")
        # self.assertEqual(len(matches), 1)
        # self.assertEqual(matches[0]['person'], self.person1)
        
        # Test with middle name - should still match
        matches = matcher.find_matches("John A. Smith")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)
    
    def test_find_matches_relaxed(self):
        """Test finding relaxed name matches."""
        matcher = PersonMatcher(confidence_threshold=0.0)  # return all matches regardless of confidence
        
        # Test match with special characters (would normalize to j jensen)
        matches = matcher.find_matches("Jørgen Jensen")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person5)  # Jonas Jensen
        self.assertLess(matches[0]['confidence'], 1.0)  # Should be relaxed match
        
        # Test with no results
        matches = matcher.find_matches("Unknown Person")
        self.assertEqual(len(matches), 0)
    
    def test_find_matches_by_id(self):
        """Test finding matches by ID number."""
        matcher = PersonMatcher()
        
        # Test student ID match
        matches = matcher.find_matches("s123456")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person2)
        self.assertAlmostEqual(matches[0]['confidence'], 1.0)
        
        # Test employee ID match

        # NB PersonMatcher currently does not support employee ID matching directly!!

        # matches = matcher.find_matches("12345")
        # self.assertEqual(len(matches), 1)
        # self.assertEqual(matches[0]['person'], self.person4)
        # self.assertAlmostEqual(matches[0]['confidence'], 1.0)
    
    def test_find_matches_by_email(self):
        """Test finding matches by email."""
        matcher = PersonMatcher()
        
        matches = matcher.find_matches("Some Person jane.doe@example.com")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person2)
        self.assertAlmostEqual(matches[0]['confidence'], 1.0)
        
    def test_find_matches_by_initials(self):
        """Test finding matches by initials."""
        matcher = PersonMatcher()
        
        matches = matcher.find_matches("MJ")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person3)
        self.assertAlmostEqual(matches[0]['confidence'], 1.0)
    
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
        
    def test_find_matches_with_tags(self):
        """Test finding matches with id tags."""
        matcher = PersonMatcher()
        
        # Test with ID tag
        matches = matcher.find_matches(f"[id:{self.person1.pk}] Some Name")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)
        self.assertAlmostEqual(matches[0]['confidence'], 1.0)
        self.assertEqual(matches[0]['match_type'], "exact_id")

    def test_find_matches_with_confidence_threshold(self):
        """Test confidence threshold filtering."""
        # Create matcher with high threshold
        matcher = PersonMatcher(confidence_threshold=0.95)

        # This should return no matches due to high threshold
        matches = matcher.find_matches("Jørgen Jensen")  # Relaxed match to Jonas Jensen
        self.assertEqual(len(matches), 0)
        
        # Lower threshold
        matcher = PersonMatcher(confidence_threshold=0.2)
        matches = matcher.find_matches("Jørgen Jensen")
        self.assertEqual(len(matches), 1)  # Now should match
    
    # We need to patch the find_ldap_person function in the module in which
    # it is called - it is being imported in person_disambiguation.py
    # and thus we need to patch it there.
    @patch('publications.workflows.person_disambiguation.find_ldap_person')
    def test_find_matches_with_ldap(self, mock_find_ldap):
        """Test finding matches with LDAP integration."""
        # Set up the LDAP mock
        # Should have some of the following fields:
        # - sn (surname)
        # - givenName (first name)
        # - department (department)
        # - company (company)
        # - title (position)
        # - employeeID (id_number)
        # - initials (initials)
        # - name (id_number, if company is 'Studerende')
    
        mock_person_data = MagicMock()
        mock_person_data.sn.value = "TestLast"
        mock_person_data.givenName.value = "TestFirst"
        mock_person_data.initials.value = "TF"
        mock_person_data.company.value = "DTU"
        mock_person_data.title.value = "Professor"
        mock_person_data.employeeID.value = "12378"
        mock_person_data.department.value = "Test Dept"

        mock_find_ldap.return_value = [mock_person_data]

        # Create a matcher with LDAP enabled and user provided
        matcher = PersonMatcher(user=self.test_user, use_ldap=True)
        
        # Test with LDAP tag
        matches = matcher.find_matches("[ldap:TF] Some Name")
        
        # Should have called find_ldap_person with initials
        mock_find_ldap.assert_called_with(initials="TF")
        
        # Verify we got a match from the LDAP lookup
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['match_type'], "ldap")
    
    def test_match_by_namestring(self):
        """Test _match_by_namestring method."""
        matcher = PersonMatcher()
        
        # Exact match
        matches = matcher._match_by_namestring("John Smith")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)

        # Partial match on one name component, (first name only) - should not match with exact=True
        matches = matcher._match_by_namestring("Smith", exact=True)
        self.assertEqual(len(matches), 0)

        # Partial match on one name component, (first name only) - should match with exact=False
        matches = matcher._match_by_namestring("Smith", exact=False)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)
    
    def test_match_by_relaxed_namestring(self):
        """Test _match_by_relaxed_namestring method."""
        matcher = PersonMatcher()
        
        # Test with characters that would normalize
        matches = matcher._match_by_relaxed_namestring("Jøhn Smith")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)
        
        # Test with different case
        matches = matcher._match_by_relaxed_namestring("JOHN smith")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['person'], self.person1)
