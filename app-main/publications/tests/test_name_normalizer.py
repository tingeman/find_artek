"""
Tests for the NameNormalizer class in utils_person.py
"""

import unittest
from unittest.mock import MagicMock
from django.test import TestCase

from publications.models import Person
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
        self.assertEqual(NameNormalizer.normalize_name("José Müller-Straße"), "jose muller-strasse")

    def test_normalize_name_whitespace(self):
        """Test normalize_name handles whitespace correctly."""
        self.assertEqual(NameNormalizer.normalize_name("  John   Smith  "), "john smith")
        
    def test_clean_name(self):
        """Test clean_name removes tags and whitespace."""
        self.assertEqual(NameNormalizer.clean_name("[id:123] John Smith "), "John Smith")
        self.assertEqual(NameNormalizer.clean_name("John Smith [tag:value]"), "John Smith")
        
    def test_get_tags(self):
        """Test get_tags extracts tags correctly."""
        tags = NameNormalizer.get_tags("John Smith [id:123] [type:student]")
        self.assertEqual(tags, {"id": "123", "type": "student"})
        
        # Empty case
        self.assertEqual(NameNormalizer.get_tags("John Smith"), {})

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
        
    def test_get_relaxed_name_components_with_tags(self):
        """Test get_relaxed_name_components handles tags."""
        result = NameNormalizer.get_relaxed_name_components("[id:123] John Smith")
        self.assertEqual(result, {"first_relaxed": "j", "last_relaxed": "smith"})

    def test_get_all_name_components(self):
        """Test get_all_name_components parses name correctly."""
        result = NameNormalizer.get_all_name_components("John A. Smith")
        
        # Check standard components
        self.assertEqual(result["first"], "John")
        self.assertEqual(result["middle"], "A.")
        self.assertEqual(result["last"], "Smith")
        
        # Check relaxed components
        self.assertEqual(result["first_relaxed"], "j")
        self.assertEqual(result["last_relaxed"], "smith")
        
    def test_get_all_name_components_with_optionals(self):
        """Test get_all_name_components with optional parameters."""
        result = NameNormalizer.get_all_name_components(
            "John Smith", 
            initials="JS", 
            id_number="s12345"
        )
        
        # Check optional fields
        self.assertEqual(result["initials"], "JS")
        self.assertEqual(result["id_number"], "s12345")
        
    def test_get_all_name_components_complex(self):
        """Test get_all_name_components with a complex name."""
        result = NameNormalizer.get_all_name_components("von Neumann, John")
        
        # This should correctly parse the name with last name first
        self.assertEqual(result["first"], "John")
        self.assertEqual(result["prelast"], "von")
        self.assertEqual(result["last"], "Neumann")
        self.assertEqual(result["first_relaxed"], "j")
        self.assertEqual(result["last_relaxed"], "neumann")

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
