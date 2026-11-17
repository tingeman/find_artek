#!/usr/bin/env python
"""
Manual verification script for the person disambiguation implementation.

This script demonstrates how the relaxed name matching works with initial matching integrated.
Run it manually to test and verify the implementation without relying on the test framework.

Usage:
    python verify_disambiguation.py
"""

import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "find_artek.development_settings")
django.setup()

from django.db import connection
from publications.models import Person
from publications.workflows.person_disambiguation import NameNormalizer, PersonMatcher

def setup_test_data():
    """Create test data for demonstration"""
    # Clean existing test data
    Person.objects.filter(first__in=["TestJohn", "TestJane", "TestMichael", "TestJennifer"]).delete()
    
    # Create test persons
    person1 = Person.objects.create(
        first="TestJohn", 
        last="Smith",
        first_relaxed="t",
        last_relaxed="smith",
        email="testjohn.smith@example.com"
    )
    
    person2 = Person.objects.create(
        first="TestJane", 
        last="Doe",
        first_relaxed="t",
        last_relaxed="doe",
        email="testjane.doe@example.com",
        id_number="s12345"
    )
    
    person3 = Person.objects.create(
        first="TestMichael", 
        last="Johnson",
        first_relaxed="t",
        last_relaxed="johnson",
        initials="MJ"
    )
    
    person4 = Person.objects.create(
        first="TestJennifer", 
        last="Smith",
        first_relaxed="t", 
        last_relaxed="smith"
    )
    
    return [person1, person2, person3, person4]

def run_tests():
    """Run manual tests and print results"""
    print("\n=== PERSON DISAMBIGUATION VERIFICATION ===\n")
    
    # Create test data
    persons = setup_test_data()
    print(f"Created {len(persons)} test persons:")
    for p in persons:
        print(f"  - {p.first} {p.last} (relaxed: {p.first_relaxed}/{p.last_relaxed})")
    
    # Create matcher
    matcher = PersonMatcher()
    
    # Test 1: Initial-based matching within relaxed matching
    print("\nTEST 1: Initial-based matching within relaxed matching")
    print("Searching for 'TestJ Smith' - should match both TestJohn and TestJennifer Smith")
    matches = matcher._match_by_relaxed_name("TestJ Smith")
    print(f"Found {len(matches)} matches:")
    for m in matches:
        person = m['person']
        confidence = m['confidence']
        match_type = m['match_type']
        print(f"  - {person.first} {person.last} (confidence: {confidence:.2f}, type: {match_type})")
    
    # Test 2: Company initials vs. initial matching
    print("\nTEST 2: Company initials vs. initial matching")
    print("Searching for 'MJ TestPerson' - should match TestMichael Johnson by company initials")
    initials_matches = matcher._match_by_company_initials("MJ TestPerson")
    print(f"Found {len(initials_matches)} company initial matches:")
    for m in initials_matches:
        person = m['person']
        confidence = m['confidence']
        print(f"  - {person.first} {person.last} (confidence: {confidence:.2f}, type: {m['match_type']})")
    
    # Test 3: Full matching pipeline with ranking
    print("\nTEST 3: Full matching pipeline")
    print("Searching for 'TestJ Smith s12345 MJ' - should find all matches with proper ranking")
    all_matches = matcher.find_matches("TestJ Smith s12345 MJ")
    print(f"Found {len(all_matches)} total matches (ranked by confidence):")
    for i, m in enumerate(all_matches, 1):
        person = m['person']
        confidence = m['confidence']
        match_type = m['match_type']
        print(f"  {i}. {person.first} {person.last} (confidence: {confidence:.2f}, type: {match_type})")
    
    # Clean up test data
    for p in persons:
        p.delete()
    print("\nTest data cleaned up.")
    
    print("\n=== VERIFICATION COMPLETE ===\n")

if __name__ == "__main__":
    run_tests()
