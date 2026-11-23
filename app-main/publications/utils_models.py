"""
Model-dependent utility functions for publications app.
These functions depend on Django models or database/database access.
"""


import os
import posixpath
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
from PIL import Image, ImageOps

from publications.media_access import image_thumbnail_name
from publications.models import (
    Publication, FileObject, Appendenciesship, Keyword, ImageObject, ImageObjectship,
)

logger = logging.getLogger(__name__)


def get_or_create_keywords(items):
    """Keyword instances for the cleaned value of ``KeywordTagField``: Keyword instances are
    kept, names (str) become the existing keyword with that name (case-insensitive) or a new
    one. Call it inside the transaction that saves the report, so a failed save creates none."""
    keywords = []
    for item in items:
        if isinstance(item, Keyword):
            keywords.append(item)
            continue
        name = str(item).strip()
        if not name:
            continue
        keyword = Keyword.objects.filter(keyword__iexact=name).first()
        if keyword is None:
            keyword = Keyword.objects.create(keyword=name)
        keywords.append(keyword)
    return keywords


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


def handle_appendix_file_upload(publication, uploaded_file, user):
    """Save ``uploaded_file`` as an appendix file of ``publication`` and return its
    FileObject (created_by/modified_by = ``user``), or None without a file."""
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
        description=f"Appendix file for report {publication.number} ({publication.year})",
        created_by=user,
        modified_by=user,
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
                    file_obj = handle_appendix_file_upload(publication, file_content, request.user)
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


# --- Files and images of a feature (plan "features" T8, roadmap FA-R64, design note 5) -----
# New uploads go to MEDIA_ROOT/reports/<year>/<number>/features/<feature id>/ (images in img/
# below it), with the report the upload starts from. The names come from FileObject /
# ImageObject.upload_to (models.get_file_path / get_image_path); the storage makes a name
# unique (a suffix), so an existing file is never overwritten. Thumbnails of images are made
# with Pillow right after the upload, as <img dir>/thumbs/<file name>_thumb.jpg
# (media_access.image_thumbnail_name; served with the image's visibility).

FEATURE_THUMBNAIL_SIZE = (400, 400)   # box; report thumbnails are 400 px high

# A report number usable as one folder name (e.g. '25-07').
_SAFE_FOLDER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')

FEATURE_FILE = 'file'
FEATURE_IMAGE = 'image'


class FeatureUploadError(Exception):
    """The upload cannot be stored (no usable report folder); the message is for the user."""


def feature_media_dir(feature, report):
    """``reports/<year>/<number>/features/<feature id>`` for uploads to ``feature`` started
    from ``report``. FeatureUploadError without a report, or when the report has no year or
    no number usable as a folder name."""
    if report is None:
        raise FeatureUploadError(
            'Files and images can only be added to a feature that belongs to a report.')
    year = str(report.year or '')
    number = str(report.number or '')
    if not _usable_report_folder(year, number):
        raise FeatureUploadError(
            f'Report {report.number or report.pk} has no year or report number usable as a '
            f'folder name; files cannot be stored for it.')
    return _feature_dir_name(year, number, feature.pk)


def _usable_report_folder(year, number):
    return year.isdigit() and bool(_SAFE_FOLDER.match(number)) and '..' not in number


def _feature_dir_name(year, number, feature_pk):
    return posixpath.join('reports', year, number, 'features', str(feature_pk))


def feature_media_root(path, feature_pk):
    """Absolute path of the folder ``reports/<year>/<number>/features/<feature_pk>`` under
    MEDIA_ROOT (feature_media_dir) that holds ``path`` (an absolute file path), or None if
    ``path`` is not inside such a folder of this feature (other storage places, other
    features, outside MEDIA_ROOT). The folder may belong to any report: files stay where
    they were uploaded, also when the feature later leaves that report."""
    media_root = os.path.realpath(settings.MEDIA_ROOT)
    directory = os.path.realpath(os.path.dirname(path))
    try:
        if os.path.commonpath([media_root, directory]) != media_root:
            return None
    except ValueError:   # different drives
        return None
    parts = os.path.relpath(directory, media_root).split(os.sep)
    if len(parts) < 5 or parts[0] != 'reports' or parts[3] != 'features':
        return None
    year, number = parts[1], parts[2]
    if not _usable_report_folder(year, number) or parts[4] != str(feature_pk):
        return None
    return os.path.join(media_root, *_feature_dir_name(year, number, feature_pk).split('/'))


