from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .serializers import PublicationSerializer, FeatureSerializer, PersonSerializer
from publications.models import Publication, Topic, Feature, Person
import http.client
import json



class GetReportViewSet(viewsets.ModelViewSet):

    serializer_class = PublicationSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        queryset = Publication.objects.all()
        filter_param = self.request.query_params.get('topic', None)
        if filter_param is not None:
            queryset = queryset.filter(topic__name=filter_param)
        return queryset