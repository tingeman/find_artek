"""Who may download which file under MEDIA_ROOT (roadmap FA-R30, FA-R75; plan PLAN_confidential T5).

Every request for a file under ``MEDIA_URL`` goes through ``publications.views_media.serve_media``,
which uses the functions here:

1. ``resolve_media_path(path)`` normalises the requested path and refuses anything that could
   leave ``MEDIA_ROOT`` (``..``, absolute paths, backslashes, NUL, symlinks pointing outside).
2. ``media_owners(relpath)`` finds what the file belongs to:

   - ``('publication', pub)``: the report PDF (``Publication.file``) or an appendix
     (``Publication.appendices``) is a ``FileObject`` whose ``file`` name equals the path;
   - ``('feature', feature)``: a ``FileObject`` in ``Feature.files`` or an ``ImageObject`` in
     ``Feature.images``;
   - ``('thumbnail', pub)``: ``<dir>/thumbs/<stem>_thumb.jpg`` (no database row). Its report is
     the one whose PDF is ``<dir>/<stem>.<ext>`` (the template tag ``thumb_file``), or, for
     ``<dir>`` = ``reports/<year>``, the one with ``number`` = ``<stem>`` and that ``year``
     (the ``generate_thumbnails`` command);
   - ``('temp', fileobject)``: a ``FileObject`` under ``temp/`` (an upload not yet moved into
     a report).

   A file can have several owners (e.g. one FileObject used as appendix of two reports, or as
   a report file and a feature file). It may be downloaded if **any** owner allows it.
3. ``can_access_media(user, relpath)`` applies the visibility rule (``publications.visibility``):
   publication and thumbnail -> ``can_view_publication``; feature -> ``can_view_feature``;
   temp -> its uploader (``created_by``), ``artek_editor`` and superusers. A file with **no
   owner** (``.old`` PDFs, orphans, a FileObject linked to nothing) is for ``artek_editor`` and
   superusers only: **default deny**.

``MediaIndex`` answers the same questions for a whole tree with a fixed number of queries (the
command ``check_media_access``); ``publications.test_media_access`` checks that both agree.

File names are matched exactly as stored (``FileObject.file``, ``ImageObject.image``): a stored
name in another spelling (backslashes, a leading ``/``) doesn't own the file, which is then
editors-only. ``check_media_access --list-unowned`` shows such files.
"""
import os
import posixpath
from collections import defaultdict

from django.conf import settings
from django.db.models import Prefetch, Q

from publications.models import (
    Appendenciesship, Feature, FileObject, ImageObject, ImageObjectship, Publication,
)
from publications.visibility import can_view_feature, can_view_publication, sees_all

PUBLICATION = 'publication'
FEATURE = 'feature'
THUMBNAIL = 'thumbnail'
TEMP = 'temp'

TEMP_PREFIX = 'temp/'
THUMB_DIR = 'thumbs'
THUMB_SUFFIX = '_thumb.jpg'

# Access levels (check_media_access): anonymous users may download the file; only some
# logged-in users may; only artek_editor and superusers may.
PUBLIC = 'public'
RESTRICTED = 'restricted'
EDITORS_ONLY = 'editors_only'


def resolve_media_path(path):
    """The normalised path of ``path`` relative to MEDIA_ROOT (forward slashes), or None if it
    is empty, absolute, contains a backslash, NUL or a ``..`` segment, or its real path (after
    symlinks) isn't inside MEDIA_ROOT. Doesn't check that the file exists."""
    if not path or not isinstance(path, str):
        return None
    if '\x00' in path or '\\' in path:
        return None
    if path.startswith('/') or os.path.isabs(path) or os.path.splitdrive(path)[0]:
        return None
    if any(segment == '..' for segment in path.split('/')):
        return None
    relpath = posixpath.normpath(path)
    if relpath in ('', '.') or relpath.startswith('/') or relpath.startswith('../'):
        return None
    root = os.path.realpath(settings.MEDIA_ROOT)
    full = os.path.realpath(os.path.join(root, *relpath.split('/')))
    try:
        if os.path.commonpath([root, full]) != root:
            return None
    except ValueError:  # different drives (Windows)
        return None
    if full == root:
        return None
    return relpath


