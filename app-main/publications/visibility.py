"""Who may see which publications and features (roadmap FA-R75, plan PLAN_confidential T2).

The single rule for every place that lists or shows publications or features: the report API
(api.views.GetReportViewSet), the feature API (api.views.GetFeatureViewSet), the publications
of a person and of a feature (api.serializers), and, from T3/T5 on, the pages and the files.
Keep them in sync by using these functions, not a copy of the filters.

A publication is visible to

- anonymous users (or ``user`` None): ``verified=True`` and ``confidential=False``;
- logged-in users: ``confidential=False`` (verified or not), or the user is listed on the
  publication (author, supervisor or editor, see ``listed_on_q``), or the user may see
  everything (``sees_all``: member of ``artek_editor`` or superuser).

A feature is visible when it belongs to no publication, or to at least one visible
publication. A visible feature lists only its visible publications (callers filter its
``publications`` with ``visible_publications``).

Every rule has a queryset form (``visible_publications``, ``visible_features``) for lists and
an object form (``can_view_publication``, ``can_view_feature``) for single objects; the tests
(publications.test_visibility) pin both to the same answer. The ``comment`` no longer matters:
since migration 0004 the field ``Publication.confidential`` decides (T1).
"""
from django.db.models import Q

from publications.models import Publication
from publications.roles import ARTEK_EDITOR

# Attribute on the user instance caching ``sees_all`` (one group query per user instance,
# i.e. per request; like Django's own ``_perm_cache``).
_SEES_ALL_CACHE = '_visibility_sees_all'

PERSON_RELATIONS = ('authors', 'supervisors', 'editors')


def _is_authenticated(user):
    return bool(getattr(user, 'is_authenticated', False))


def _username(user):
    if not _is_authenticated(user):
        return ''
    return user.get_username() or ''


def sees_all(user):
    """True if ``user`` may see every publication and feature: a superuser or a member of the
    group ``artek_editor`` (publications.roles.ARTEK_EDITOR). False for anonymous users and
    None. The answer is cached on the user instance."""
    if not _is_authenticated(user):
        return False
    cached = getattr(user, _SEES_ALL_CACHE, None)
    if cached is None:
        cached = bool(user.is_superuser) or user.groups.filter(name=ARTEK_EDITOR).exists()
        setattr(user, _SEES_ALL_CACHE, cached)
    return cached


def listed_on_q(user, prefix=''):
    """``Q`` matching the publications on which ``user`` is listed as author, supervisor or
    editor: the user name equals the person's ``id_number`` or ``initials``, ignoring case
    (the queryset form of ``Publication.is_own_publication_of`` / ``Person.is_related_to_user``).
    Empty values never match; anonymous users, None and an empty user name match nothing.

    ``prefix`` is put in front of the lookup, so other models can use it through their
    relation, e.g. ``listed_on_q(user, 'publications__')`` on Features. The persons are matched
    in a subquery, so the Q adds no join of its own (only the one ``prefix`` implies).
    """
    username = _username(user)
    if not username:
        return Q(**{f'{prefix}pk__in': []})
    persons = Q()
    for relation in PERSON_RELATIONS:
        persons |= Q(**{f'{relation}__id_number__iexact': username})
        persons |= Q(**{f'{relation}__initials__iexact': username})
    listed = Publication.objects.filter(persons).values('pk')
    return Q(**{f'{prefix}pk__in': listed})


def visible_publications(queryset, user=None):
    """Return ``queryset`` (Publications) without the entries ``user`` may not see.

    ``user`` is a Django user or None; None and anonymous users are treated the same.
    Adds no joins, so it doesn't duplicate rows.
    """
    if sees_all(user):
        return queryset
    if not _is_authenticated(user):
        return queryset.filter(verified=True, confidential=False)
    return queryset.filter(Q(confidential=False) | listed_on_q(user))


def can_view_publication(user, publication):
    """True if ``user`` (a Django user, AnonymousUser or None) may see ``publication``."""
    if sees_all(user):
        return True
    if not _is_authenticated(user):
        return bool(publication.verified) and not publication.confidential
    if not publication.confidential:
        return True
    return publication.is_own_publication_of(user)


def visible_features(queryset, user=None):
    """Return ``queryset`` (Features) with only the features ``user`` may see: those without
    any publication and those with at least one visible publication. Distinct rows."""
    if sees_all(user):
        return queryset
    visible = visible_publications(Publication.objects.all(), user)
    return queryset.filter(
        Q(publications__in=visible) | Q(publications__isnull=True)).distinct()


def can_view_feature(user, feature):
    """True if ``user`` may see ``feature``: it has no publication, or ``user`` may see at
    least one of them."""
    publications = list(feature.publications.all())
    if not publications:
        return True
    return any(can_view_publication(user, publication) for publication in publications)
