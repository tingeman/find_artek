from django.urls import include, path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('base/', views.BaseView.as_view(), name='base'),
    path('frontpage/', views.FrontPageView.as_view(), name='frontpage'),
    path('map/', views.MapView.as_view(), name='map'),
    path('reports/', views.ReportsView.as_view(), name='reports'),
    path('persons/', views.PersonsView.as_view(), name='persons'),

    path('report/<int:pk>/', views.ReportView.as_view(), name='report'),
    path('person/<int:pk>/', views.PersonView.as_view(), name='person'),
    path('feature/<int:pk>/', views.FeatureView.as_view(), name='feature'),
    # path('login/', views.LoginView.as_view(), name='login'),
    # path('logout/', views.LogoutView.as_view(), name='logout'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page=reverse_lazy('frontpage')), name='logout'),

    #path('^pubs/edit/report/(?P<pub_id>\d+)/$', views.AddEditReportView.as_view(), name='add_edit_report'),
]