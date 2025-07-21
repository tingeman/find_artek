import re
import os
from unidecode import unidecode
from django.db.models import Case, When, Value, IntegerField
from django.conf import settings
from django.core.files.storage import default_storage


class CaseInsensitively(object):
    """Wrap CaseInsensitively around an object to make comparisons
    case-insensitive.

    example:
    if CaseInsensitively('Hello world') in ['hello world', 'Hej Verden']:
        print "The if clause evaluates True!"

    """
    def __init__(self, s):
        self.__s = s.lower()

    def __hash__(self):
        return hash(self.__s)

    def __eq__(self, other):
        # ensure proper comparison between instances of this class
        try:
            other = other.__s
        except (TypeError, AttributeError):
            try:
                other = other.lower()
            except:
                pass
        return self.__s == other


class CyclicList(list):
    """Overloaded list class, which will wrap around
    when accessing indices larger than the length of
    list."""

#    from itertools import cycle

    def __getitem__(self, index):
        if isinstance(index, int):
            return list.__getitem__(self, index % len(self))
        else:
            raise TypeError("index must be int or slice")

    def __getslice__(self, i, j):
        newlist = []
        for k in range(i, j):
            newlist.append(self[k])
        return newlist


# Find "[tag:value]" items allowing for whitespace, extract tag and value.
re_tag_items = re.compile(r'\[\s*(?P<tag>[a-zA-Z]*?)\s*[:=]\s*(?P<value>.*?)\s*\]')

# Find "[tag:value]" strings allowing for whitespace (matching the entire string).
re_tag = re.compile(r'(?P<tag>\[\s*[a-zA-Z]*?\s*[:=]\s*.*?\s*\])')


def extract_tags(s):
    """Get all [tag:value] pairs in the string 's'
    and return as dictionary with key=tag and value=value.
    """
    return re.findall(re_tag_items, s)


def get_tag(s, tag, lower=True):
    """Get the value of [tag:value] for the tag-named passed in argument 'tag'
    or return None if not found
    """

    tags = extract_tags(s)
    if tags:
        # iterate over tag:value pairs
        if lower:  # all tag names converted to lower case
            for t, v in tags:
                if t.lower() == tag.lower():
                    return v
        else:  # no case change performed on input string
            for t, v in tags:
                if t == tag:
                    return v
    return None


def remove_tags(s):
    """Removes all [xx:xx] tags in a string and strips any whitespace from both
    ends of the string, returning the resulting string.
    """
    return re.sub(re_tag, "", s).strip()


def dk_unidecode(string):
    """use unidecode, but first exchange æÆ, øØ and åÅ with ae, oe and aa
    """
    kwargs = {'æ': 'ae', 'Æ': 'Ae',
              'ø': 'oe', 'Ø': 'Oe',
              'å': 'aa', 'Å': 'Aa'}

    for old, new in kwargs.items():
        string = string.replace(old, new)

    # now call regular unidecode
    return unidecode(string)


def create_ordered_queryset(model_class, pk_list):
    """
    Create an ordered QuerySet that preserves the order of the input pk_list.
    Uses Django's Case/When to order by the position in the original list.
    
    Args:
        model_class: The Django model class to query
        pk_list: List of primary keys in the desired order
        
    Returns:
        QuerySet: An ordered QuerySet that preserves the input order
        
    Example:
        # Get Person objects in specific order
        person_ids = [3, 1, 4, 2]
        ordered_persons = create_ordered_queryset(Person, person_ids)
        # Result will be Person objects in order [pk=3, pk=1, pk=4, pk=2]
    """
    if not pk_list:
        return model_class.objects.none()
    
    # Create Case/When clauses to preserve order
    preserved_order = Case(*[
        When(pk=pk, then=Value(i)) 
        for i, pk in enumerate(pk_list)
    ], output_field=IntegerField())
    
    # Filter and order the QuerySet
    queryset = model_class.objects.filter(pk__in=pk_list).annotate(
        preserved_order=preserved_order
    ).order_by('preserved_order')
    
    return queryset


