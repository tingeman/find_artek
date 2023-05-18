# api_urls.py
from django.urls import path
from . import api_views

urlpatterns = [
    path('feature/', api_views.get_feature_geographic_location_data, name='get_feature_geographic_location_data'),
    path('reports/', api_views.get_reports_table_data, name='get_reports_table_data'),
    # ...other API URLs...
]