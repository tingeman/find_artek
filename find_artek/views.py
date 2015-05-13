import sys
import traceback
import os.path
import shutil
from datetime import datetime

from django.http import HttpResponseServerError, HttpResponse
from django.shortcuts import render_to_response  # , get_object_or_404
from django.template import RequestContext
from django.conf import settings
from django.template import Context, loader
from django.contrib.auth.decorators import login_required


def index(request):
    return render_to_response('index.html', {},
                              context_instance=RequestContext(request))


def test(request):
    return render_to_response('test.html', {'STATIC_ROOT': settings.STATIC_ROOT},
                              context_instance=RequestContext(request))


def custom_500(request):
    t = loader.get_template('500.html')
    type, value, tb = sys.exc_info()
    return HttpResponseServerError(t.render(Context({
        'exception_value': value, })))

		
def error_404_view(request):
    tb = ''.join(traceback.format_exception(*sys.exc_info()))
    return render_to_response('404.html', {'exception': ""},
						      context_instance=RequestContext(request))

def error_500_view(request):
    tb = ''.join(traceback.format_exception(*sys.exc_info()))
    return render_to_response('500.html', {'exception': ""},
						      context_instance=RequestContext(request))

		
		

@login_required(login_url='/accounts/login/')
def db_backup(request):
    if os.path.exists(settings.DATABASES['default']['NAME']):
        head, tail = os.path.split(settings.DATABASES['default']['NAME'])
        backup_name = os.path.join(head, "{0}".format(datetime.now().strftime('%Y%m%d_%H%M%S_')) + tail)

        shutil.copy2(settings.DATABASES['default']['NAME'], backup_name)

        if os.path.exists(backup_name):
            return HttpResponse('A backup was created.')
        else:
            return HttpResponse('Backup not created...! (Can''t tell you why!)')

    return HttpResponse('The database file was not found! No backup created.')
