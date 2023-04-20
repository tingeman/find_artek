from django.urls import path
from . import views

urlpatterns = [
    path('frontpage/', views.frontpage, name='frontpage'),
    path('map/', views.map, name='map'),
    path('map/data/', views.map_data, name='map_data'),
    path('reports/', views.reports, name='reports'),
    path('report/<int:publication_id>/', views.report, name='report'),
    
    # q: how to implement this in django 4.1 url(r'^pubs/report/(?P<pub_id>\d+)/$', 'publications.views.detail'),
    # path('report/<int:pk>/', views.detail, name='detail'),
    
]