from django.shortcuts import get_object_or_404, render_to_response
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from models import MultiuploaderImage
from django.core.files.uploadedfile import UploadedFile

#importing json parser to generate jQuery plugin friendly json response
from django.utils import simplejson

#for generating thumbnails



from django.views.decorators.csrf import csrf_exempt

import logging
log = logging


@csrf_exempt
def multiuploader_delete(request, pk):
    """
    View for deleting photos with multiuploader AJAX plugin.
    made from api on:
    https://github.com/blueimp/jQuery-File-Upload
    """

    if request.method == 'POST':
        log.info(u'Called delete image. image id=' + str(pk))
        image = get_object_or_404(MultiuploaderImage, pk=pk)
        image.delete()
        log.info(u'DONE. Deleted photo id=' + str(pk))
        return HttpResponse(str(pk))
    else:
        log.info(u'Received not POST request to delete image view')
        return HttpResponseBadRequest('Only POST accepted')



def multi_show_uploaded(request, key):
    """Simple file view helper.
    Used to show uploaded file directly"""
    image = get_object_or_404(MultiuploaderImage, key_data=key)
    url = settings.MEDIA_URL + image.image.name
    return render_to_response('multiuploader/one_image.html', {"multi_single_url": url, })
