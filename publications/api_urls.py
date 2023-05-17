# api_urls.py
from django.urls import path
from . import api_views

urlpatterns = [
    path('feature/', api_views.feature_geographic_location_data, name='feature_geographic_location_data'),
    # ...other API URLs...
]