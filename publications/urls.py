from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('frontpage/', views.FrontPageView.as_view(), name='frontpage'),
    path('map/', views.MapView.as_view(), name='map'),
    path('reports/', views.ReportsView.as_view(), name='reports'),
    path('report/<int:publication_id>/', views.ReportView.as_view(), name='report'),
    path('feature/<int:feature_id>/', views.FeatureView.as_view(), name='feature'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page=reverse_lazy('frontpage')), name='logout'),

    # API DATA
    path('map/data/', views.map_data, name='map_data'),
]