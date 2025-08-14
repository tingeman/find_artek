#!/usr/bin/env python
"""
Demo script for testing the person disambiguation system.

This script provides a simple command-line interface to test the person matching functionality.
It allows you to:
1. Test name normalization
2. Find matches for a person name
3. Update relaxed fields for a specific person

Usage:
    python demo_person_matching.py normalize "Jørgen Ægir"
    python demo_person_matching.py find "John Smith"
    python demo_person_matching.py update <person_id>
"""

import os
import sys
import django
import argparse

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "find_artek.settings")
django.setup()

from publications.models import Person
from publications.workflows.person_disambiguation import NameNormalizer, PersonMatcher


def normalize_name(name):
    """Normalize a name and show the results."""
    print(f"Original name: {name}")
    
    normalized = NameNormalizer.normalize_name(name)
    print(f"Normalized: {normalized}")
    
    components = NameNormalizer.get_relaxed_name_components(name)
    print(f"Relaxed components:")
    print(f"  First relaxed: {components['first_relaxed']}")
    print(f"  Last relaxed: {components['last_relaxed']}")


def find_matches(name):
    """Find potential matches for a name and show the results."""
    print(f"Finding matches for: {name}")
    
    matcher = PersonMatcher()
    matches = matcher.find_matches(name)
    
    if not matches:
        print("No matches found.")
        return
    
    print(f"Found {len(matches)} match(es):")
    for i, match in enumerate(matches, 1):
        person = match['person']
        confidence = match['confidence']
        match_type = match['match_type']
        
        print(f"\n{i}. Person #{person.pk}: {person.first} {person.last}")
        print(f"   Confidence: {confidence:.2f} ({match_type})")
        print(f"   Email: {person.email or 'N/A'}")
        print(f"   ID Number: {getattr(person, 'id_number', 'N/A')}")
        print(f"   Initials: {getattr(person, 'initials', 'N/A')}")
        print(f"   Relaxed fields: {person.first_relaxed}/{person.last_relaxed}")


def update_person(person_id):
    """Update the relaxed fields for a specific person."""
    try:
        person = Person.objects.get(pk=person_id)
    except Person.DoesNotExist:
        print(f"Error: Person with ID {person_id} not found.")
        return
    
    # Show before state
    print(f"Person #{person.pk}: {person.first} {person.last}")
    print(f"Before: first_relaxed={person.first_relaxed}, last_relaxed={person.last_relaxed}")
    
    # Update the relaxed fields
    NameNormalizer.update_person_relaxed_fields(person)
    
    # Show after state (without saving)
    print(f"After: first_relaxed={person.first_relaxed}, last_relaxed={person.last_relaxed}")
    
    # Ask for confirmation
    confirm = input("\nSave these changes? (y/n): ")
    if confirm.lower() == 'y':
        person.save(update_fields=['first_relaxed', 'last_relaxed'])
        print("Changes saved.")
    else:
        print("Changes discarded.")


def main():
    parser = argparse.ArgumentParser(description="Test the person disambiguation system")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Normalize command
    normalize_parser = subparsers.add_parser("normalize", help="Normalize a name")
    normalize_parser.add_argument("name", help="Name to normalize")
    
    # Find command
    find_parser = subparsers.add_parser("find", help="Find matches for a name")
    find_parser.add_argument("name", help="Name to find matches for")
    
    # Update command
    update_parser = subparsers.add_parser("update", help="Update relaxed fields for a person")
    update_parser.add_argument("person_id", type=int, help="ID of the person to update")
    
    args = parser.parse_args()
    
    if args.command == "normalize":
        normalize_name(args.name)
    elif args.command == "find":
        find_matches(args.name)
    elif args.command == "update":
        update_person(args.person_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
