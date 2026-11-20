import logging
import json
import http.client

from django.db.models import Case, When, IntegerField
from django.utils.functional import lazy
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.views import APIView

from find_artek.search import get_query
from publications.models import Publication, Topic, Feature, Person
from publications import utils_models
from publications.visibility import visible_features, visible_publications
from .serializers import PublicationSerializer, FeatureSerializer, PersonSerializer


# Get a logger instance for your app
logger = logging.getLogger('api')
logger.warning("views.py is loaded")

# Get a logger instance for your app
logger = logging.getLogger('api')
logger.warning("views.py is loaded")

def _topic_parameter_description():
    """Description of the ``topic`` query parameter, with the topics in the database.

    Called when the Swagger schema is generated, not when the module is imported: a query at
    import time breaks ``manage.py check`` and ``migrate`` on an empty database (FA-R14).
    """
    topics = "".join(f"\t{topic.topic}\n" for topic in Topic.objects.all())
    return ("Filter publications by topic name. Available topics are:\n\n "
            f"{topics} \n if no topic is provided, all reports are returned.")


class GetReportViewSet(ListModelMixin, RetrieveModelMixin, viewsets.GenericViewSet):

    serializer_class = PublicationSerializer

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='topic',
                in_=openapi.IN_QUERY,
                # lazy: drf-yasg evaluates it when it renders the schema (each request)
                description=lazy(_topic_parameter_description, str)(),
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                name='author_id',
                in_=openapi.IN_QUERY,
                description="Filter publications by author ID.",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                name='supervisor_id',
                in_=openapi.IN_QUERY,
                description="Filter publications by supervisor ID.",
                type=openapi.TYPE_INTEGER,
            )
        ],
        responses={
            200: 'List of reports based on the given filters or all reports if no filters are provided.',
            404: 'Topic not found'
        }
    )
    def list(self, request, *args, **kwargs):
        logger.warning("GetReportViewSet.list was called")
        queryset = self.get_queryset()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        """Filters the queryset based on the query parameters and returns the filtered queryset.

        Only the reports the requesting user may see (publications.visibility, roadmap FA-R75):
        list and detail (``/api/report/<pk>/``, 404 for a hidden report) both use it.

        Available filters:
        - topic: Filter by topic name
        - author_id: Filter by author ID
        - supervisor_id: Filter by supervisor ID
        - q: Filter by searching title and abstract for the query string(s)
        
        Returns:
            queryset: The filtered queryset ordered by year and number in descending order
        """
        queryset = Publication.objects.all()
        
        # Obtain query parameters
        topic = self.request.query_params.get('topic', None)
        author_id = self.request.query_params.get('author_id', None)
        supervisor_id = self.request.query_params.get('supervisor_id', None)
        q = self.request.query_params.get('q', None)

        # Filter the queryset based on the query parameters
        if topic:
            try:
                topic_obj = Topic.objects.get(topic=topic)
            except Topic.DoesNotExist:
                raise NotFound('Topic not found')
            queryset = queryset.filter(publication_topics=topic_obj)
        
        if author_id:
            queryset = queryset.filter(authors__id=author_id)
        
        if supervisor_id:
            queryset = queryset.filter(supervisors__id=supervisor_id)

        if q:
            try:
                queryset = queryset.filter(get_query(q, ['title', 'abstract', 'publication_keywords__keyword']))
            except Exception as e:
                logger.error(f"Error while filtering queryset: {e}")
                raise ValidationError({'q': 'Invalid search query.'})
            
        # ========== Order the queryset ==========
        # keep only unique entries
        queryset = queryset.distinct()

        # Create a custom ordering field
        queryset = queryset.annotate(
            custom_order=Case(
                When(number__regex=r'^9[0-9]-', then=1),
                default=2,
                output_field=IntegerField(),
            )
        ).order_by('-custom_order', '-number')


        # ============ Only the reports the user may see ============
        # One rule for all publications in the API: publications.visibility.
        return visible_publications(queryset, self.request.user)




 



class GetFeatureViewSet(ListModelMixin, RetrieveModelMixin, viewsets.GenericViewSet):

    serializer_class = FeatureSerializer


    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='publication_id',
                in_=openapi.IN_QUERY,
                description="Filter publications by publication ID.",
                type=openapi.TYPE_INTEGER,
            )
        ],
        responses={
            200: 'List of features based on the given filters or all features if no filters are provided.',
            404: 'Ressource not found'
        }
    )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    
    def get_queryset(self):
        queryset = Feature.objects.all()
    
        # Obtain query parameters
        publication_id = self.request.query_params.get('publication_id', None)

        # Filter the queryset based on the query parameters
        if publication_id:
            # Features of that publication if the user may see it; a hidden publication
            # gives an empty result.
            visible = visible_publications(Publication.objects.filter(id=publication_id),
                                           self.request.user)
            queryset = queryset.filter(publications__in=visible)

        # Only features the user may see (publications.visibility, same rule as the report
        # API): no publication, or at least one visible one. Distinct rows; the detail of a
        # hidden feature is 404.
        return visible_features(queryset, self.request.user).distinct()



class GetPersonViewSet(ListModelMixin, RetrieveModelMixin, viewsets.GenericViewSet):

    serializer_class = PersonSerializer


    @swagger_auto_schema(
        manual_parameters=[

        ],
        responses={
            200: 'List of persons and associated reports.',
            404: 'Ressource not found'
        }
    )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    
    def get_queryset(self):
        queryset = Person.objects.all().order_by('last', 'first')
    
        return queryset


# class GetNextReportNumberView(View):
#     """
#     AJAX view to get the next available report number for a given year.
#     Used for auto-updating the report number field when year changes.
#     """
    
#     def get(self, request):
#         year = request.GET.get('year')
        
#         if not year:
#             return JsonResponse({'error': 'Year parameter is required'}, status=400)
        
#         try:
#             year = int(year)
#             next_number = generate_next_report_number(year)
#             return JsonResponse({'number': next_number})
#         except (ValueError, TypeError):
#             return JsonResponse({'error': 'Invalid year format'}, status=400)
#         except Exception as e:
#             return JsonResponse({'error': f'Error generating report number: {str(e)}'}, status=500)

class GetNextReportNumberView(APIView):
    """
    API endpoint to get the next available report number for a given year.
    Used for auto-updating the report number field when year changes.
    """

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='year',
                in_=openapi.IN_QUERY,
                description="Year for which to get the next available report number.",
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
        ],
        responses={
            200: openapi.Response('Next available report number', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'number': openapi.Schema(type=openapi.TYPE_STRING)
                }
            )),
            400: 'Year parameter is required or invalid format',
            500: 'Error generating report number'
        }
    )
    def get(self, request):
        year = request.GET.get('year')
        if not year:
            return Response({'error': 'Year parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            year = int(year)
            next_number = utils_models.generate_next_report_number(year)
            return Response({'number': next_number}, status=status.HTTP_200_OK)
        except (ValueError, TypeError):
            return Response({'error': 'Invalid year format'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Error generating report number: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)