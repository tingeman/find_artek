from django.urls import path
from . import views

urlpatterns = [
    path('frontpage/', views.frontpage, name='frontpage'),
    path('publist/', views.publist, name='publist')
]