def media_file_path(relpath):
    """Absolute path of a path returned by ``resolve_media_path``."""
    return os.path.join(settings.MEDIA_ROOT, *relpath.split('/'))


def thumbnail_key(relpath):
    """``(dir, stem)`` for a thumbnail path ``<dir>/thumbs/<stem>_thumb.jpg``, else None."""
    head, name = posixpath.split(relpath)
    parent, thumbs = posixpath.split(head)
    if thumbs != THUMB_DIR or not name.endswith(THUMB_SUFFIX):
        return None
    stem = name[:-len(THUMB_SUFFIX)]
    return (parent, stem) if stem else None


def _pdf_thumbnail_key(file_name):
    """The thumbnail key of a report PDF's stored name (template tag ``thumb_file``)."""
    if not file_name:
        return None
    head, name = posixpath.split(file_name)
    stem = posixpath.splitext(name)[0]
    return (head, stem) if stem else None


def _number_thumbnail_key(publication):
    """The thumbnail key the ``generate_thumbnails`` command uses for ``publication``."""
    if not (publication.number and publication.year):
        return None
    return (f'reports/{publication.year}', publication.number)


def _is_temp(relpath):
    return relpath.startswith(TEMP_PREFIX)


def _thumbnail_publications(key):
    directory, stem = key
    query = Q(file__file__startswith=f'{directory}/{stem}.' if directory else f'{stem}.')
    if directory.startswith('reports/'):
        year = directory[len('reports/'):]
        if year.isdigit():
            query |= Q(number=stem, year=int(year))
    found = []
    for pub in Publication.objects.filter(query).select_related('file').distinct():
        if key in (_pdf_thumbnail_key(pub.file.file.name if pub.file else ''),
                   _number_thumbnail_key(pub)):
            found.append(pub)
    return found


def media_owners(relpath):
    """List of ``(kind, object)`` owning the file at ``relpath`` (see the module docstring);
    empty if nothing owns it."""
    owners = []
    for fileobject in FileObject.objects.filter(file=relpath):
        pubs = Publication.objects.filter(
            Q(file=fileobject) | Q(appendices=fileobject)).distinct()
        owners.extend((PUBLICATION, pub) for pub in pubs)
        owners.extend((FEATURE, feature) for feature in Feature.objects.filter(files=fileobject))
        if _is_temp(relpath):
            owners.append((TEMP, fileobject))
    features = Feature.objects.filter(images__image=relpath).distinct()
    owners.extend((FEATURE, feature) for feature in features)
    key = thumbnail_key(relpath)
    if key:
        owners.extend((THUMBNAIL, pub) for pub in _thumbnail_publications(key))
    return owners


def _owner_allows(user, kind, obj):
    if kind in (PUBLICATION, THUMBNAIL):
        return can_view_publication(user, obj)
    if kind == FEATURE:
        return can_view_feature(user, obj)
    if kind == TEMP:
        return sees_all(user) or (
            obj.created_by_id is not None
            and bool(getattr(user, 'is_authenticated', False))
            and obj.created_by_id == user.pk)
    return False


def can_access_media(user, relpath):
    """``(allowed, public)`` for the file at ``relpath`` (from ``resolve_media_path``):
    ``allowed`` if ``user`` may download it, ``public`` if anonymous users may (the view sets
    ``Cache-Control`` from it). Doesn't check that the file exists."""
    owners = media_owners(relpath)
    public = any(_owner_allows(None, kind, obj) for kind, obj in owners)
    if public:
        return True, True
    if sees_all(user):
        return True, False
    return any(_owner_allows(user, kind, obj) for kind, obj in owners), False


# --- Whole tree (check_media_access) -------------------------------------------------------

