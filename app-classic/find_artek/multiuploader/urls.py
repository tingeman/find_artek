from django.conf.urls import patterns, include, url
from django.conf import settings

try:
    delete_url = settings.MULTI_FILE_DELETE_URL
except AttributeError:
    delete_url = 'multi_delete'

try:
    image_url = settings.MULTI_IMAGE_URL
except AttributeError:
    image_url = 'multi_image'

urlpatterns = patterns('',
    url(r'^'+delete_url[1:]+'/(?P<pk>\d+)/$', 'multiuploader.views.multiuploader_delete'),
    url(r'^multi/$', 'multiuploader.views.multiuploader', name='multi'),
    url(r'^'+image_url[1:]+'/(?P<pk>\d+)/$', 'multiuploader.views.multi_show_uploaded'),
)
