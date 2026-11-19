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
"""
import mimetypes
import os
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe

from publications.media_access import can_access_media, media_file_path, resolve_media_path

CACHE_PUBLIC = 'public, max-age=3600'
CACHE_PRIVATE = 'private, no-store'


def _content_type(relpath):
    content_type, encoding = mimetypes.guess_type(relpath)
    if not content_type or encoding:
        return 'application/octet-stream'
    return content_type


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

    prefix = getattr(settings, 'MEDIA_ACCEL_REDIRECT_PREFIX', '')
    if prefix:
        response = HttpResponse(content_type=_content_type(relpath))
        response['X-Accel-Redirect'] = prefix + quote(relpath)
    else:
        response = FileResponse(open(full_path, 'rb'))
    response['Cache-Control'] = CACHE_PUBLIC if public else CACHE_PRIVATE
    return response
