from django.conf import settings

def URL_PREFIX(request):
    return {
        'URL_PREFIX': settings.URL_PREFIX
    }