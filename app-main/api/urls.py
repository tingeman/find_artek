from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GetReportViewSet, GetFeatureViewSet

router = DefaultRouter()
router.register(r'report', GetReportViewSet, basename='report')
router.register(r'feature', GetFeatureViewSet, basename='feature')


urlpatterns = [

] + router.urls

