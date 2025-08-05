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

@register.filter
def report_type_display(value):
    """Convert report type codes to human-readable text"""
    if not value:
        return "Not specified"
    
    # Define the mapping once
    type_mapping = {
        'MASTERTHESIS': 'Master Thesis',
        'PHDTHESIS': 'PhD Thesis',
        'TECHREPORT': 'Technical Report',
        'ARTICLE': 'Article',
        'BOOK': 'Book',
        'INPROCEEDINGS': 'Conference Paper',
        'INCOLLECTION': 'Book Chapter',
        'INBOOK': 'Book Section',
        'PROCEEDINGS': 'Conference Proceedings',
        'MANUAL': 'Manual',
        'MISC': 'Miscellaneous',
        'UNPUBLISHED': 'Unpublished',
    }
        
    # If value is a PubType object, use its type attribute
    if hasattr(value, 'type'):
        return type_mapping.get(value.type, value.type)
    
    # If it's a numeric string (likely a PK), try to fetch the actual PubType
    if str(value).isdigit():
        try:
            from publications.models import PubType
            pub_type = PubType.objects.get(pk=int(value))
            return type_mapping.get(pub_type.type, pub_type.type)
        except Exception:
            # If we can't get the PubType, just return the value
            return value
    
    # For string type codes, apply the mapping directly
    return type_mapping.get(str(value), value)

@register.simple_tag
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

    furl = furl.replace('\\', '/')
    
    return furl
