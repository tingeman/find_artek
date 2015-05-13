# -*- coding: utf_8 -*-

# Django settings for find_artek project.

import os
import ldap
from django_auth_ldap.config import LDAPSearch, GroupOfNamesType, ActiveDirectoryGroupType
from django.conf import global_settings

SITE_ROOT = "D:/find_artek_www/"
DEBUG = False
ONLINE = True

if not os.path.exists(SITE_ROOT):
    SITE_ROOT = "C:/THIN/www/django_sites/find_artek_vb/"
    DEBUG = True
    ONLINE = False
    
    if not os.path.exists(SITE_ROOT):
        raise ValueError('SITE_ROOT incorrectly defined, path does not exist.')


SETTINGS_ROOT = os.path.dirname(__file__)
TEMPLATE_DEBUG = DEBUG


ADMINS = (
    # ('Your Name', 'your_email@example.com'),
    ('Thomas Ingeman-Nielsen', 'tin@byg.dtu.dk'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',   # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': os.path.join(SITE_ROOT, 'find_artek.sqlite'),    # Or path to database file if using sqlite3.
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'Europe/Copenhagen'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

LANGUAGES = (
    ('en', 'English'),
    ('da', 'Danish'),
)

LOCALE_PATHS = (
    '/conf/locale',
    '/publications/conf/local'
)

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.path.abspath(os.path.join(SITE_ROOT, '..', 'find_artek_media'))
#MEDIA_ROOT = os.path.abspath(os.path.join(SITE_ROOT, 'find_artek_media'))
#MEDIA_ROOT = os.path.join(SETTINGS_ROOT, "media_root/")

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
#STATIC_ROOT = '/home/bitnami/apps/find_artek/find_artek/static'
STATIC_ROOT = os.path.join(SETTINGS_ROOT, "static_root/")

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    #'/opt/bitnami/apps/django/lib/python2.7/site-packages/django/contrib/admin/static',
    os.path.join(SETTINGS_ROOT, 'static/'),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'HODZ<ZSQYh|B6Q|kgHHoVlD=B<[/7fR5L>U)W8)Rf,j6:]/*fp'
# generated at http://www.fourmilab.ch/onetime/otpjs.html
# by THIN on October 19, 2012

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    # 'django.template.loaders.eggs.Loader',
)

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    # 'django.template.loaders.eggs.Loader',
)


TEMPLATE_CONTEXT_PROCESSORS = global_settings.TEMPLATE_CONTEXT_PROCESSORS + (
    "django.core.context_processors.request",
)


MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.locale.LocaleMiddleware'
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'find_artek.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'find_artek.wsgi.application'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(SETTINGS_ROOT, 'templates'),
    os.path.join(SETTINGS_ROOT, 'publications/templates'),
    os.path.join(SITE_ROOT, 'multiuploader/templates'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    'django.contrib.gis',
    'south',
    'django_extensions',
    'olwidget',
    'multiuploader',
    'sorl.thumbnail',
    'find_artek.publications',
)


## LDAP Baseline configuration.
AUTH_LDAP_SERVER_URI = "ldap://win.dtu.dk"

AUTH_LDAP_BIND_DN = "cn=BYG-Artek_AD_Read,ou=Funktionskonti,ou=BYG,ou=Institutter,DC=win,DC=dtu,DC=dk"
AUTH_LDAP_BIND_PASSWORD = "KETRAGYB"

AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=DTUBaseUsers,dc=win,dc=dtu,dc=dk",
                                   ldap.SCOPE_SUBTREE, "(name=%(user)s)")

AUTH_LDAP_GROUP_SEARCH = LDAPSearch("dc=win,dc=dtu,dc=dk", ldap.SCOPE_SUBTREE, "(objectClass=group)")
AUTH_LDAP_GROUP_TYPE = ActiveDirectoryGroupType(name_attr="cn")


AUTH_LDAP_USER_ATTR_MAP = {"first_name": "givenName", "last_name": "sn",
                           "email": "mail"}

AUTH_LDAP_USER_FLAGS_BY_GROUP = {
    #"is_active": "cn=active,ou=django,ou=groups,dc=example,dc=com",
    "is_staff": "CN=BYG-ArktiskCenter,OU=Grupper_migreret_fra_BYG,OU=Security group,OU=BYG,OU=Institutter,DC=win,DC=dtu,DC=dk",
    #"is_superuser": "cn=superuser,ou=django,ou=groups,dc=example,dc=com"
}

