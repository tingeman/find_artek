from django.urls import include, path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .person_workflow import disambiguate_person_step, complete_person_workflow

app_name = 'publications'

urlpatterns = [
    path('base/', views.BaseView.as_view(), name='base'),
    path('frontpage/', views.FrontPageView.as_view(), name='frontpage'),
    path('map/', views.MapView.as_view(), name='map'),
    path('reports/', views.ReportsView.as_view(), name='reports'),
    path('persons/', views.PersonsView.as_view(), name='persons'),

    path('report/<int:pk>/', views.ReportView.as_view(), name='report'),
    path('report/<int:pk>/appendix/upload/', views.UploadAppendixView.as_view(), name='upload_appendix'),
    path('person/<int:pk>/', views.PersonView.as_view(), name='person'),
    path('feature/<int:pk>/', views.FeatureView.as_view(), name='feature'),
    path('feature/<int:pk>/delete/', views.DeleteFeatureView.as_view(), name='delete_feature'),
    # path('login/', views.LoginView.as_view(), name='login'),
    # path('logout/', views.LogoutView.as_view(), name='logout'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page=reverse_lazy('publications:frontpage')), name='logout'),

    path('add/report/', views.AddEditReportView.as_view(), name='add_report'),
    path('add/report/review/', views.AddEditReportReviewView.as_view(), name='add_report_review'),
    path('add/report/finalize/', views.AddEditReportView.as_view(), name='publication_final_save'),
    path('report/<int:pk>/edit/', views.AddEditReportView.as_view(), name='edit_report'),
    path('report/<int:pk>/edit/review/', views.AddEditReportReviewView.as_view(), name='edit_report_review'),
    path('report/<int:pk>/edit/finalize/', views.AddEditReportView.as_view(), name='edit_report_final_save'),
    path('report/<int:pk>/delete/', views.DeleteReportView.as_view(), name='delete_report'),
    path('report/<int:pk>/change-number/', views.ChangeReportNumberView.as_view(), name='change_report_number'),
    path('report/<int:report_pk>/add-feature-by-coordinates/', views.AddFeatureCoordinatesView.as_view(), name='add_feature_coordinates'),
    path("test/autocomplete/person/", views.PersonAutocompleteView.as_view(), name="person-autocomplete"),
    path("select/persons/", views.PersonSelectView.as_view(), name="select-persons"),
    path("ajax/next-report-number/", views.GetNextReportNumberView.as_view(), name="get_next_report_number"),
    
    # AJAX endpoints for person disambiguation workflow
    path("ajax/person/check/", views.check_person_ajax, name="check_person_ajax"),
    path("ajax/person/add/", views.add_person_ajax, name="add_person_ajax"),
    
    # Multi-step person disambiguation workflow
    path("workflow/person/disambiguate/", disambiguate_person_step, name="disambiguate_person_step"),
    path("workflow/person/complete/", complete_person_workflow, name="complete_person_workflow"),


    #path("test/create/", views.TestPublicationCreateView.as_view(), name="test-publication-create"),
    #path("test/create/<int:pk>/", views.TestPublicationCreateViewNEW.as_view(), name="test-publication-create"),
]