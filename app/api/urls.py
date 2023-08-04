from django.urls import path
from . import views

urlpatterns = [
    # path('', views.getData, name='getData'),
    path('reports/', views.get_reports, name='get_reports'),
    path('features/', views.get_feature_data, name='get_feature_data'),
    path('persons/', views.get_persons, name='get_persons'),
    path('person/<int:pk>/', views.get_person, name='get_person'),
    path('dtu/search/<str:full_name>/', views.search_dtu, name='search_dtu'),

]