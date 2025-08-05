from django.core.management.base import BaseCommand
from django.conf import settings
from publications.models import Publication, FileObject
import os
import time
import shutil


class Command(BaseCommand):
    help = 'Clean up orphaned temporary files in the media/temp directory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-age',
            type=int,
            default=3600,  # 1 hour in seconds
            help='Maximum age of temporary files to keep (in seconds, default: 3600)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting files'
        )

    def handle(self, *args, **options):
        max_age = options['max_age']
        dry_run = options['dry_run']
        
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        
        if not os.path.exists(temp_dir):
            self.stdout.write(
                self.style.SUCCESS(f'Temp directory {temp_dir} does not exist. Nothing to clean.')
            )
            return
        
        current_time = time.time()
        deleted_count = 0
        deleted_size = 0
        
        self.stdout.write(f'Scanning temp directory: {temp_dir}')
        self.stdout.write(f'Max age: {max_age} seconds ({max_age/3600:.1f} hours)')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No files will actually be deleted'))
        
        # Get all temp publication IDs to check which ones are still in session/workflow
        temp_publication_ids = set()
        for pub in Publication.objects.filter(title__startswith='temp_'):
            temp_publication_ids.add(pub.id)
        
        # Scan all subdirectories in temp folder
        for root, dirs, files in os.walk(temp_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                
                try:
                    # Get file age
                    file_age = current_time - os.path.getctime(file_path)
                    file_size = os.path.getsize(file_path)
                    
                    should_delete = False
                    reason = ""
                    
                    # Check if file is old enough
                    if file_age > max_age:
                        should_delete = True
                        reason = f"older than {max_age} seconds"
                    
                    # Check if the file is associated with a temp publication that no longer exists
                    # Extract timestamp from directory name if possible
                    rel_path = os.path.relpath(file_path, temp_dir)
                    dir_name = os.path.dirname(rel_path)
                    
                    # Check if there are any FileObjects pointing to this file
                    file_objects = FileObject.objects.filter(file__contains=rel_path)
                    if file_objects.exists():
                        # Check if any of these FileObjects belong to temp publications
                        for file_obj in file_objects:
                            if hasattr(file_obj, 'publication_set'):
                                pubs = file_obj.publication_set.filter(title__startswith='temp_')
                                if pubs.exists():
                                    # Check if any temp publications are older than max_age
                                    for pub in pubs:
                                        pub_age = current_time - pub.created_at.timestamp()
                                        if pub_age > max_age:
                                            should_delete = True
                                            reason = f"associated temp publication is older than {max_age} seconds"
                                            break
                    else:
                        # No FileObject references this file, check age
                        if file_age > max_age:
                            should_delete = True
                            reason = f"orphaned file older than {max_age} seconds"
                    
                    if should_delete:
                        if dry_run:
                            self.stdout.write(
                                f'Would delete: {file_path} ({file_size} bytes) - {reason}'
                            )
                        else:
                            os.remove(file_path)
                            self.stdout.write(
                                f'Deleted: {file_path} ({file_size} bytes) - {reason}'
                            )
                        
                        deleted_count += 1
                        deleted_size += file_size
                    
                except (OSError, IOError) as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error processing {file_path}: {e}')
                    )
        
        # Clean up empty directories
        for root, dirs, files in os.walk(temp_dir, topdown=False):
            if root != temp_dir:  # Don't delete the temp directory itself
                try:
                    if not os.listdir(root):  # Directory is empty
                        if dry_run:
                            self.stdout.write(f'Would remove empty directory: {root}')
                        else:
                            os.rmdir(root)
                            self.stdout.write(f'Removed empty directory: {root}')
                except OSError as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error removing directory {root}: {e}')
                    )
        
        # Clean up orphaned temp publications
        if not dry_run:
            temp_pubs = Publication.objects.filter(title__startswith='temp_')
            for pub in temp_pubs:
                pub_age = current_time - pub.created_at.timestamp()
                if pub_age > max_age:
                    self.stdout.write(f'Deleting orphaned temp publication: {pub.title}')
                    pub.delete()
        
        # Summary
        size_mb = deleted_size / (1024 * 1024)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'DRY RUN: Would delete {deleted_count} files ({size_mb:.2f} MB)'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Cleanup complete: Deleted {deleted_count} files ({size_mb:.2f} MB)'
                )
            )
