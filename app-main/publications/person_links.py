"""Duplicate markers on the links of a person to reports (plan release-2026-7 T7, roadmap FA-R66).

A link (``Authorship``, ``Supervisorship``, ``Editorship``; models.Personship) is *marked* when
one of its match flags is set: a new person was created for the name although matching persons
existed (Excel import, register_from_file; "create new person" in the report form,
workflows/person.match_flags). ``exact_match``: persons with this exact name existed;
``relaxed_match``: persons with a similar name (initial and last name); ``multiple_match``:
more than one of them.

Only users with ``merge_person`` (permissions.MERGE_PERSON) see the markers. Confirming a
person (``clear_markers``) clears the flags of all its links.
"""
from django.db import transaction
from django.db.models import Q

from publications.models import Authorship, Editorship, Supervisorship

# Role name (as shown in the marker's tooltip) and link model, in the order the person page
# lists them.
LINK_MODELS = (
    ('author', Authorship),
    ('supervisor', Supervisorship),
    ('editor', Editorship),
)

MARKED = Q(exact_match=True) | Q(relaxed_match=True) | Q(multiple_match=True)

CLEARED = {'exact_match': False, 'relaxed_match': False, 'multiple_match': False,
           'match_string': ''}


def is_marked(link):
    return bool(link.exact_match or link.relaxed_match or link.multiple_match)


def marked_links(person):
    """(role, link) for every marked link of ``person``, with the link's publication loaded,
    authors first, then supervisors, then editors, each by report number. One query per role."""
    result = []
    for role, model in LINK_MODELS:
        links = (model.objects.filter(MARKED, person=person)
                 .select_related('publication').order_by('publication__number', 'pk'))
        result.extend((role, link) for link in links)
    return result


def clear_markers(person):
    """Clears the match flags (and ``match_string``) of every link of ``person``, and of no
    other person, in one transaction. Returns the number of links that were marked."""
    with transaction.atomic():
        marked = 0
        for _, model in LINK_MODELS:
            links = model.objects.filter(person=person)
            marked += links.filter(MARKED).count()
            links.update(**CLEARED)
        return marked
