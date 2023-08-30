from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .serializers import PublicationSerializer, FeatureSerializer, PersonSerializer
from publications.models import Publication, Topic, Feature, Person
from rest_framework.exceptions import NotFound
# limit to only GET /report/ and GET /report/{id}/
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin

import http.client
import json



class GetReportViewSet(ListModelMixin, RetrieveModelMixin, viewsets.GenericViewSet):

    serializer_class = PublicationSerializer

    def get_available_topics():
        string_of_topics = ""
        topics = Topic.objects.all()
        for topic in topics:
            string_of_topics += f"\t{topic.topic}\n"
        return string_of_topics


    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='topic',
                in_=openapi.IN_QUERY,
                description=f"Filter publications by topic name. Available topics are:\n\n {get_available_topics()} \n if no topic is provided, all reports are returned.",
                type=openapi.TYPE_STRING,
            )
        ],
        responses={
            200: 'List of reports based on the given topic or all reports if no topic is provided.',
            404: 'Topic not found'
        }
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    # This functions returns the values to the client
    def get_queryset(self):
        queryset = Publication.objects.all()
        filter_param = self.request.query_params.get('topic', None)


        if filter_param is not None:

            try:
                topic = Topic.objects.get(topic=filter_param)
            except Topic.DoesNotExist:
                raise NotFound('Topic not found')

            queryset = queryset.filter(publication_topics=topic)

            
        return queryset
    



class GetFeatureViewSet(ListModelMixin, RetrieveModelMixin, viewsets.GenericViewSet):

    serializer_class = FeatureSerializer


    @swagger_auto_schema(
        manual_parameters=[

        ],
        responses={
            200: 'List of geograhic associated data.',
            404: 'Ressource not found'
        }
    )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    
    def get_queryset(self):
        queryset = Feature.objects.all()
    
        return queryset
