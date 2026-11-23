"""A report that still has features is never deleted (plan "features" T13, owner 2026-11-23).

Deleting such a report would leave its features in the database without any report, still
on the map. Every place that deletes reports uses these helpers: the report's delete page
(views.DeleteReportView), the bulk delete (views.BulkDeletePublicationsView) and the Django
admin (admin.PublicationAdmin).
"""
from django.db.models import Count

from publications.models import Feature


def report_features(publication):
    """The features linked to ``publication``, sorted by name."""
    return Feature.objects.filter(publications=publication).distinct().order_by('name', 'pk')


def has_features(publication):
    """True if ``publication`` still has features (it may not be deleted)."""
    return Feature.objects.filter(publications=publication).exists()


def with_feature_count(queryset):
    """``queryset`` (Publications) annotated with ``feature_count``."""
    return queryset.annotate(feature_count=Count('feature', distinct=True))


def split_by_features(queryset):
    """(deletable, blocked): the publications of ``queryset`` without and with features, as
    lists annotated with ``feature_count``, in the queryset's order."""
    deletable, blocked = [], []
    for publication in with_feature_count(queryset):
        (blocked if publication.feature_count else deletable).append(publication)
    return deletable, blocked


def report_label(publication):
    """Short name of a report in messages: its number, else its pk."""
    return str(publication.number or publication.pk)
