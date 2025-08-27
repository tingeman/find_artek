"""
Management command to update first_relaxed and last_relaxed fields for all Person objects.

This command uses the new NameNormalizer class to ensure consistent name normalization
across the application.
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from publications.models import Person
from publications.workflows.person_disambiguation import NameNormalizer

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update first_relaxed and last_relaxed fields for all Person objects using the new NameNormalizer'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of Person objects to process in each batch',
        )
        
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        # Get total count for progress reporting
        total_persons = Person.objects.count()
        self.stdout.write(f"Found {total_persons} person records to process")
        
        if dry_run:
            self.stdout.write("DRY RUN - no changes will be made to the database")
            
        # Process in batches to avoid memory issues with large datasets
        processed_count = 0
        updated_count = 0
        
        # Use batches with offsets to efficiently process large datasets
        offset = 0
        
        while True:
            # Get the next batch
            persons_batch = Person.objects.all()[offset:offset+batch_size]
            if not persons_batch:
                break  # No more persons to process
                
            # Process this batch
            with transaction.atomic():
                for person in persons_batch:
                    processed_count += 1
                    
                    # Calculate new relaxed fields
                    old_first_relaxed = person.first_relaxed
                    old_last_relaxed = person.last_relaxed
                    
                    # Update the person object using the normalizer
                    NameNormalizer.update_person_relaxed_fields(person)
                    
                    # Check if anything changed
                    if person.first_relaxed != old_first_relaxed or person.last_relaxed != old_last_relaxed:
                        if not dry_run:
                            person.save(update_fields=['first_relaxed', 'last_relaxed'])
                        updated_count += 1
                        
                        # In verbose mode, show what changed
                        if options['verbosity'] >= 2:
                            self.stdout.write(
                                f"Person {person.pk}: "
                                f"'{old_first_relaxed}'/'{old_last_relaxed}' → "
                                f"'{person.first_relaxed}'/'{person.last_relaxed}'"
                            )
                            
            # Report progress
            if options['verbosity'] >= 1 and processed_count % (batch_size * 10) == 0:
                self.stdout.write(f"Processed {processed_count}/{total_persons} persons...")
                
            # Move to the next batch
            offset += batch_size
            
        # Final report
        action = "Would update" if dry_run else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"Done! Processed {processed_count} person records. "
            f"{action} {updated_count} records with new relaxed names."
        ))
