from django.urls import include, path, reverse_lazy
from django.contrib.auth import views as auth_views

# Import view classes directly from their modules to avoid circular imports
from publications.views.base_views import BaseView, FrontPageView
from publications.views.feature_views import MapView, FeatureView, DeleteFeatureView, AddFeatureCoordinatesView, AddFeatureByMapView
from publications.views.file_views import AddReportsFromFileUploadView, UploadAppendixView
from publications.views.person_views import PersonsView, PersonView, PersonAutocompleteView, PersonSelectView
from publications.views.publication_views import (
    ReportsView, ReportView, ReportFormView, ReportReviewView, ReportFinalizeView,
    VerifyReportView, UnverifyReportView, ChangeReportNumberView, DeleteReportView,
    BulkDeletePublicationsView
)
from publications.views.disambiguation_views import (
    DisambiguatePersonStepView, FinalizePersonWorkflowView,
    ClearDisambiguationWorkflowsView, DisambiguationWorkflowStatusView
)

app_name = 'publications'

urlpatterns = [
    path('base/', BaseView.as_view(), name='base'),
    path('frontpage/', FrontPageView.as_view(), name='frontpage'),
    path('map/', MapView.as_view(), name='map'),
    path('reports/', ReportsView.as_view(), name='reports'),
    path('persons/', PersonsView.as_view(), name='persons'),

    # Excel file upload for adding publications
    path('add/reports_from_file/', AddReportsFromFileUploadView.as_view(), name='add_reports_from_file_upload'),

    path('report/<int:pk>/', ReportView.as_view(), name='report'),
    path('report/<int:pk>/appendix/upload/', UploadAppendixView.as_view(), name='upload_appendix'),
    path('person/<int:pk>/', PersonView.as_view(), name='person'),
    path('feature/<int:pk>/', FeatureView.as_view(), name='feature'),
    path('feature/<int:pk>/delete/', DeleteFeatureView.as_view(), name='delete_feature'),
    # path('login/', views.LoginView.as_view(), name='login'),
    # path('logout/', views.LogoutView.as_view(), name='logout'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page=reverse_lazy('publications:frontpage')), name='logout'),

    # Add report workflows
    path('report/add/', ReportFormView.as_view(), name='add_report'),
    path('report/add/review/', ReportReviewView.as_view(), name='add_report_review'),
    path('report/add/finalize/', ReportFinalizeView.as_view(), name='add_report_finalize'),

    # edit report workflows
    path('report/<int:pk>/edit/', ReportFormView.as_view(), name='edit_report'),
    path('report/<int:pk>/edit/review/', ReportReviewView.as_view(), name='edit_report_review'),
    path('report/<int:pk>/edit/finalize/', ReportFinalizeView.as_view(), name='edit_report_finalize'),

    # path('add/report/', views.AddEditReportView.as_view(), name='add_report'),
    # path('add/report/review/', views.AddEditReportReviewView.as_view(), name='review_add_report'),
    # path('add/report/finalize/', views.AddEditReportView.as_view(), name='publication_final_save'),
    # path('report/<int:pk>/edit/', views.AddEditReportView.as_view(), name='edit_report'),
    # path('report/<int:pk>/edit/review/', views.AddEditReportReviewView.as_view(), name='review_edit_report'),
    # path('report/<int:pk>/edit/finalize/', views.AddEditReportView.as_view(), name='edit_report_final_save'),
    path('report/<int:pk>/delete/', DeleteReportView.as_view(), name='delete_report'),
    path('report/<int:pk>/change-number/', ChangeReportNumberView.as_view(), name='change_report_number'),
    path('report/<int:report_pk>/add-feature-by-coordinates/', AddFeatureCoordinatesView.as_view(), name='add_feature_coordinates'),
    path('report/<int:report_pk>/add-feature-by-map/', AddFeatureByMapView.as_view(), name='add_feature_by_map'),
    path('report/<int:pub_id>/verify/', VerifyReportView.as_view(), name='verify_report'),
    path('report/<int:pub_id>/unverify/', UnverifyReportView.as_view(), name='unverify_report'),
    path("test/autocomplete/person/", PersonAutocompleteView.as_view(), name="person-autocomplete"),
    path("select/persons/", PersonSelectView.as_view(), name="select-persons"),
    # path("ajax/next-report-number/", views.GetNextReportNumberView.as_view(), name="get_next_report_number"),
    
    # AJAX endpoints for person disambiguation workflow
    # TODO: Should we change to use the api instead???
    #       We commented out these methods
    #path("ajax/person/check/", person_views.check_person_ajax, name="check_person_ajax"),
    #path("ajax/person/add/", person_views.add_person_ajax, name="add_person_ajax"),
    
    # Multi-step person disambiguation workflow
    path("workflow/person/disambiguate/", DisambiguatePersonStepView.as_view(), name="disambiguate_person_step"),
    path("workflow/person/finalize/", FinalizePersonWorkflowView.as_view(), name="finalize_person_workflow"),
    path('workflow/person/clear/', ClearDisambiguationWorkflowsView.as_view(), name='clear_disambiguation_workflows'),
    path('workflow/person/status/', DisambiguationWorkflowStatusView.as_view(), name='disambiguation_workflow_status'),
    
    # Bulk delete publications
    path('reports/bulk-delete/', BulkDeletePublicationsView.as_view(), name='bulk_delete_publications'),


    #path("test/create/", views.TestPublicationCreateView.as_view(), name="test-publication-create"),
    #path("test/create/<int:pk>/", views.TestPublicationCreateViewNEW.as_view(), name="test-publication-create"),
]