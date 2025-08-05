#!/usr/bin/env python
"""
Test script with actual names from the database
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

def test_with_existing_names():
    """Test with names that exist in the database"""
    print("=== Testing with Existing Database Names ===\n")
    
    form = PersonSelectForm()
    
    # Test with names that exist in the database
    test_person = Person.objects.first()
    if test_person:
        full_name = test_person.get_full_name()
        print(f"Testing exact match with: '{full_name}'")
        print(f"Original person: {test_person} [pk:{test_person.pk}]")
        print("-" * 50)
        
        matches = form.get_person_matches(full_name)
        if matches:
            print(f"Found {len(matches)} matches:")
            for i, match in enumerate(matches, 1):
                person = match['person']
                confidence = match['confidence']
                match_type = match['match_type']
                print(f"  {i}. {person.get_full_name()}")
                print(f"     Confidence: {confidence:.0%}, Type: {match_type}")
                print(f"     PK: {person.pk}")
        print("\n" + "="*60 + "\n")
        
        # Test with first name + last name
        if test_person.first and test_person.last:
            partial_name = f"{test_person.first} {test_person.last}"
            print(f"Testing with first+last only: '{partial_name}'")
            print("-" * 50)
            
            matches = form.get_person_matches(partial_name)
            if matches:
                print(f"Found {len(matches)} matches:")
                for i, match in enumerate(matches[:5], 1):  # Top 5
                    person = match['person']
                    confidence = match['confidence']
                    match_type = match['match_type']
                    print(f"  {i}. {person.get_full_name()}")
                    print(f"     Confidence: {confidence:.0%}, Type: {match_type}")
            print("\n" + "="*60 + "\n")
        
        # Test with just first initial + last name
        if test_person.first and test_person.last:
            initial_name = f"{test_person.first[0]}. {test_person.last}"
            print(f"Testing with initial+last: '{initial_name}'")
            print("-" * 50)
            
            matches = form.get_person_matches(initial_name)
            if matches:
                print(f"Found {len(matches)} matches:")
                for i, match in enumerate(matches[:3], 1):  # Top 3
                    person = match['person']
                    confidence = match['confidence']
                    match_type = match['match_type']
                    print(f"  {i}. {person.get_full_name()}")
                    print(f"     Confidence: {confidence:.0%}, Type: {match_type}")
            print("\n" + "="*60 + "\n")

def test_specific_names():
    """Test specific name matching scenarios"""
    print("=== Testing Specific Name Matching Scenarios ===\n")
    
    form = PersonSelectForm()
    
    # Check if our test persons exist in database
    test_targets = [
        "Frederik Ancker Agergaard",
        "Mads Albæk Sørensen", 
        "Brian Elmegård"
    ]
    
    found_targets = {}
    for target in test_targets:
        # Try to find by exact name match
        matches = form.get_person_matches(target)
        exact_matches = [m for m in matches if m['confidence'] >= 0.95]
        if exact_matches:
            found_targets[target] = exact_matches[0]['person']
            print(f"✓ Found target: {target} -> {exact_matches[0]['person'].get_full_name()} [pk:{exact_matches[0]['person'].pk}]")
    
    print(f"\nFound {len(found_targets)} of {len(test_targets)} target persons in database\n")
    
    # Test cases for Frederik Ancker Agergaard
    if "Frederik Ancker Agergaard" in found_targets:
        print("=== Testing Frederik Ancker Agergaard Matches ===")
        target_person = found_targets["Frederik Ancker Agergaard"]
        print(f"Target: {target_person.get_full_name()} [pk:{target_person.pk}]")
        
        test_searches = [
            "F. Ancker",
            "F. Agergaard", 
            "Frederik Agergaard",
            "Frederik Ancker",
            "F. A. Agergaard"
        ]
        
        for search_name in test_searches:
            print(f"\nSearching for: '{search_name}'")
            print("-" * 40)
            
            matches = form.get_person_matches(search_name)
            # Check if target person is in matches
            target_found = False
            for match in matches:
                if match['person'].pk == target_person.pk:
                    target_found = True
                    print(f"✓ TARGET FOUND: {match['person'].get_full_name()}")
                    print(f"  Confidence: {match['confidence']:.0%}, Type: {match['match_type']}")
                    print(f"  Notes: {match.get('notes', 'N/A')}")
                    break
            
            if not target_found:
                print("✗ TARGET NOT FOUND in matches")
                if matches:
                    print("  Other matches found:")
                    for i, match in enumerate(matches[:3], 1):
                        print(f"    {i}. {match['person'].get_full_name()} ({match['confidence']:.0%})")
                else:
                    print("  No matches found at all")
        
        print("\n" + "="*60 + "\n")
    
    # Test cases for Mads Albæk Sørensen  
    if "Mads Albæk Sørensen" in found_targets:
        print("=== Testing Mads Albæk Sørensen Matches (Special Characters) ===")
        target_person = found_targets["Mads Albæk Sørensen"]
        print(f"Target: {target_person.get_full_name()} [pk:{target_person.pk}]")
        
        test_searches = [
            "Mads Sørensen",
            "Mads Sorensen",  # ø -> o 
            "Mads Soerensen", # ø -> oe
            "Mads Albæk",
            "Mads Albaek"     # æ -> ae
        ]
        
        for search_name in test_searches:
            print(f"\nSearching for: '{search_name}'")
            print("-" * 40)
            
            matches = form.get_person_matches(search_name)
            # Check if target person is in matches
            target_found = False
            for match in matches:
                if match['person'].pk == target_person.pk:
                    target_found = True
                    print(f"✓ TARGET FOUND: {match['person'].get_full_name()}")
                    print(f"  Confidence: {match['confidence']:.0%}, Type: {match['match_type']}")
                    print(f"  Notes: {match.get('notes', 'N/A')}")
                    break
            
            if not target_found:
                print("✗ TARGET NOT FOUND in matches")
                if matches:
                    print("  Other matches found:")
                    for i, match in enumerate(matches[:3], 1):
                        print(f"    {i}. {match['person'].get_full_name()} ({match['confidence']:.0%})")
                else:
                    print("  No matches found at all")
        
        print("\n" + "="*60 + "\n")
    
    # Test cases for Brian Elmegård
    if "Brian Elmegård" in found_targets:
        print("=== Testing Brian Elmegård Matches (Special Characters) ===")
        target_person = found_targets["Brian Elmegård"]
        print(f"Target: {target_person.get_full_name()} [pk:{target_person.pk}]")
        
        test_searches = [
            "Brian Elmegård",   # exact
            "Brian Elmegaard",  # å -> aa
            "Brian Elmegard"    # å -> a
        ]
        
        for search_name in test_searches:
            print(f"\nSearching for: '{search_name}'")
            print("-" * 40)
            
            matches = form.get_person_matches(search_name)
            # Check if target person is in matches
            target_found = False
            for match in matches:
                if match['person'].pk == target_person.pk:
                    target_found = True
                    print(f"✓ TARGET FOUND: {match['person'].get_full_name()}")
                    print(f"  Confidence: {match['confidence']:.0%}, Type: {match['match_type']}")
                    print(f"  Notes: {match.get('notes', 'N/A')}")
                    break
            
            if not target_found:
                print("✗ TARGET NOT FOUND in matches")
                if matches:
                    print("  Other matches found:")
                    for i, match in enumerate(matches[:3], 1):
                        print(f"    {i}. {match['person'].get_full_name()} ({match['confidence']:.0%})")
                else:
                    print("  No matches found at all")
        
        print("\n" + "="*60 + "\n")

def check_database_for_test_names():
    """Check if our test target names exist in the database"""
    print("=== Database Check for Test Target Names ===\n")
    
    target_names = [
        "Frederik Ancker Agergaard",
        "Mads Albæk Sørensen", 
        "Brian Elmegård"
    ]
    
    for target_name in target_names:
        print(f"Checking for: '{target_name}'")
        
        # Try different search strategies
        parts = target_name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = parts[-1]
            
            # Search by first and last name
            matches = Person.objects.filter(
                first__icontains=first_name,
                last__icontains=last_name
            )
            
            if matches:
                print(f"  Found {len(matches)} potential matches:")
                for person in matches[:5]:  # Show top 5
                    print(f"    - {person.get_full_name()} [pk:{person.pk}]")
                    print(f"      Fields: first='{person.first}', middle='{person.middle}', last='{person.last}'")
            else:
                print("  No matches found")
        print()

if __name__ == "__main__":
    check_database_for_test_names()
    print("\n" + "="*80 + "\n")
    test_with_existing_names()
    print("\n" + "="*80 + "\n") 
    test_specific_names()