def handle_publication_file_upload(publication, uploaded_file):
    """
    Handle the upload, renaming, and storage of a publication PDF file.
    
    Args:
        publication: The Publication instance
        uploaded_file: The uploaded file from the form
        
    Returns:
        FileObject: The created FileObject instance
    """
    if not uploaded_file:
        return None
        
    # Generate the new filename based on report number
    new_filename = f"{publication.number}.pdf"
    
    # Create the directory path: reports/YYYY/
    year_dir = f"reports/{publication.year}"
    file_path = os.path.join(year_dir, new_filename)
    
    # Ensure the directory exists
    full_dir_path = os.path.join(settings.MEDIA_ROOT, year_dir)
    os.makedirs(full_dir_path, exist_ok=True)
    
    # Save the file with the new name
    saved_path = default_storage.save(file_path, uploaded_file)
    
    # Create FileObject instance
    from publications.models import FileObject
    file_obj = FileObject.objects.create(
        file=saved_path,
        description=f"PDF file for report {publication.number} ({publication.year})"
    )
    
    return file_obj


def handle_appendix_file_upload(publication, uploaded_file):
    """
    Handle the upload and storage of an appendix file for a publication.
    Files are stored in: media/reports/{year}/{report_number}/filename.ext
    
    Note: For very large files (>100MB), we may need to implement 
    a secondary upload scheme with chunked uploads or streaming.
    
    Args:
        publication: The Publication instance
        uploaded_file: The uploaded file from the form
        
    Returns:
        FileObject: The created FileObject instance
    """
    if not uploaded_file:
        return None
        
    # Keep original filename for appendices
    original_filename = uploaded_file.name
    
    # Create the directory path: reports/YYYY/report_number/
    appendix_dir = f"reports/{publication.year}/{publication.number}"
    file_path = os.path.join(appendix_dir, original_filename)
    
    # Ensure the directory exists
    full_dir_path = os.path.join(settings.MEDIA_ROOT, appendix_dir)
    os.makedirs(full_dir_path, exist_ok=True)
    
    # Save the file with original name
    saved_path = default_storage.save(file_path, uploaded_file)
    
    # Create FileObject instance
    from publications.models import FileObject
    file_obj = FileObject.objects.create(
        file=saved_path,
        description=f"Appendix file for report {publication.number} ({publication.year})"
    )
    
    return file_obj


def handle_session_appendix_uploads(request, publication):
    """
    Process all appendix files stored in session and create FileObject instances.
    Links them to the publication via Appendenciesship.
    
    Args:
        request: The HTTP request object (for session access)
        publication: The Publication instance to attach files to
        
    Returns:
        list: List of created FileObject instances
    """
    from django.db import transaction
    from publications.models import FileObject, Appendenciesship
    import tempfile
    import shutil
    from django.core.files.base import ContentFile
    
    session_key = f'appendix_upload_{publication.id}'
    uploaded_files = request.session.get(session_key, [])
    
    if not uploaded_files:
        return []
    
    created_files = []
    
    with transaction.atomic():
        for file_data in uploaded_files:
            # Recreate the uploaded file from session data
            temp_file_path = file_data.get('temp_path')
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    with open(temp_file_path, 'rb') as temp_file:
                        file_content = ContentFile(temp_file.read(), name=file_data['filename'])
                        
                    # Create FileObject using our utility
                    file_obj = handle_appendix_file_upload(publication, file_content)
                    
                    if file_obj:
                        # Link to publication
                        Appendenciesship.objects.create(
                            publication=publication,
                            fileobject=file_obj
                        )
                        created_files.append(file_obj)
                        
                except Exception as e:
                    # Log error but continue processing other files
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error processing appendix file {file_data['filename']}: {e}")
                finally:
                    # Clean up temporary file
                    try:
                        os.unlink(temp_file_path)
                    except OSError:
                        pass
    
    # Clear session data after successful processing
    if session_key in request.session:
        del request.session[session_key]
    
    return created_files


