from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GetReportViewSet

router = DefaultRouter()
router.register(r'report', GetReportViewSet, basename='report')


urlpatterns = [

] + router.urls

