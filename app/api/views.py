# from rest_framework.response import Response
# from rest_framework.decorators import api_view
# from .serializers import PublicationSerializer
# from publications.models import Publication, Topic


# @api_view(['GET'])
# def getData(request):
#     topic_param = request.query_params.get('topic', None)

#     publications = Publication.objects.all()

#     # Filter the publications if a topic parameter is provided
#     if topic_param is not None:
#         topic = Topic.objects.get(topic=topic_param)  # Assume topics can be retrieved by their name
#         publications = publications.filter(publication_topics=topic)

#     serializer = PublicationSerializer(publications, many=True)
    
#     return Response(serializer.data)


from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .serializers import PublicationSerializer, FeatureSerializer, PersonSerializer
from publications.models import Publication, Topic, Feature, Person
import http.client
import json

topic_param = openapi.Parameter(
    'topic', 
    in_=openapi.IN_QUERY, 
    description='Topic to filter publications by', 
    type=openapi.TYPE_STRING
)

@swagger_auto_schema(manual_parameters=[topic_param], method='get', responses={200: PublicationSerializer(many=True)})
@api_view(['GET'])
def get_reports(request):
    topic_param = request.query_params.get('topic', None)

    publications = Publication.objects.all()

    # Filter the publications if a topic parameter is provided
    if topic_param is not None:
        topic = Topic.objects.get(topic=topic_param)  # Assume topics can be retrieved by their name
        publications = publications.filter(publication_topics=topic)


    # Apply some ordering and extra selection to the publications query
    publications = publications.extra(
        select={'year': 'CAST(year AS INTEGER)'}
    ).extra(
        order_by=['-year', '-number']
    )


    serializer = PublicationSerializer(publications, many=True)
    
    return Response(serializer.data)


@swagger_auto_schema(method='get', responses={200: PublicationSerializer(many=True)})
@api_view(['GET'])
def get_feature_data(request):

    features = Feature.objects.all()

    serializer = FeatureSerializer(features, many=True)

    return Response(serializer.data)



@api_view(['GET'])
def get_persons(request):
    persons = Person.objects.all()

    serializer = PersonSerializer(persons, many=True)

    return Response(serializer.data)


@api_view(['GET'])
def get_person(request, pk):
    person = Person.objects.get(pk=pk)

    serializer = PersonSerializer(person, many=False)

    return Response(serializer.data)



@api_view(['GET'])
def search_dtu(request, full_name):

    conn = http.client.HTTPSConnection("dtu.dk")
    payload = json.dumps({
    "Pagination": {
        "Number": 1,
        "Size": 1
    },
    "Constraint": {
        "Text": f"{full_name}",
        "ListMembership": None,
        "Types": [
        "Employee"
        ],
        "OrganizationUnitIds": [],
        "SearchTextType": 1,
        "ShowPrimaryOnly": True,
        "PersonIds": None
    },
    "Sort": {
        "Direction": "Ascending",
        "SortOn": "Surname",
        "LanguageCode": "Da"
    },
    "SitecoreContextUri": {
        "Database": "web",
        "Language": "da",
        "Path": "{FE04B7F2-2484-4816-8CCF-08D1DF3DD275}",
        "Site": "website"
    }
    })
    headers = {
    'Content-Type': 'application/json'
    }
    conn.request("POST", "/api/v1/person/search", payload, headers)
    res = conn.getresponse()
    data = res.read()

    #  serializer = DTUSearchSerializer(data, many=True)

    # convert data.decode("utf-8") to json

    data = json.loads(data.decode("utf-8"))


    # print(data.decode("utf-8"))
    return Response(data)