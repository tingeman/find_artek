from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GetReportViewSet, GetFeatureViewSet, GetPersonViewSet, GetNextReportNumberView

router = DefaultRouter()
router.register(r'report', GetReportViewSet, basename='report')
router.register(r'feature', GetFeatureViewSet, basename='feature')
router.register(r'person', GetPersonViewSet, basename='person')

urlpatterns = [

path("ajax/next-report-number/", GetNextReportNumberView.as_view(), name="get_next_report_number"),

] + router.urls

