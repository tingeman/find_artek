from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from publications.models import Publication
from publications.utils import generate_next_report_number, validate_report_number_format


class Command(BaseCommand):
    help = 'Generate missing report numbers for publications that don\'t have proper YY-NN format numbers'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even for publications that already have numbers',
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Process only publications from a specific year',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)
        specific_year = options.get('year')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE: No publications will be updated")
            )
        
        # Build queryset
        queryset = Publication.objects.all()
        
        if specific_year:
            queryset = queryset.filter(year=specific_year)
            self.stdout.write(f"Processing publications from year {specific_year}")
        else:
            self.stdout.write("Processing all publications")
        
        # Filter publications that need report numbers
        publications_to_update = []
        
        for publication in queryset:
            needs_update = False
            reason = ""
            
            if not publication.number:
                needs_update = True
                reason = "No report number"
            elif force:
                needs_update = True
                reason = "Force update requested"
            else:
                # Check if number follows proper format
                is_valid, _ = validate_report_number_format(publication.number)
                if not is_valid:
                    needs_update = True
                    reason = f"Invalid format: {publication.number}"
            
            if needs_update:
                if not publication.year:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Publication {publication.id} ({publication.title[:50]}...): "
                            f"Cannot generate number - missing year"
                        )
                    )
                    continue
                
                publications_to_update.append((publication, reason))
        
        if not publications_to_update:
            self.stdout.write(
                self.style.SUCCESS("No publications need report number updates")
            )
            return
        
        self.stdout.write(f"Found {len(publications_to_update)} publications to update:")
        
        # Group by year for better number generation
        by_year = {}
        for pub, reason in publications_to_update:
            year = pub.year
            if year not in by_year:
                by_year[year] = []
            by_year[year].append((pub, reason))
        
        updated_count = 0
        
        # Generate number assignments for all publications (both dry-run and real)
        # This ensures consistent numbering preview in dry-run mode
        from publications.utils import generate_batch_report_numbers
        
        # Prepare data for batch generation: extract just the publications by year
        publications_by_year = {}
        for year, pub_reason_pairs in by_year.items():
            publications_by_year[year] = [pub for pub, reason in pub_reason_pairs]
        
        # Generate all number assignments at once
        number_assignments = generate_batch_report_numbers(publications_by_year)
        
        for year in sorted(by_year.keys()):
            publications_for_year = by_year[year]
            self.stdout.write(f"\nProcessing {len(publications_for_year)} publications for year {year}:")
            
            for publication, reason in publications_for_year:
                old_number = publication.number or "(none)"
                
                # Use pre-calculated batch assignments for both dry-run and real execution
                new_number = number_assignments.get(publication.id)
                if not new_number:
                    self.stdout.write(
                        self.style.ERROR(
                            f"    No number assigned for publication {publication.id}"
                        )
                    )
                    continue
                
                self.stdout.write(
                    f"  Publication {publication.id}: {old_number} -> {new_number} ({reason})"
                )
                
                if not dry_run:
                    try:
                        with transaction.atomic():
                            publication.number = new_number
                            publication.save(update_fields=['number'])
                            updated_count += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"    Error updating publication {publication.id}: {e}"
                            )
                        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN: Would have updated {len(publications_to_update)} publications"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully updated {updated_count} publications"
                )
            )
