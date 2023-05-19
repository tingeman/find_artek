# api_views.py
from django.http import HttpResponse, JsonResponse
from django.core import serializers
from publications.models import Publication, Topic, Feature


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

    # If topic is specified, filter by topic, else get all publications
    if topic:
        try:
            topic_obj = Topic.objects.get(topic=topic)
            publications = Publication.objects.filter(
                publication_topics=topic_obj,
                verified=True
            )
        except Topic.DoesNotExist:
            return JsonResponse({'error': 'invalid topic'}, status=400)
    else:
        publications = Publication.objects.filter(verified=True)
        
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















# Create the API view for persons
def get_persons_data(request):
    pass

# Finish the feature view
# Finish the person view
# Fix the links in the report template