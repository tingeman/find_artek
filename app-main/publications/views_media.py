"""The checked view for every file under MEDIA_URL (roadmap FA-R30, FA-R75; plan PLAN_confidential T5).

Who may download what is decided in ``publications.media_access``. Denied, invalid and missing
files all answer 404, for every user and without a login redirect: these are file URLs, often
loaded as images, and a 404 doesn't confirm that a hidden file exists.

Allowed files:

- ``settings.MEDIA_ACCEL_REDIRECT_PREFIX`` set (production, ``/find/_protected_media/``): an
  empty response with ``X-Accel-Redirect``; nginx serves the file from its internal location
  (Range requests, slow clients). gunicorn (2 workers x 2 threads, 120 s timeout) must never
  stream a file itself.
- empty (development settings): Django streams the file (``FileResponse``).

``Cache-Control`` is ``public, max-age=3600`` for files anonymous users may download and
``private, no-store`` for all others.

Headers against stored XSS (plan "features" T8a): media is served from the app's own origin, so
a browser must never render an uploaded file as a page. Every file response has
``X-Content-Type-Options: nosniff``. Only the types in ``INLINE_CONTENT_TYPES`` (PDF, plain
text, raster images) are sent inline with their type; every other file (feature files of any
type, appendices such as .docx/.xlsx/.zip, ``.xml``, ``.old`` copies, files without extension)
is sent as ``application/octet-stream`` with ``Content-Disposition: attachment`` (RFC 6266,
``filename*`` for non-ASCII names). The rule goes by the last extension of the stored name and
applies to all media, not only feature files. Who may download what is unchanged.
"""
import os
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.utils.http import content_disposition_header
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe

from publications.media_access import can_access_media, media_file_path, resolve_media_path

CACHE_PUBLIC = 'public, max-age=3600'
CACHE_PRIVATE = 'private, no-store'


DOWNLOAD_CONTENT_TYPE = 'application/octet-stream'

# Extension (lower case, last one only) -> type of the files a browser may show inline. Kept
# small on purpose: none of these can run script in our origin. TIFF is left out (most
# browsers cannot show it; it is downloaded).
INLINE_CONTENT_TYPES = {
    '.pdf': 'application/pdf',
    '.txt': 'text/plain',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
}


def media_headers(relpath):
    """``(content_type, content_disposition)`` for the media file ``relpath``;
    ``content_disposition`` is None for inline files."""
    ext = os.path.splitext(relpath)[1].lower()
    if ext in INLINE_CONTENT_TYPES:
        return INLINE_CONTENT_TYPES[ext], None
    return DOWNLOAD_CONTENT_TYPE, content_disposition_header(True, os.path.basename(relpath))


# csrf_exempt: the view only answers GET and HEAD (require_safe); without it a POST would get
# the CSRF 403 instead of 405.
@csrf_exempt
@require_safe
def serve_media(request, path):
    relpath = resolve_media_path(path)
    if relpath is None:
        raise Http404('No such file')
    full_path = media_file_path(relpath)
    if not os.path.isfile(full_path):
        raise Http404('No such file')
    allowed, public = can_access_media(request.user, relpath)
    if not allowed:
        raise Http404('No such file')

    content_type, disposition = media_headers(relpath)
    prefix = getattr(settings, 'MEDIA_ACCEL_REDIRECT_PREFIX', '')
    if prefix:
        # nginx keeps these headers of the empty response when it serves the file.
        response = HttpResponse(content_type=content_type)
        response['X-Accel-Redirect'] = prefix + quote(relpath)
    else:
        response = FileResponse(open(full_path, 'rb'), content_type=content_type)
    if disposition:
        response['Content-Disposition'] = disposition
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = CACHE_PUBLIC if public else CACHE_PRIVATE
    return response
