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
from django.views.generic import RedirectView
import django_cas_ng.views
from publications_meta.views import AdminCasLoginView

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
    path('api/', include('api.urls')),

    #swagger ui
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    
    # redoc
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    
    # redirect root URL to pubs/publist
    path("", RedirectView.as_view(url="publications/frontpage/", permanent=True)),
    
    # include the primary publication
    path("publications/", include("publications.urls")),
    
    
    # cas login and logout
    path("login", django_cas_ng.views.LoginView.as_view(), name="cas_ng_login"),
    path("logout", django_cas_ng.views.LogoutView.as_view(), name="cas_ng_logout"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    