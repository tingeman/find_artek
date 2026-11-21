"""find_artek URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django import views
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import RedirectView
import django_cas_ng.views
from find_artek.cas_views import LoginView as CasLoginView
from publications_meta.views import AdminCasLoginView
from publications.views_media import serve_media

from django.urls import re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


schema_view = get_schema_view(
   openapi.Info(
      title="Find_Artek Data API",
      default_version='v1',
      description="A simple REST API",
      terms_of_service="",
      contact=openapi.Contact(email="vicre@dtu.dk"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)


urlpatterns = [

    # admin panel 
    path('admin/', admin.site.urls),
    path('admin-cas-login/', AdminCasLoginView.as_view(), name='admin-cas-login'),

    # api/*
    path('api/', include(('api.urls', 'api'), namespace='api')),

    #swagger ui
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    
    # redoc
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # select2
    path("select2/", include("django_select2.urls")),
   
    # include the primary publication
    path("publications/", include("publications.urls", namespace="publications")),
        
    # cas login and logout
    path("login", CasLoginView.as_view(), name="cas_ng_login"),
    path("logout", django_cas_ng.views.LogoutView.as_view(), name="cas_ng_logout"),


    # Root redirect pattern MUST BE LAST - catch-all for any unmatched URLs
    path("", RedirectView.as_view(pattern_name="publications:frontpage", permanent=True)),

]

# Every file under MEDIA_URL goes through the checked view (FA-R30, FA-R75 T5), also in dev.
# The route is MEDIA_URL without FORCE_SCRIPT_NAME (Django sees paths without the prefix):
# production '/find/media/' - '/find' -> 'media/<path>'; dev settings (no prefix) ->
# 'find/media/<path>'. In production nginx must proxy /find/media/ to Django (dtu_sus_web_server).
def _media_route():
    media_url = settings.MEDIA_URL
    script_name = (settings.FORCE_SCRIPT_NAME or '').rstrip('/')
    if script_name and media_url.startswith(script_name + '/'):
        media_url = media_url[len(script_name):]
    return media_url.lstrip('/') + '<path:path>'


urlpatterns += [path(_media_route(), serve_media, name='media')]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()

    