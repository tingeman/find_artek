#!/usr/bin/env python
"""
Test script for enhanced person matching algorithm
"""
import os
import sys
import django

# Setup Django environment
sys.path.append('/workspace/app-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'find_artek.development_settings')
django.setup()

from publications.forms import PersonSelectForm
from publications.models import Person

def test_enhanced_matching():
    """Test the enhanced person matching functionality"""
    print("=== Enhanced Person Matching Algorithm Test ===\n")
    
    # Create a test form instance
    form = PersonSelectForm()
    
    # Test cases
    test_names = [
        "John Smith",
        "J. Smith", 
        "Smith, John",
        "John A. Smith",
        "João da Silva",  # Test special characters
        "12345",  # Test ID number
        "j.smith@example.com",  # Test email
        "Müller, Hans",  # Test special characters
    ]
    
    print("Existing persons in database:")
    existing_persons = Person.objects.all()[:10]  # Show first 10
    for person in existing_persons:
        print(f"  - {person.get_full_name()} [pk:{person.pk}] (ID: {person.id_number}, Email: {person.email})")
    
    if not existing_persons:
        print("  No persons found in database")
    
    print(f"\nTotal persons in database: {Person.objects.count()}\n")
    
    for test_name in test_names:
        print(f"Testing name: '{test_name}'")
        print("-" * 40)
        
        try:
            matches = form.get_person_matches(test_name)
            
            if matches:
                print(f"Found {len(matches)} matches:")
                for i, match in enumerate(matches[:5], 1):  # Show top 5
                    person = match['person']
                    confidence = match['confidence']
                    match_type = match['match_type']
                    notes = match.get('notes', '')
                    
                    print(f"  {i}. {person.get_full_name()}")
                    print(f"     Confidence: {confidence:.0%}")
                    print(f"     Match Type: {match_type}")
                    print(f"     PK: {person.pk}, Email: {person.email}, ID: {person.id_number}")
                    if notes:
                        print(f"     Notes: {notes}")
                    print()
            else:
                print("No matches found")
                
        except Exception as e:
            print(f"Error testing '{test_name}': {e}")
        
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    test_enhanced_matching()
