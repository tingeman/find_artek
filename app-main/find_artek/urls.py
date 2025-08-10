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
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import RedirectView
import django_cas_ng.views
from publications_meta.views import AdminCasLoginView

from django.urls import re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


from django.views import View
from django.http import HttpResponse
import json

class DebugRootView(View):
    def get(self, request):
        debug_info = {
            'path': request.path,
            'path_info': request.path_info,
            'script_name': request.META.get('SCRIPT_NAME', 'Not set'),
            'force_script_name': settings.FORCE_SCRIPT_NAME,
            'url_prefix': settings.URL_PREFIX,
        }
        return HttpResponse(f"<pre>{json.dumps(debug_info, indent=2)}</pre>")
    




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
    path("login", django_cas_ng.views.LoginView.as_view(), name="cas_ng_login"),
    path("logout", django_cas_ng.views.LogoutView.as_view(), name="cas_ng_logout"),

    # Temporary debug root view
    path("debug-root/", DebugRootView.as_view(), name="debug-root"),


    # Root redirect pattern MUST BE LAST - catch-all for any unmatched URLs
    path("", RedirectView.as_view(pattern_name="publications:frontpage", permanent=True)),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()

    