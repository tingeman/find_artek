from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('frontpage/', views.FrontPageView.as_view(), name='frontpage'),
    path('map/', views.map, name='map'),
    path('map/data/', views.map_data, name='map_data'),
    path('reports/', views.reports, name='reports'),
    path('report/<int:publication_id>/', views.report, name='report'),
    path('feature/<int:feature_id>/', views.feature, name='feature'),
    path('login/', views.login_view, name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page=reverse_lazy('frontpage')), name='logout'),
]