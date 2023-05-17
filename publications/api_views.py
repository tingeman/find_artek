# api_views.py
from django.http import JsonResponse
from django.core import serializers
from publications.models import Publication, Topic, Feature


def feature_geographic_location_data(request):

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


