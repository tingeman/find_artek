from rest_framework import serializers
from publications.models import Publication, Feature, Person



class PublicationSerializer(serializers.ModelSerializer):

    feature_count = serializers.SerializerMethodField()  
    file = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    authors = serializers.SerializerMethodField()
    link_to_pdf_associated_with_this_publication = serializers.SerializerMethodField()

    class Meta:
        model = Publication
        fields = ['link_to_pdf_associated_with_this_publication', 'feature_count', 'id', 'number' , 'title', 'authors', 'file', 'type', 'feature_count']

    def get_feature_count(self, obj):
        return obj.feature_set.count()

    def get_file(self, obj):
        return obj.file.filename() if obj.file else None

    def get_authors(self, obj):
        return [{'pk': author.pk, 'first': author.first, 'last': author.last} for author in obj.authors.all()]

    def get_link_to_pdf_associated_with_this_publication(self, obj):
        return obj.file.file.url if obj.file else None

    def get_type(self, obj):
        return obj.type.type if obj.type else None


class FeatureSerializer(serializers.ModelSerializer):
    
    points = serializers.SerializerMethodField()
    lines  = serializers.SerializerMethodField()
    polys  = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    feature_pk = serializers.SerializerMethodField()
    related_publications = serializers.SerializerMethodField()

    
    class Meta:
        model = Feature
        fields = ['points', 'lines', 'polys', 'name', 'type', 'date', 'feature_pk', 'related_publications']

    def get_points(self, obj):
        return obj.points.geojson if obj.points else None
    
    def get_lines(self, obj):
        return obj.lines.geojson if obj.lines else None
    
    def get_polys(self, obj):
        return obj.polys.geojson if obj.polys else None
    
    def get_name(self, obj):
        return obj.name if obj.name else None
    
    def get_type(self, obj):
        return obj.type if obj.type else None

    def get_date(self, obj):
        return obj.date.strftime('%Y-%m-%d')

    def get_feature_pk(self, obj):
        return obj.pk
    
    def get_related_publications(self, obj):
        return [{'id': publication.pk, 'number': publication.number, 'title': publication.title} for publication in obj.publications.all()]
    


class PersonSerializer(serializers.ModelSerializer):

    id = serializers.SerializerMethodField()

    class Meta: 
        model = Person
        fields = ['id', 'first', 'last']


    def get_id(self, obj):
        return obj.pk
    