# This is the default, but I like to be explicit.
AUTH_LDAP_ALWAYS_UPDATE_USER = True

# Use LDAP group membership to calculate group permissions.
AUTH_LDAP_FIND_GROUP_PERMS = True

# Cache group memberships for an hour to minimize LDAP traffic
AUTH_LDAP_CACHE_GROUPS = True
AUTH_LDAP_GROUP_CACHE_TIMEOUT = 3600




# 'is_active': True,
# 'is_staff': False,
# 'is_superuser': False,


if ONLINE:
    AUTHENTICATION_BACKENDS = (
        'django_auth_ldap.backend.LDAPBackend',
        'django.contrib.auth.backends.ModelBackend',
    )
else:
    AUTHENTICATION_BACKENDS = (
        'django.contrib.auth.backends.ModelBackend',
    )





# According to: https://groups.google.com/forum/?fromgroups=#!topic/olwidget/wmVGC3TiK8w
#OL_API = 'http://openlayers.org/dev/OpenLayers.js'
# 2013-05-22: The above line was causing a problem with the edit maps in add-feature
# form and admin feature page. We will have to live with the pop-up on google-earth map,
# or implement a direct google earth map, outside olwidget.

GOOGLE_API_KEY = 'AIzaSyBIagLz1ayoRbJZef1Er9h8WkWJF26hr44'
#OLWIDGET_STATIC_URL = 'C:/THIN/www/apps/find_artek/find_artek/static/olwidget'
#OLWIDGET_MEDIA_URL = 'C:/THIN/www/apps/find_artek/find_artek/static/olwidget'


# Tells whether reverse url finish with slash or not.
APPEND_SLASH = True

# Redirect to the following view after successful authentication
#LOGIN_REDIRECT_URL = "/pubs/frontpage"

# Parameters for multifileuploader
MULTI_FILE_DELETE_URL = '/multi_delete'
MULTI_IMAGE_URL = '/multi_image'
MULTI_IMAGES_FOLDER = 'uploaded_files'

#THUMBNAIL_DEBUG = True
#THUMBNAIL_CONVERT = 'C:/Program Files (x86)/GraphicsMagick-1.3.17-Q16/gm convert'
#THUMBNAIL_IDENTIFY = 'C:/Program Files (x86)/GraphicsMagick-1.3.17-Q16/gm identify'
#THUMBNAIL_CONVERT = 'gm convert'
#THUMBNAIL_IDENTIFY = 'gm identify'
#THUMBNAIL_CONVERT = 'convert'
#THUMBNAIL_IDENTIFY = 'identify'
#THUMBNAIL_ENGINE = 'sorl.thumbnail.engines.convert_engine.Engine'
#THUMBNAIL_PROGRESSIVE = False

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
#LOGGING = {
#    'version': 1,
#    'disable_existing_loggers': False,
#    'filters': {
#        'require_debug_false': {
#            '()': 'django.utils.log.RequireDebugFalse'
#        }
#    },
#    'handlers': {
#        'mail_admins': {
#            'level': 'ERROR',
#            'filters': ['require_debug_false'],
#            'class': 'django.utils.log.AdminEmailHandler'
#        }
#    },
#    'loggers': {
#        'django.request': {
#            'handlers': ['mail_admins'],
#            'level': 'ERROR',
#            'propagate': True,
#        },
#    }
#}


LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/default.log',
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
            'formatter': 'standard',
        },
       'find_artek_handler': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/find_artek.log',
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
            'formatter': 'standard',
        },
        'ldap_handler': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/ldap.log',
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
            'formatter': 'standard',
        },
        'request_handler': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/django_request.log',
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
            'formatter': 'standard',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'ERROR',
            'propagate': True
        },
        'django.db': {
            'handlers': ['default'],
            'level': 'ERROR',
            'propagate': False
        },
        'django.request': {
            'handlers': ['request_handler'],
            'level': 'DEBUG',
            'propagate': False
        },
        'django_auth_ldap': {
            'handlers': ['ldap_handler'],
            'level': 'DEBUG',
            'propagate': False
        },
        'find_artek': {
            'handlers': ['find_artek_handler'],
            'level': 'DEBUG',
            'propagate': False
        },

    }
}
