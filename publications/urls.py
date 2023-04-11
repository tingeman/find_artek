from django.urls import path
from . import views

urlpatterns = [
    path('frontpage/', views.frontpage, name='frontpage'),
    path('publist/', views.publist, name='publist'),
    path('report/<int:pub_id>/', views.detail, name='detail'),
    # q: how to implement this in django 4.1 url(r'^pubs/report/(?P<pub_id>\d+)/$', 'publications.views.detail'),
    # path('report/<int:pk>/', views.detail, name='detail'),

]