def remove_empty_feature_dirs(path, feature_pk):
    """After a file of feature ``feature_pk`` was removed: remove the folders that are now
    empty, from the folder of ``path`` up to and including the feature's folder
    (feature_media_root), never above it (plan "features" T15). os.rmdir only removes empty
    folders, so a folder that still holds anything stops the walk. Nothing happens for a
    path outside a folder of this feature."""
    feature_dir = feature_media_root(path, feature_pk)
    if feature_dir is None:
        return
    current = os.path.realpath(os.path.dirname(path))
    while os.path.commonpath([feature_dir, current]) == feature_dir:
        try:
            os.rmdir(current)
        except FileNotFoundError:
            pass                       # already gone: go on with the parent
        except OSError:
            return                     # not empty (or not removable): keep it and above
        if current == feature_dir:
            return
        current = os.path.dirname(current)


def remove_empty_dirs_below(feature_dir):
    """Remove the empty folders inside the absolute folder ``feature_dir`` (bottom up) and
    the folder itself if it is then empty. Only for a feature folder (feature_media_dir) of
    a deleted feature. Folders that hold anything are kept (os.rmdir)."""
    if not os.path.isdir(feature_dir):
        return
    for directory, _subdirs, _files in os.walk(feature_dir, topdown=False):
        try:
            os.rmdir(directory)
        except OSError:
            pass


def _save_feature_record(feature, directory, uploaded_file, user, kind, text, saved_paths):
    if kind == FEATURE_IMAGE:
        record = ImageObject(caption=text, created_by=user, modified_by=user)
        record.upload_to = posixpath.join(directory, 'img')   # models.get_image_path
        field = record.image
    else:
        record = FileObject(description=text, created_by=user, modified_by=user)
        record.upload_to = directory                          # models.get_file_path
        field = record.file
    field.save(os.path.basename(uploaded_file.name), uploaded_file, save=False)
    saved_paths.append(field.path)
    record.save()
    if kind == FEATURE_IMAGE:
        ImageObjectship.objects.create(imageobject=record, feature=feature)
    else:
        feature.files.add(record)
    return record


def handle_feature_uploads(feature, report, uploaded_files, user, kind, text=''):
    """Store ``uploaded_files`` (validated by FeatureFileUploadForm / FeatureImageUploadForm)
    as files (``kind`` FEATURE_FILE) or images (FEATURE_IMAGE) of ``feature`` in the folder of
    ``report`` (feature_media_dir) and return the new records. ``text`` is the description
    (files) or caption (images). All records are created in one transaction; if it fails,
    the files written so far are removed and the error is raised. Thumbnails of images are
    made afterwards; a failed thumbnail is only logged."""
    directory = feature_media_dir(feature, report)
    saved_paths = []
    try:
        with transaction.atomic():
            records = [
                _save_feature_record(feature, directory, uploaded_file, user, kind, text,
                                     saved_paths)
                for uploaded_file in uploaded_files]
    except Exception:
        for path in saved_paths:
            try:
                os.remove(path)
            except OSError:
                logger.warning("Could not remove %s after a failed feature upload", path)
        raise
    if kind == FEATURE_IMAGE:
        for record in records:
            make_image_thumbnail(record)
    return records


def image_thumbnail_path(image_object):
    """Absolute path of the thumbnail of ``image_object`` (whether it exists or not), or None
    without an image name."""
    if not image_object.image or not image_object.image.name:
        return None
    name = image_thumbnail_name(image_object.image.name)
    return os.path.join(settings.MEDIA_ROOT, *name.split('/'))


def image_thumbnail_url(image_object):
    """MEDIA_URL of the thumbnail of ``image_object`` if the thumbnail exists, else None."""
    path = image_thumbnail_path(image_object)
    if path is None or not os.path.isfile(path):
        return None
    return settings.MEDIA_URL + image_thumbnail_name(image_object.image.name)


def make_image_thumbnail(image_object):
    """Write the JPEG thumbnail (at most FEATURE_THUMBNAIL_SIZE, EXIF orientation applied) of
    ``image_object`` and return its path, or None (logged) if the image cannot be read."""
    target = image_thumbnail_path(image_object)
    if target is None:
        return None
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with Image.open(image_object.image.path) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail(FEATURE_THUMBNAIL_SIZE)
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGBA')
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel('A'))
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            image.save(target, 'JPEG', quality=85, optimize=True)
        return target
    except Exception:
        logger.exception("Could not make the thumbnail of ImageObject %s", image_object.pk)
        try:
            if os.path.exists(target):
                os.remove(target)
        except OSError:
            pass
        return None