def generate_next_report_number(year, exclude_ids=None):
    """
    Generate the next available report number for a given year.
    Format: YY-NN where YY is last two digits of year and NN is incremental number.
    Uses database locking to prevent race conditions.
    
    Args:
        year (int): The publication year (e.g., 2025)
        exclude_ids (list): Publication IDs to exclude from existing number check
        
    Returns:
        str: The next available report number (e.g., "25-01", "25-02")
    """
    from django.db import transaction
    from publications.models import Publication
    
    # Get last two digits of year
    year_suffix = str(year)[-2:]
    
    with transaction.atomic():
        # Find all existing report numbers for this year with row locking
        queryset = Publication.objects.filter(
            year=year,
            number__startswith=f"{year_suffix}-"
        ).select_for_update()
        
        # Exclude specific publication IDs if provided
        if exclude_ids:
            queryset = queryset.exclude(id__in=exclude_ids)
        
        existing_numbers = queryset.values_list('number', flat=True)
        
        # Extract the incremental part and find the highest
        used_increments = set()
        for number in existing_numbers:
            if number and '-' in number:
                try:
                    prefix, increment = number.split('-', 1)
                    if prefix == year_suffix and increment.isdigit():
                        used_increments.add(int(increment))
                except (ValueError, AttributeError):
                    # Skip malformed numbers
                    continue
        
        # Find the next available increment with double-check
        next_increment = 1
        while next_increment <= 999:  # Safety limit
            candidate_number = f"{year_suffix}-{next_increment:02d}"
            
            # Double-check this specific number doesn't exist
            exists = Publication.objects.filter(
                year=year,
                number=candidate_number
            ).select_for_update().exists()
            
            if not exists:
                return candidate_number
            
            next_increment += 1
        
        # If we get here, we've exhausted all possibilities
        raise Exception(f"No available report numbers for year {year} (all numbers up to {year_suffix}-999 are taken)")


def generate_batch_report_numbers(publications_by_year):
    """
    Generate report numbers for multiple publications, ensuring no conflicts.
    Uses database transactions and unique constraints to prevent race conditions.
    
    Args:
        publications_by_year (dict): Dict with year as key and list of publications as value
        
    Returns:
        dict: Dict mapping publication ID to new report number
    """
    from django.db import transaction
    from publications.models import Publication
    
    result = {}
    
    for year, publications in publications_by_year.items():
        if not publications:
            continue
            
        # Sort publications by ID for consistent ordering
        publications = sorted(publications, key=lambda p: p.id or 0)
        
        # Use database-level transaction with row locking
        with transaction.atomic():
            # Get IDs of publications we're updating to exclude from existing check
            updating_ids = [pub.id for pub in publications if pub.id]
            
            year_suffix = str(year)[-2:]
            
            # Use SELECT FOR UPDATE to lock the rows and prevent concurrent modifications
            # This ensures no other process can insert conflicting numbers during our operation
            existing_queryset = Publication.objects.filter(
                year=year,
                number__startswith=f"{year_suffix}-"
            ).select_for_update()
            
            if updating_ids:
                existing_queryset = existing_queryset.exclude(id__in=updating_ids)
            
            # Get fresh data with row locks held
            existing_numbers = set(existing_queryset.values_list('number', flat=True))
            
            # Track numbers we've assigned in this batch to avoid duplicates
            assigned_in_batch = set()
            
            # Assign numbers to publications
            for publication in publications:
                next_increment = 1
                
                # Find next available increment that doesn't exist in DB or batch
                while True:
                    candidate_number = f"{year_suffix}-{next_increment:02d}"
                    
                    # Double-check availability by querying database with lock
                    # This prevents race conditions from other processes
                    existing_check = Publication.objects.filter(
                        year=year,
                        number=candidate_number
                    ).select_for_update().exists()
                    
                    if not existing_check and candidate_number not in assigned_in_batch:
                        # This number is available
                        result[publication.id] = candidate_number
                        assigned_in_batch.add(candidate_number)
                        break
                    
                    next_increment += 1
                    
                    # Safety check to prevent infinite loop
                    if next_increment > 999:
                        raise Exception(f"No available report numbers for year {year} (tried up to {year_suffix}-999)")
    
    return result


