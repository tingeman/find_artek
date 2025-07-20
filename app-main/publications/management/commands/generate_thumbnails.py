import os
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.files.storage import default_storage
from publications.models import Publication
from PIL import Image
import sys

# Set up logging
logger = logging.getLogger(__name__)

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False


class Command(BaseCommand):
    help = 'Generate thumbnails for publications missing them'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate existing thumbnails'
        )
        parser.add_argument(
            '--publication-id',
            type=int,
            help='Generate thumbnail for specific publication ID'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress information'
        )
        parser.add_argument(
            '--height',
            type=int,
            default=400,
            help='Height of generated thumbnails in pixels (default: 400)'
        )
    
    def handle(self, *args, **options):
        if not PDF2IMAGE_AVAILABLE:
            raise CommandError(
                "pdf2image package is not installed. "
                "Please install it with: pip install pdf2image\n"
                "You may also need to install poppler-utils system package."
            )
        
        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        self.dry_run = options.get('dry_run', False)
        self.force = options.get('force', False)
        self.thumbnail_height = options.get('height', 400)
        
        # Validate height parameter
        if self.thumbnail_height < 50 or self.thumbnail_height > 2000:
            raise CommandError("Height must be between 50 and 2000 pixels")
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE: No files will be created or modified")
            )
        
        if self.thumbnail_height != 400:
            self.stdout.write(f"Using custom thumbnail height: {self.thumbnail_height}px")
        
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
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for publication in publications:
            try:
                result = self.process_publication(publication)
                if result == 'success':
                    success_count += 1
                elif result == 'skipped':
                    skip_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Unexpected error processing publication {publication.id}: {str(e)}"
                    )
                )
                logger.error(f"Unexpected error processing publication {publication.id}: {str(e)}")
        
        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS(f"SUMMARY:"))
        self.stdout.write(f"  Successful: {success_count}")
        self.stdout.write(f"  Skipped: {skip_count}")
        self.stdout.write(f"  Errors: {error_count}")
        self.stdout.write("="*50)
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"There were {error_count} errors. Check the logs for details."
                )
            )
    
    def process_publication(self, publication):
        """Process a single publication and return 'success', 'skipped', or 'error'"""
        
        if not publication.file:
            if self.verbose:
                self.stdout.write(f"  Publication {publication.id} has no file attached")
            return 'skipped'
        
        # Build file paths
        pdf_path = os.path.join(settings.MEDIA_ROOT, publication.file.file.name)
        thumb_dir = os.path.join(settings.MEDIA_ROOT, f'reports/{publication.year}/thumbs')
        
        # Use publication number for thumbnail name (canonical naming)
        thumb_path = os.path.join(thumb_dir, f'{publication.number}_thumb.jpg')
        
        # Check if PDF file exists
        if not os.path.exists(pdf_path):
            self.stdout.write(
                self.style.ERROR(
                    f"  Publication {publication.id}: PDF file not found at {pdf_path}"
                )
            )
            logger.error(f"PDF file not found for publication {publication.id}: {pdf_path}")
            return 'error'
        
        # Check if thumbnail already exists
        if os.path.exists(thumb_path) and not self.force:
            if self.verbose:
                self.stdout.write(f"  Publication {publication.id}: Thumbnail already exists (use --force to regenerate)")
            return 'skipped'
        
        # Generate thumbnail
        if self.verbose or self.verbosity >= 2:
            self.stdout.write(f"  Processing publication {publication.id} ({publication.number})...")
        
        if self.dry_run:
            self.stdout.write(f"    Would generate: {thumb_path}")
            return 'success'
        
        try:
            success = self.generate_thumbnail(pdf_path, thumb_path, publication)
            if success:
                if self.verbose or self.verbosity >= 2:
                    self.stdout.write(
                        self.style.SUCCESS(f"    Generated thumbnail: {thumb_path}")
                    )
                return 'success'
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Publication {publication.id}: Failed to generate thumbnail"
                    )
                )
                return 'error'
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"  Publication {publication.id}: Error generating thumbnail: {str(e)}"
                )
            )
            logger.error(f"Error generating thumbnail for publication {publication.id}: {str(e)}")
            return 'error'
    
    def generate_thumbnail(self, pdf_path, thumb_path, publication):
        """Generate thumbnail from PDF file"""
        
        try:
            # Create thumbnail directory if it doesn't exist
            thumb_dir = os.path.dirname(thumb_path)
            os.makedirs(thumb_dir, exist_ok=True)
            
            # Convert first page of PDF to image
            # Using DPI=150 for good quality without being too large
            pages = convert_from_path(
                pdf_path, 
                first_page=1, 
                last_page=1, 
                dpi=150,
                thread_count=1  # Use single thread to avoid memory issues
            )
            
            if not pages:
                logger.error(f"No pages found in PDF: {pdf_path}")
                return False
            
            # Get the first (and only) page
            image = pages[0]
            
            # Calculate new dimensions (configurable height, maintain aspect ratio)
            aspect_ratio = image.width / image.height
            new_width = int(self.thumbnail_height * aspect_ratio)
            new_height = self.thumbnail_height
            
            # Resize image
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save as JPEG with good quality
            resized_image.save(
                thumb_path, 
                'JPEG', 
                quality=85, 
                optimize=True,
                progressive=True
            )
            
            # Verify the file was created
            if os.path.exists(thumb_path):
                file_size = os.path.getsize(thumb_path)
                if self.verbose:
                    self.stdout.write(f"    Thumbnail created: {file_size} bytes")
                return True
            else:
                logger.error(f"Thumbnail file was not created: {thumb_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error in generate_thumbnail: {str(e)}")
            # Clean up partial file if it exists
            if os.path.exists(thumb_path):
                try:
                    os.remove(thumb_path)
                except:
                    pass
            raise e
