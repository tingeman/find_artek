from django.urls import include, path
from . import views
from .views_administration import AdministrationView
from .views_persons import (
    PersonConfirmView, PersonMergeConfirmView, PersonMergeDoView, PersonMergeView,
)
from publications.workflows.person import disambiguate_person_step, complete_person_workflow

app_name = 'publications'

urlpatterns = [
    path('base/', views.BaseView.as_view(), name='base'),
    path('frontpage/', views.FrontPageView.as_view(), name='frontpage'),
    path('map/', views.MapView.as_view(), name='map'),
    path('reports/', views.ReportsView.as_view(), name='reports'),
    path('persons/', views.PersonsView.as_view(), name='persons'),

    # Tile page with the add/import tools (FA-R100), linked from the header
    path('administration/', AdministrationView.as_view(), name='administration'),

    # Excel file upload for adding publications
    path('add/reports_from_file/', views.AddReportsFromFileUploadView.as_view(), name='add_reports_from_file_upload'),

    path('report/<int:pk>/', views.ReportView.as_view(), name='report'),
    path('report/<int:pk>/appendix/upload/', views.UploadAppendixView.as_view(), name='upload_appendix'),
    # edit (may edit the report): GET confirmation page, POST deletes one appendix (FA-R104)
    path('report/<int:pk>/appendix/<int:file_pk>/delete/', views.DeleteAppendixView.as_view(),
         name='delete_appendix'),
    path('person/<int:pk>/', views.PersonView.as_view(), name='person'),
    # POST only, merge_person (editors): clear the person's duplicate markers (FA-R66)
    path('person/<int:pk>/confirm/', PersonConfirmView.as_view(), name='person_confirm'),
    # merge_person (editors): merge duplicates into this person (FA-R58). The page is GET; the
    # confirmation (writes nothing) and the merge itself are POST only.
    path('person/<int:pk>/merge/', PersonMergeView.as_view(), name='person_merge'),
    path('person/<int:pk>/merge/confirm/', PersonMergeConfirmView.as_view(),
         name='person_merge_confirm'),
    path('person/<int:pk>/merge/do/', PersonMergeDoView.as_view(), name='person_merge_do'),
    path('feature/<int:pk>/', views.FeatureView.as_view(), name='feature'),
    path('feature/<int:pk>/edit/', views.EditFeatureByMapView.as_view(), name='edit_feature_by_map'),
    path('feature/<int:pk>/edit-coordinates/', views.EditFeatureCoordinatesView.as_view(), name='edit_feature_coordinates'),
    path('feature/<int:pk>/delete/', views.DeleteFeatureView.as_view(), name='delete_feature'),
    # edit_feature: upload files and images to a feature; GET confirmation page and POST
    # delete of one file or image (features T8, FA-R64)
    path('feature/<int:pk>/upload/', views.UploadFeatureMediaView.as_view(),
         name='upload_feature_media'),
    path('feature/<int:pk>/file/<int:record_pk>/delete/',
         views.DeleteFeatureMediaView.as_view(kind='file'), name='delete_feature_file'),
    path('feature/<int:pk>/image/<int:record_pk>/delete/',
         views.DeleteFeatureMediaView.as_view(kind='image'), name='delete_feature_image'),
    # path('login/', views.LoginView.as_view(), name='login'),

    # Add report workflows
    path('report/add/', views.ReportFormView.as_view(), name='add_report'),
    path('report/add/review/', views.ReportReviewView.as_view(), name='add_report_review'),
    path('report/add/finalize/', views.ReportFinalizeView.as_view(), name='add_report_finalize'),

    # edit report workflows
    path('report/<int:pk>/edit/', views.ReportFormView.as_view(), name='edit_report'),
    path('report/<int:pk>/edit/review/', views.ReportReviewView.as_view(), name='edit_report_review'),
    path('report/<int:pk>/edit/finalize/', views.ReportFinalizeView.as_view(), name='edit_report_finalize'),

    # path('add/report/', views.AddEditReportView.as_view(), name='add_report'),
    # path('add/report/review/', views.AddEditReportReviewView.as_view(), name='review_add_report'),
    # path('report/<int:pk>/edit/', views.AddEditReportView.as_view(), name='edit_report'),
    # path('report/<int:pk>/edit/review/', views.AddEditReportReviewView.as_view(), name='review_edit_report'),
    path('report/<int:pk>/delete/', views.DeleteReportView.as_view(), name='delete_report'),
    path('report/<int:pk>/change-number/', views.ChangeReportNumberView.as_view(), name='change_report_number'),
    # add_feature on the report: delete its features, unlink shared ones (features T7)
    path('report/<int:pk>/features/delete/', views.DeleteReportFeaturesView.as_view(),
         name='delete_report_features'),
    path('report/<int:report_pk>/add-feature-by-coordinates/', views.AddFeatureCoordinatesView.as_view(), name='add_feature_coordinates'),
    path('report/<int:report_pk>/add-feature-by-map/', views.AddFeatureByMapView.as_view(), name='add_feature_by_map'),
    path('report/<int:pub_id>/verify/', views.VerifyReportView.as_view(), name='verify_report'),
    path('report/<int:pub_id>/unverify/', views.UnverifyReportView.as_view(), name='unverify_report'),
    path("test/autocomplete/person/", views.PersonAutocompleteView.as_view(), name="person-autocomplete"),
    # path("ajax/next-report-number/", views.GetNextReportNumberView.as_view(), name="get_next_report_number"),
    
    # AJAX endpoints for person disambiguation workflow
    path("ajax/person/add/", views.add_person_ajax, name="add_person_ajax"),
    
    # Multi-step person disambiguation workflow
    path("workflow/person/disambiguate/", disambiguate_person_step, name="disambiguate_person_step"),
    path("workflow/person/complete/", complete_person_workflow, name="complete_person_workflow"),

    # Bulk delete publications
    path('reports/bulk-delete/', views.BulkDeletePublicationsView.as_view(), name='bulk_delete_publications'),


    #path("test/create/", views.TestPublicationCreateView.as_view(), name="test-publication-create"),
    #path("test/create/<int:pk>/", views.TestPublicationCreateViewNEW.as_view(), name="test-publication-create"),
]