"""
Model-dependent utility functions for publications app.
These functions depend on Django models or database/database access.
"""


import os
import re
import shutil
import tempfile
import time
import logging

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Case, When, Value, IntegerField

from publications.models import Publication, FileObject, Appendenciesship


def create_ordered_queryset(model_class, pk_list):
    # ...existing code from utils.py...
    if not pk_list:
        return model_class.objects.none()
    preserved_order = Case(*[
        When(pk=pk, then=Value(i)) 
        for i, pk in enumerate(pk_list)
    ], output_field=IntegerField())
    queryset = model_class.objects.filter(pk__in=pk_list).annotate(
        preserved_order=preserved_order
    ).order_by('preserved_order')
    return queryset


def handle_appendix_file_upload(publication, uploaded_file):
    # ...existing code from utils.py...
    if not uploaded_file:
        return None
    original_filename = uploaded_file.name
    appendix_dir = f"reports/{publication.year}/{publication.number}"
    file_path = os.path.join(appendix_dir, original_filename)
    full_dir_path = os.path.join(settings.MEDIA_ROOT, appendix_dir)
    os.makedirs(full_dir_path, exist_ok=True)
    saved_path = default_storage.save(file_path, uploaded_file)
    file_obj = FileObject.objects.create(
        file=saved_path,
        description=f"Appendix file for report {publication.number} ({publication.year})"
    )
    return file_obj


def handle_session_appendix_uploads(request, publication):
    # ...existing code from utils.py...
    session_key = f'appendix_upload_{publication.id}'
    uploaded_files = request.session.get(session_key, [])
    if not uploaded_files:
        return []
    created_files = []
    with transaction.atomic():
        for file_data in uploaded_files:
            temp_file_path = file_data.get('temp_path')
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    with open(temp_file_path, 'rb') as temp_file:
                        file_content = ContentFile(temp_file.read(), name=file_data['filename'])
                    file_obj = handle_appendix_file_upload(publication, file_content)
                    if file_obj:
                        Appendenciesship.objects.create(
                            publication=publication,
                            fileobject=file_obj
                        )
                        created_files.append(file_obj)
                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error processing appendix file {file_data['filename']}: {e}")
                finally:
                    try:
                        os.unlink(temp_file_path)
                    except OSError:
                        pass
    if session_key in request.session:
        del request.session[session_key]
    return created_files


def generate_next_report_number(year, exclude_ids=None):
    """
    Generate the next available report number for a given year.
    Report numbers are in the format YY-NN, where YY is the last two digits of the year,
    and NN is a two-digit increment starting from 01. The function ensures uniqueness
    by checking existing numbers in the database and skipping any numbers already used.

    Args:
        year (int): The year for which to generate the report number.
        exclude_ids (list, optional): List of publication IDs to exclude from the search (useful for batch updates).

    Returns:
        str: The next available report number in the format YY-NN.

    Raises:
        Exception: If all numbers up to YY-999 are taken for the given year.
    """
    year_suffix = str(year)[-2:]  # Get last two digits of the year
    with transaction.atomic():
        # Query for publications in the given year with numbers starting with the year suffix
        queryset = Publication.objects.filter(
            year=year,
            number__startswith=f"{year_suffix}-"
        ).select_for_update()
        if exclude_ids:
            queryset = queryset.exclude(id__in=exclude_ids)
        existing_numbers = queryset.values_list('number', flat=True)
        used_increments = set()
        # Parse existing numbers and collect used increments
        for number in existing_numbers:
            if number and '-' in number:
                try:
                    prefix, increment = number.split('-', 1)
                    if prefix == year_suffix and increment.isdigit():
                        used_increments.add(int(increment))
                except (ValueError, AttributeError):
                    continue  # Skip malformed numbers
        next_increment = 1
        # Find the next available increment
        while next_increment <= 999:
            candidate_number = f"{year_suffix}-{next_increment:02d}"
            exists = Publication.objects.filter(
                year=year,
                number=candidate_number
            ).select_for_update().exists()
            if not exists:
                return candidate_number
            next_increment += 1
        # If all numbers are taken, raise an exception
        raise Exception(f"No available report numbers for year {year} (all numbers up to {year_suffix}-999 are taken)")


