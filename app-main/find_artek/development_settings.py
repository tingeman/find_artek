from .settings import *

DEBUG = True

FORCE_SCRIPT_NAME = ''
URL_PREFIX = ''
#STATIC_URL = ''
#MEDIA_URL = ''

# Override LOGGING for development: DEBUG level, log to both console and file
LOGGING['handlers']['file']['level'] = 'DEBUG'
LOGGING['handlers']['api_file']['level'] = 'DEBUG'
LOGGING['handlers']['console']['level'] = 'DEBUG'
LOGGING['loggers']['django']['handlers'] = ['file', 'console']
LOGGING['loggers']['django']['level'] = 'DEBUG'
LOGGING['loggers']['api']['handlers'] = ['api_file', 'console']
LOGGING['loggers']['api']['level'] = 'DEBUG'