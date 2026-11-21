from django.db.models import Count, OuterRef, Prefetch, Subquery
from django.db.models.functions import Coalesce
from rest_framework import serializers
from publications.models import Authorship, Publication, Feature, Person
from publications import person_privacy
from publications.permissions import MERGE_PERSON, user_may
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

    # Attributes set by prepare_queryset (roadmap FA-R97: one query per relation instead of
    # one per report). Without them (a Publication from elsewhere) the fields query as before.
    FEATURE_COUNT = 'api_feature_count'
    AUTHORSHIPS = 'api_authorships'

    @classmethod
    def prepare_queryset(cls, queryset):
        """``queryset`` (Publications) with what the fields need loaded in a fixed number of
        queries: type and file prefetched, the number of features as an annotation (a
        subquery), the authorships (with their persons) prefetched in the order of their rows,
        which is the order ``authors.all()`` returns them in on MariaDB.

        Doesn't change which rows or their order. Type and file are prefetched, not joined
        (``select_related``): a join changes MariaDB's plan, and with it the order of reports
        with the same number, which the ordering doesn't decide (seen on the dev copy)."""
        feature_links = (Feature.publications.through.objects
                         .filter(publication_id=OuterRef('pk'))
                         .order_by().values('publication_id')
                         .annotate(n=Count('pk')).values('n'))
        return (queryset
                .annotate(**{cls.FEATURE_COUNT: Coalesce(Subquery(feature_links), 0)})
                .prefetch_related('type', 'file', Prefetch(
                    'authorship_set',
                    queryset=Authorship.objects.select_related('person').order_by('pk'),
                    to_attr=cls.AUTHORSHIPS)))

    def get_feature_count(self, obj):
        count = getattr(obj, self.FEATURE_COUNT, None)
        return obj.feature_set.count() if count is None else count

    def get_file(self, obj):
        return obj.file.filename() if obj.file else None

    def _shows_person_markers(self):
        """True if the request user has merge_person (FA-R66): only then do the author dicts
        carry the duplicate markers. Decided once per serializer (and so once per list)."""
        if not hasattr(self, '_person_markers'):
            self._person_markers = user_may(_request_user(self), MERGE_PERSON)
        return self._person_markers

    def get_authors(self, obj):
        """``{pk, first, last}`` per author. For users with merge_person only, a marked link
        (person_links) adds ``match``: ``"exact"`` (exact_match) or ``"relaxed"``
        (relaxed_match or multiple_match alone), and ``"multiple": true`` with multiple_match;
        for everyone else the dicts are exactly as before."""
        authorships = getattr(obj, self.AUTHORSHIPS, None)
        if authorships is None:
            authorships = obj.authorship_set.select_related('person').order_by('pk')
        markers = self._shows_person_markers()
        authors = []
        for authorship in authorships:
            author = authorship.person
            item = {'pk': author.pk, 'first': author.first, 'last': author.last}
            if markers:
                if authorship.exact_match:
                    item['match'] = 'exact'
                elif authorship.relaxed_match or authorship.multiple_match:
                    item['match'] = 'relaxed'
                if authorship.multiple_match:
                    item['multiple'] = True
            authors.append(item)
        return authors

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
    
    # Set by prepare_queryset: the publications of the feature the user may see.
    VISIBLE_PUBLICATIONS = 'api_visible_publications'

    @classmethod
    def prepare_queryset(cls, queryset, user):
        """``queryset`` (Features) with the publications ``user`` may see prefetched in one
        query (roadmap FA-R97), filtered by publications.visibility as the field does without
        it, and ordered by id, the order the database returns them in for one feature.
        Doesn't change which features are listed or their order."""
        publications = visible_publications(
            Publication.objects.only('pk', 'number', 'title').order_by('pk'), user)
        return queryset.prefetch_related(Prefetch(
            'publications', queryset=publications, to_attr=cls.VISIBLE_PUBLICATIONS))

    def get_related_publications(self, obj):
        publications = getattr(obj, self.VISIBLE_PUBLICATIONS, None)
        if publications is None:
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

    