def generate_batch_report_numbers(publications_by_year):
    """
    Generate unique report numbers for a batch of publications grouped by year.
    Each publication is assigned a number in the format YY-NN, where YY is the last two digits of the year
    and NN is a two-digit increment starting from 01. The function ensures uniqueness by checking existing
    numbers in the database and avoiding duplicates within the batch.

    Args:
        publications_by_year (dict): Dictionary mapping year (int) to a list of Publication objects for that year.

    Returns:
        dict: Mapping of publication IDs to their assigned report numbers (str).

    Raises:
        Exception: If all numbers up to YY-999 are taken for a given year.
    """
    result = {}
    for year, publications in publications_by_year.items():
        if not publications:
            continue  # Skip years with no publications
        # Sort publications by ID for deterministic assignment
        publications = sorted(publications, key=lambda p: p.id or 0)
        with transaction.atomic():
            # IDs of publications being updated (to avoid excluding their current numbers)
            updating_ids = [pub.id for pub in publications if pub.id]
            year_suffix = str(year)[-2:]  # Last two digits of the year
            # Query for existing report numbers for the year, excluding those being updated
            existing_queryset = Publication.objects.filter(
                year=year,
                number__startswith=f"{year_suffix}-"
            ).select_for_update()
            if updating_ids:
                existing_queryset = existing_queryset.exclude(id__in=updating_ids)
            existing_numbers = set(existing_queryset.values_list('number', flat=True))
            assigned_in_batch = set()  # Track numbers assigned in this batch to avoid duplicates
            for publication in publications:
                next_increment = 1
                while True:
                    # Format candidate number as YY-NN
                    candidate_number = f"{year_suffix}-{next_increment:02d}"
                    # Check if candidate number exists in DB or already assigned in batch
                    existing_check = Publication.objects.filter(
                        year=year,
                        number=candidate_number
                    ).select_for_update().exists()
                    if not existing_check and candidate_number not in assigned_in_batch:
                        # Assign candidate number to publication
                        result[publication.id] = candidate_number
                        assigned_in_batch.add(candidate_number)
                        break
                    next_increment += 1
                    if next_increment > 999:
                        # All numbers for this year are taken
                        raise Exception(f"No available report numbers for year {year} (tried up to {year_suffix}-999)")
    return result


def validate_report_number_format(number):
    # ...existing code from utils.py...
    if not number:
        return False, "Report number is required"
    pattern = r'^\d{2}-\d{2}$'
    if not re.match(pattern, number):
        return False, "Report number must be in format YY-NN (e.g., 25-01)"
    return True, None


def rename_publication_files(publication, old_number, new_number):
    # ...existing code from utils.py...
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
    old_report_dir = os.path.join(media_root, 'reports', str(year), old_number)
    new_report_dir = os.path.join(media_root, 'reports', str(year), new_number)
    old_thumb_file = os.path.join(media_root, 'reports', str(year), 'thumbs', f'{old_number}_thumb.jpg')
    new_thumb_file = os.path.join(media_root, 'reports', str(year), 'thumbs', f'{new_number}_thumb.jpg')
    try:
        if os.path.exists(old_report_dir):
            if os.path.exists(new_report_dir):
                results['errors'].append(f"Target directory already exists: {new_report_dir}")
            else:
                shutil.move(old_report_dir, new_report_dir)
                results['directories_renamed'].append(f"{old_report_dir} → {new_report_dir}")
        if os.path.exists(old_thumb_file):
            if os.path.exists(new_thumb_file):
                results['errors'].append(f"Target thumbnail already exists: {new_thumb_file}")
            else:
                shutil.move(old_thumb_file, new_thumb_file)
                results['renamed_files'].append(f"{old_thumb_file} → {new_thumb_file}")
        if publication.file and publication.file.file:
            old_file_path = publication.file.file.path
            if old_number in old_file_path:
                new_file_path = old_file_path.replace(f'/{old_number}/', f'/{new_number}/')
                publication.file.file.name = new_file_path.replace(media_root, '').lstrip('/')
                publication.file.save()
                results['renamed_files'].append(f"Updated database path: {old_file_path} → {new_file_path}")
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


def handle_publication_file_upload(uploaded_file, user, publication=None):
    print(f"🔍 DEBUG: handle_publication_file_upload - Starting file processing")
    print(f"🔍 DEBUG: Uploaded file: {uploaded_file.name}, size: {uploaded_file.size}")
    
    file_obj = FileObject()
    file_obj.created_by = user
    file_obj.modified_by = user

    if publication is None:
        timestamp = str(int(time.time()))
        upload_to = os.path.join('temp', timestamp)
        print(f"🔍 DEBUG: Using temporary storage path: {upload_to}")
        base_name, ext = os.path.splitext(uploaded_file.name)
        filename = f"temp_{int(time.time())}_{base_name}{ext}"
    else:
        pub_number = publication.number if publication.number else f"pub_{file_obj.id}"
        year = publication.year if hasattr(publication, 'year') and publication.year else 'unknown_year'
        year_str = str(year)
        pub_number_str = str(pub_number)
        upload_to = os.path.join('reports', year_str)
        print(f"🔍 DEBUG: Using final storage path: {upload_to}")
        base_name, ext = os.path.splitext(uploaded_file.name)
        filename = f"{pub_number}{ext}"

    full_upload_path = os.path.join(settings.MEDIA_ROOT, upload_to)
    os.makedirs(full_upload_path, exist_ok=True)
    print(f"🔍 DEBUG: File will be saved to: {upload_to}")

    file_path = os.path.join(upload_to, filename)

    counter = 1
    original_file_path = file_path
    while os.path.exists(os.path.join(settings.MEDIA_ROOT, file_path)):
        base_path, ext = os.path.splitext(original_file_path)
        file_path = f"{base_path}_{counter}{ext}"
        counter += 1

    file_obj.file.name = file_path
    full_file_path = os.path.join(settings.MEDIA_ROOT, file_path)
    with open(full_file_path, 'wb') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    
    file_obj.save()
    print(f"🔍 DEBUG: File saved successfully: {file_obj.file.name}")
    return file_obj
