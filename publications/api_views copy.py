# api_views.py
from django.http import HttpResponse, JsonResponse
from django.core import serializers
from publications.models import Publication, Topic, Feature, Person


def get_feature_geographic_location_data(request):

    # if get request with publication_id, return all features associated with that publication
    publication_id = request.GET.get('publication_id', None)
    if publication_id is not None:
        publication = Publication.objects.get(pk=publication_id)
        features = Feature.objects.filter(publications=publication)
    else:
        features = Feature.objects.all()

    feature_data = []
    for feature in features:
        related_publications = feature.get_related_publications()

        related_publications_data = []

        for publication in related_publications:
            related_publications_data.append({
                'pk': publication.pk,
                'number': publication.number,
            })

        feature_data.append({
            'points': feature.points.geojson if feature.points else "",
            'lines': feature.lines.geojson if feature.lines else "",
            'polys': feature.polys.geojson if feature.polys else "",
            'name': feature.name if feature.name else "",
            'type': feature.type if feature.type else "",
            'date': feature.date.strftime('%Y-%m-%d') if feature.date else "",
            'feature_pk': feature.pk,
            'related_publications'  : related_publications_data,
            })

    
    return JsonResponse(feature_data, safe=False)




# Create the API view for reports
def get_reports_table_data(request):
    topic = request.GET.get('topic')
    person_id = request.GET.get('person_id')

    # If both topic and person_id are specified, return an error
    # We can only filter by either topic or person, not both
    if topic and person_id:
        return JsonResponse({'error': 'can only specify one of topic or person'}, status=400)

    publications = Publication.objects.filter(verified=True)

    # Try to filter by person_id if it's specified
    if person_id:
        try:
            person = Person.objects.get(pk=person_id)
            publications = person.publication_supervisor.all()
        except Person.DoesNotExist:
            # Return an error if the person_id doesn't correspond to any person
            return JsonResponse({'error': 'invalid person'}, status=400)
    # If person_id wasn't specified or was invalid, try to filter by topic if it's specified
    elif topic:
        try:
            topic_obj = Topic.objects.get(topic=topic)
            publications = publications.filter(publication_topics=topic_obj)
        except Topic.DoesNotExist:
            # Return an error if the topic doesn't correspond to any topics
            return JsonResponse({'error': 'invalid topic'}, status=400)

    # Apply some ordering and extra selection to the publications query
    publications = publications.extra(
        select={'year': 'CAST(year AS INTEGER)'}
    ).extra(
        order_by=['-year', '-number']
    )

    # Manually creating list of dicts for each publication with only specified fields
    data = []
    for publication in publications:
        authors_list = [{'first': author.first, 'last': author.last} for author in publication.authors.all()]

        data.append({
            'id': publication.pk,  # This is the primary key of the publication
            'number': publication.number,
            'title': publication.title,
            'authors': authors_list,
            'file': publication.file.filename() if publication.file else None,  # Make sure to handle case when file is None
            'link_to_pdf_associated_with_this_publication': publication.file.file.url if publication.file else None,  # Make sure to handle case when file is None
            'type': publication.type.type if publication.type else None,  # Handle case when type is None
            'feature_count': publication.feature_set.count(),
        })

    return JsonResponse(data, safe=False)


    # Manually creating list of dicts for each publication with only specified fields
    data = []
    for publication in publications:

        authors_list = [{'first': author.first, 'last': author.last} for author in publication.authors.all()]

        data.append({
            'id': publication.pk,  # This is the primary key of the publication
            'number': publication.number,
            'title': publication.title,
            'authors': authors_list,
            'file': publication.file.filename() if publication.file else None,  # Make sure to handle case when file is None
            'link_to_pdf_associated_with_this_publication': publication.file.file.url if publication.file else None,  # Make sure to handle case when file is None
            'type': publication.type.type if publication.type else None,  # Handle case when type is None
            'feature_count': publication.feature_set.count(),
        })

    return JsonResponse(data, safe=False)















# Create the API view for persons
def get_persons_table_data(request):
    persons = Person.objects.all()

    # Manually creating list of dicts for each person with only specified fields
    data = []
    for person in persons:
        data.append({
            'id': person.pk,
            'first': person.first,
            'last': person.last,
        })

    return JsonResponse(data, safe=False)
# Finish the feature view
# Finish the person view
# Fix the links in the report template