import os
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from publications.models import Publication

# Set up logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Normalize PDF filenames to match publication number format (XX-YY.pdf)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be renamed without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each publication',
        )
        parser.add_argument(
            '--publication-id',
            type=int,
            help='Process only a specific publication ID',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force processing even if target filename already exists',
        )

    def handle(self, *args, **options):
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise CommandError(
                "pdf2image is required but not installed.\n"
                "Please install it with: pip install pdf2image\n"
                "You may also need to install poppler-utils system package."
            )
        
        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        self.dry_run = options.get('dry_run', False)
        self.force = options.get('force', False)
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE: No files will be renamed or database updated")
            )
        
        # Get publications to process
        if options.get('publication_id'):
            try:
                publications = [Publication.objects.get(id=options['publication_id'])]
                self.stdout.write(f"Processing single publication ID: {options['publication_id']}")
            except Publication.DoesNotExist:
                raise CommandError(f"Publication with ID {options['publication_id']} does not exist")
        else:
            publications = Publication.objects.filter(file__isnull=False).select_related('file')
            self.stdout.write(f"Processing {publications.count()} publications with PDF files")
        
        # Track results
        results = {
            'processed': 0,
            'renamed': 0,
            'already_correct': 0,
            'errors': 0,
            'skipped': 0
        }
        
        for publication in publications:
            result = self.process_publication(publication)
            results[result] += 1
            results['processed'] += 1
        
        # Print summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write("SUMMARY:")
        self.stdout.write(f"  Processed: {results['processed']}")
        self.stdout.write(f"  Renamed: {results['renamed']}")
        self.stdout.write(f"  Already correct: {results['already_correct']}")
        self.stdout.write(f"  Skipped: {results['skipped']}")
        self.stdout.write(f"  Errors: {results['errors']}")
        self.stdout.write("="*50)

    def process_publication(self, publication):
        """Process a single publication to normalize its PDF filename"""
        
        if self.verbose:
            self.stdout.write(f"  Processing publication {publication.id} ({publication.number})...")
        
        # Check if publication has a file
        if not publication.file:
            if self.verbose:
                self.stdout.write(f"    Skipped: No file attached")
            return 'skipped'
        
        # Get current file path
        current_filename = publication.file.file.name
        current_full_path = os.path.join(settings.MEDIA_ROOT, current_filename)
        
        # Check if file exists on disk
        if not os.path.exists(current_full_path):
            self.stdout.write(
                self.style.ERROR(f"  Publication {publication.id} ({publication.number}): PDF file not found at {current_full_path}")
            )
            logger.error(f"PDF file not found for publication {publication.id}: {current_full_path}")
            return 'errors'
        
        # Generate expected filename
        expected_basename = f"{publication.number}.pdf"
        
        # Extract directory from current path
        current_dir = os.path.dirname(current_filename)
        expected_filename = os.path.join(current_dir, expected_basename)
        expected_full_path = os.path.join(settings.MEDIA_ROOT, expected_filename)
        
        # Check if already correctly named
        current_basename = os.path.basename(current_filename)
        if current_basename == expected_basename:
            if self.verbose:
                self.stdout.write(f"    Already correct: {current_basename}")
            return 'already_correct'
        
        # Check if target file already exists
        if os.path.exists(expected_full_path) and not self.force:
            self.stdout.write(
                self.style.WARNING(
                    f"  Publication {publication.id} ({publication.number}): Target file already exists: {expected_basename} "
                    f"(use --force to overwrite)"
                )
            )
            return 'skipped'
        
        # Show what would be done (always show when changes are needed)
        self.stdout.write(f"  Publication {publication.id} ({publication.number}): {current_basename} -> {expected_basename}")
        
        if self.dry_run:
            return 'renamed'
        
        # Perform the rename operation
        try:
            with transaction.atomic():
                # Rename the file on disk
                if os.path.exists(expected_full_path) and self.force:
                    os.remove(expected_full_path)
                    if self.verbose:
                        self.stdout.write(f"    Removed existing target file")
                
                os.rename(current_full_path, expected_full_path)
                
                # Update the database
                publication.file.file.name = expected_filename
                publication.file.save()
                
                if self.verbose:
                    self.stdout.write(f"    Successfully renamed: {current_basename} -> {expected_basename}")
                
                logger.info(f"Renamed PDF for publication {publication.id}: {current_basename} -> {expected_basename}")
                
        except OSError as e:
            self.stdout.write(
                self.style.ERROR(f"  Publication {publication.id} ({publication.number}): Error renaming file: {e}")
            )
            logger.error(f"Error renaming PDF for publication {publication.id}: {e}")
            return 'errors'
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"  Publication {publication.id} ({publication.number}): Database error: {e}")
            )
            logger.error(f"Database error for publication {publication.id}: {e}")
            return 'errors'
        
        return 'renamed'
