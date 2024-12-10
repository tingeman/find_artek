from django.conf import settings

def js_url_prefix(request):
    return {
        'JS_URL_PREFIX': settings.JS_URL_PREFIX
    }