def validate_report_number_format(number):
    """
    Validate that a report number follows the expected YY-NN format.
    
    Args:
        number (str): The report number to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    import re
    
    if not number:
        return False, "Report number is required"
    
    # Check format: exactly YY-NN where YY and NN are digits
    pattern = r'^\d{2}-\d{2}$'
    if not re.match(pattern, number):
        return False, "Report number must be in format YY-NN (e.g., 25-01)"
    
    return True, None


def rename_publication_files(publication, old_number, new_number):
    """
    Rename all files and directories associated with a publication when its number changes.
    
    Args:
        publication: Publication instance
        old_number: Previous report number
        new_number: New report number
        
    Returns:
        dict: Summary of renamed files and any errors
    """
    import os
    import shutil
    from django.conf import settings
    from django.core.files.storage import default_storage
    
    results = {
        'success': True,
        'renamed_files': [],
        'errors': [],
        'directories_renamed': []
    }
    
    if not publication.year:
        results['success'] = False
        results['errors'].append("Cannot rename files - publication has no year")
        return results
    
    year = publication.year
    media_root = settings.MEDIA_ROOT
    
    # Define old and new paths
    old_report_dir = os.path.join(media_root, 'reports', str(year), old_number)
    new_report_dir = os.path.join(media_root, 'reports', str(year), new_number)
    
    old_thumb_file = os.path.join(media_root, 'reports', str(year), 'thumbs', f'{old_number}_thumb.jpg')
    new_thumb_file = os.path.join(media_root, 'reports', str(year), 'thumbs', f'{new_number}_thumb.jpg')
    
    try:
        # 1. Rename main report directory if it exists
        if os.path.exists(old_report_dir):
            if os.path.exists(new_report_dir):
                results['errors'].append(f"Target directory already exists: {new_report_dir}")
            else:
                shutil.move(old_report_dir, new_report_dir)
                results['directories_renamed'].append(f"{old_report_dir} → {new_report_dir}")
        
        # 2. Rename thumbnail file if it exists
        if os.path.exists(old_thumb_file):
            if os.path.exists(new_thumb_file):
                results['errors'].append(f"Target thumbnail already exists: {new_thumb_file}")
            else:
                shutil.move(old_thumb_file, new_thumb_file)
                results['renamed_files'].append(f"{old_thumb_file} → {new_thumb_file}")
        
        # 3. Update database file paths
        if publication.file and publication.file.file:
            old_file_path = publication.file.file.path
            if old_number in old_file_path:
                # Update the file path in the database
                new_file_path = old_file_path.replace(f'/{old_number}/', f'/{new_number}/')
                publication.file.file.name = new_file_path.replace(media_root, '').lstrip('/')
                publication.file.save()
                results['renamed_files'].append(f"Updated database path: {old_file_path} → {new_file_path}")
        
        # 4. Update appendix file paths
        for appendix in publication.appendices.all():
            if appendix.file and appendix.file.file:
                old_appendix_path = appendix.file.file.path
                if old_number in old_appendix_path:
                    new_appendix_path = old_appendix_path.replace(f'/{old_number}/', f'/{new_number}/')
                    appendix.file.file.name = new_appendix_path.replace(media_root, '').lstrip('/')
                    appendix.file.save()
                    results['renamed_files'].append(f"Updated appendix path: {old_appendix_path} → {new_appendix_path}")
    
    except Exception as e:
        results['success'] = False
        results['errors'].append(f"Error during file renaming: {str(e)}")
    
    return results
