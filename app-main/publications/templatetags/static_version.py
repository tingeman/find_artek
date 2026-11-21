"""{% versioned_static %}: a static URL with the release version as query string.

``{% versioned_static 'publications/js/file-upload.js' %}`` gives
``{% static 'publications/js/file-upload.js' %}?v=<settings.STATIC_ASSET_VERSION>``. The
dev server and nginx send static files without a version in the name, so browsers may keep an
old copy after a release; a new query string makes them fetch the file again. The ``static``
part handles the URL prefix (STATIC_URL, '/find/static/' in production).
"""
from urllib.parse import quote

from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def versioned_static(path):
    return f'{static(path)}?v={quote(str(settings.STATIC_ASSET_VERSION))}'
