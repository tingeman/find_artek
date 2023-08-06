from django import template
from django.conf import settings

register = template.Library()


@register.inclusion_tag('multiuploader/multiuploader_main.html')
def multiupform(batch_tag):
    return {'static_url': settings.STATIC_URL,
            'batch_tag': batch_tag}
