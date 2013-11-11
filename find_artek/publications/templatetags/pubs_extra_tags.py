import os
import os.path

from django.conf import settings
from django import template
from django.core.files.storage import default_storage


register = template.Library()

@register.filter
def basename(value):
    return os.path.basename(value)

@register.filter
def filename(value):
    return os.path.basename(value.file.name)

@register.assignment_tag
def thumb_file(value):
    """Generates the path name for the thumb_file for a report"""
    dn = os.path.dirname(value)
    fn, ext = os.path.splitext( os.path.basename(value) )
    tdn = os.path.join(dn,'thumbs')
    furl = os.path.join(tdn,fn+'_thumb.jpg')

    fpath = os.path.join(settings.MEDIA_ROOT, furl)
    furl = os.path.join(settings.MEDIA_URL, furl)

    if not default_storage.exists(fpath):
        furl = os.path.join(settings.STATIC_URL,'publications',
                        'images','preview_not_available.png')

    return furl
