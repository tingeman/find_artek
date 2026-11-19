from rest_framework import serializers
from publications.models import Publication, Feature, Person
from publications import person_privacy
from publications.visibility import visible_publications


def _request_user(serializer):
    """The user of the request in the serializer context (the viewsets pass it), or None
    (treated as anonymous) when the serializer is used without a request."""
    request = serializer.context.get('request')
    return getattr(request, 'user', None)


def _visible_for_request(serializer, publications):
    """Only the publications the requesting user may see (publications.visibility, roadmap
    FA-R75; same rule as the report API). Without a request in the serializer context the
    user counts as anonymous."""
    return visible_publications(publications, _request_user(serializer))



class PublicationSerializer(serializers.ModelSerializer):

    feature_count = serializers.SerializerMethodField()  
    file = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    authors = serializers.SerializerMethodField()
    link_to_pdf_associated_with_this_publication = serializers.SerializerMethodField()

    class Meta:
        model = Publication
        fields = ['link_to_pdf_associated_with_this_publication', 'feature_count', 'id', 'number' , 'title', 'authors', 'file', 'type', 'feature_count', 'confidential']
        # Only reports the user may see are serialized (publications.visibility); the flag
        # tells the client which of them are confidential (FA-R75).
        read_only_fields = ['confidential']

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
        publications = _visible_for_request(self, obj.publications.all())
        return [{'id': publication.pk, 'number': publication.number, 'title': publication.title} for publication in publications]
    


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
        fields = ['id', 'id_number', 'fullname', 'first', 'middle', 'prelast', 'last', 'lineage', 'position', 'email', 'authorships', 'supervisorships']

    def get_id_number(self, obj):
        # Only logged-in users (person_privacy, plan "registration" T13)
        return person_privacy.visible_id_number(_request_user(self), obj)
    
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
        # Student e-mails only for logged-in users (person_privacy)
        return person_privacy.visible_email(_request_user(self), obj)
    
    def get_authorships(self, obj):
        # The model Authorship defines a many-to-many relationship between Person and Publication
        # Find all publications where this person is an author
        publications = _visible_for_request(self, Publication.objects.filter(authorship__person=obj))
        return [{'id': publication.pk, 'number': publication.number, 'title': publication.title} for publication in publications]

    def get_supervisorships(self, obj):
        # The model Supervisorship defines a many-to-many relationship between Person and Publication
        # Find all publications where this person is a supervisor
        publications = _visible_for_request(self, Publication.objects.filter(supervisorship__person=obj))
        return [{'id': publication.pk, 'number': publication.number, 'title': publication.title} for publication in publications]

    