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

    id_number = serializers.SerializerMethodField()
    fullname = serializers.SerializerMethodField()
    first = serializers.SerializerMethodField()  
    middle = serializers.SerializerMethodField()
    prelast = serializers.SerializerMethodField()
    last = serializers.SerializerMethodField()
    lineage = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    authorships = serializers.SerializerMethodField()
    supervisorships = serializers.SerializerMethodField()

    class Meta: 
        model = Person
        fields = ['id_number', 'fullname', 'first', 'middle', 'prelast', 'last', 'lineage', 'position', 'email', 'authorships', 'supervisorships']

    def get_id_number(self, obj):
        return obj.id_number if obj.id_number else None
    
    def get_fullname(self, obj):
        return str(obj) if obj else None
    
    def get_first(self, obj):
        return obj.first if obj.first else None
    
    def get_middle(self, obj):
        return obj.middle if obj.middle else None
    
    def get_prelast(self, obj):
        return obj.prelast if obj.prelast else None
    
    def get_last(self, obj):
        return obj.last if obj.last else None
    
    def get_lineage(self, obj):
        return obj.lineage if obj.lineage else None
    
    def get_position(self, obj):
        return obj.position if obj.position else None
    
    def get_email(self, obj):
        return obj.email if obj.email else None
    
    def get_authorships(self, obj):
        # The model Authorship defines a many-to-many relationship between Person and Publication
        # Find all publications where this person is an author
        publications = Publication.objects.filter(authorship__person=obj)
        return [{'id': publication.pk, 'number': publication.number, 'title': publication.title} for publication in publications]

    def get_supervisorships(self, obj):
        # The model Supervisorship defines a many-to-many relationship between Person and Publication
        # Find all publications where this person is a supervisor
        publications = Publication.objects.filter(supervisorship__person=obj)
        return [{'id': publication.pk, 'number': publication.number, 'title': publication.title} for publication in publications]

    