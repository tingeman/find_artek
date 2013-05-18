import os
import sys

path = 'D:\\find_artek_www\\'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'find_artek.settings'

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()


