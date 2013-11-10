import os

from django import template


register = template.Library()

@register.assignment_tag
def thumb_file(value):


    dn = os.path.dirname(value)
    fn, ext = os.path.splitext( os.path.basename(value) )

    tdn = os.path.join(dn,'thumbs')
    return os.path.join(tdn,fn+'_thumb.jpg')
