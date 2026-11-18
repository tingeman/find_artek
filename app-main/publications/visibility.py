"""Which publications may be listed to whom.

The single rule for every place that lists publications through the API: the report list
(api.views.GetReportViewSet) and the publications of a person (api.serializers.PersonSerializer).
Keep them in sync by using this function, not a copy of the filters.

- Publications whose ``comment`` contains "confidential" (any case) are never listed.
- Unverified publications (``verified=False``) are listed only to logged-in users.

This decides what is *listed*. Who may open a report page or its files is decided elsewhere
(roadmap FA-R10, FA-R30).
"""


def visible_publications(queryset, user=None):
    """Return ``queryset`` (Publications) without the entries ``user`` may not see listed.

    ``user`` is a Django user or None; None and anonymous users are treated the same.
    """
    queryset = queryset.exclude(comment__icontains='confidential')
    if user is None or not user.is_authenticated:
        queryset = queryset.filter(verified=True)
    return queryset