# Classes in the order of precedence when a file has owners of several kinds.
REPORT_PDF = 'report_pdf'
APPENDIX = 'appendix'
THUMBNAIL_CLASS = 'thumbnail'
FEATURE_FILE = 'feature_file'
FEATURE_IMAGE = 'feature_image'
TEMP_CLASS = 'temp'
UNOWNED = 'unowned'
CLASSES = (REPORT_PDF, APPENDIX, THUMBNAIL_CLASS, FEATURE_FILE, FEATURE_IMAGE, TEMP_CLASS, UNOWNED)
LEVELS = (PUBLIC, RESTRICTED, EDITORS_ONLY)


class MediaIndex:
    """All owners of all media files, loaded with a fixed number of queries.

    ``classify(relpath)`` -> ``(class, level)``: the class of the file (``CLASSES``; the first
    that applies) and who may download it: ``PUBLIC`` (anonymous users), ``RESTRICTED`` (some
    logged-in users, not anonymous ones) or ``EDITORS_ONLY`` (no owner, or a temp upload with no
    uploader). The anonymous answer comes from the same rule as the view
    (``can_view_publication`` / ``can_view_feature`` with user None). Like the view, a file
    with several owners gets the widest level of any of them.
    """

    def __init__(self):
        pubs = {pub.pk: pub for pub in Publication.objects.only(
            'pk', 'number', 'year', 'verified', 'confidential', 'file')}
        file_names = {}
        temp_levels = {}
        for pk, name, created_by in FileObject.objects.values_list('pk', 'file', 'created_by_id'):
            file_names[pk] = name
            temp_levels[pk] = RESTRICTED if created_by is not None else EDITORS_ONLY

        # stored name -> class -> list of levels (one per owner)
        self._owners = defaultdict(lambda: defaultdict(list))

        def add(name, cls, level):
            if name:
                self._owners[name][cls].append(level)

        pub_level = {pk: PUBLIC if can_view_publication(None, pub) else RESTRICTED
                     for pk, pub in pubs.items()}
        thumbs = defaultdict(set)
        for pk, pub in pubs.items():
            if pub.file_id:
                name = file_names.get(pub.file_id)
                add(name, REPORT_PDF, pub_level[pk])
                key = _pdf_thumbnail_key(name)
                if key:
                    thumbs[key].add(pk)
            key = _number_thumbnail_key(pub)
            if key:
                thumbs[key].add(pk)
        self._thumbs = {key: [pub_level[pk] for pk in pks] for key, pks in thumbs.items()}

        for fo_id, pub_id in Appendenciesship.objects.values_list('fileobject_id', 'publication_id'):
            add(file_names.get(fo_id), APPENDIX, pub_level[pub_id])

        features = Feature.objects.only('pk').prefetch_related(
            Prefetch('publications',
                     queryset=Publication.objects.only('pk', 'verified', 'confidential')))
        feature_level = {feature.pk: PUBLIC if can_view_feature(None, feature) else RESTRICTED
                         for feature in features}
        for fo_id, feature_id in Feature.files.through.objects.values_list(
                'fileobject_id', 'feature_id'):
            add(file_names.get(fo_id), FEATURE_FILE, feature_level[feature_id])
        image_names = dict(ImageObject.objects.values_list('pk', 'image'))
        for image_id, feature_id in ImageObjectship.objects.values_list(
                'imageobject_id', 'feature_id'):
            add(image_names.get(image_id), FEATURE_IMAGE, feature_level[feature_id])

        for pk, name in file_names.items():
            if name and _is_temp(name):
                add(name, TEMP_CLASS, temp_levels[pk])

    def classify(self, relpath):
        """``(class, level)`` of the file at ``relpath`` (relative to MEDIA_ROOT)."""
        owners = dict(self._owners.get(relpath, {}))
        key = thumbnail_key(relpath)
        if key in self._thumbs:
            owners[THUMBNAIL_CLASS] = self._thumbs[key]
        cls = next((c for c in CLASSES if c in owners), UNOWNED)
        levels = {level for values in owners.values() for level in values}
        level = next((lv for lv in LEVELS if lv in levels), EDITORS_ONLY)
        return cls, level
