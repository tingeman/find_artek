"""Merge duplicate persons into one (plan release-2026-7 T8, roadmap FA-R58 merge part).

``plan_merge(kept, merged_list)`` describes what a merge would change and writes nothing;
``merge_persons(kept, merged_list, user, expected_plan)`` does it, in one transaction.

What a merge does, for each merged person (in pk order):

- Its links (``Authorship``, ``Supervisorship``, ``Editorship``; person_links.LINK_MODELS)
  move to the kept person (``.update(person=kept)``: the link row keeps its pk and its
  ``author_id``/``supervisor_id``/``editor_id``, so the order of the persons on each report
  stays as it was).
- A link to a report on which the kept person already has the same role (or gets it from an
  earlier link in this merge) is dropped (deleted), so no report lists a person twice in a role.
- Empty identity fields of the kept person (``FILL_FIELDS``) are filled from the merged person.
  When both hold different values, the kept value stays and the conflict is reported. The name
  fields, the ``*_relaxed`` fields, ``quality``, the hidden contact fields
  (person_privacy.CONTACT_FIELDS, to be dropped by FA-R72) and the BaseModel fields are never
  touched.
- The merged person is deleted.

Afterwards the match flags of all links of the kept person are cleared
(person_links.clear_markers) and one INFO line goes to the logger ``publications.persons``
(user pk, kept pk, deleted pks, links moved and dropped per role, names of the filled fields;
no field values and no names).

Relations to ``Person`` (``Person._meta.related_objects``, checked when the plan is made): the
three link models above (FK ``person``, on_delete CASCADE) and the M2M fields
``Publication.authors``/``supervisors``/``editors``, whose through tables are those link models.
Nothing else points to Person (``created_by``/``modified_by`` are FKs *from* Person to User).
A relation that isn't handled here and has rows for a merged person is a blocker: the plan
reports it and ``merge_persons`` refuses, so a relation added later can't be lost by CASCADE.

Stale confirmation: ``MergePlan.fingerprint`` is a SHA-256 of everything the plan was made
from (the pks and the link pks and reports per role of both sides, the name and identity field
values of both sides). The confirmation page posts it back; ``merge_persons`` makes the plan
again inside its transaction, with the persons locked, and refuses when the fingerprint
differs.
"""
import hashlib
import json
import logging
from dataclasses import dataclass, field

from django.db import transaction

from publications.models import Person
from publications.person_links import LINK_MODELS, clear_markers

logger = logging.getLogger('publications.persons')

# Identity fields of Person that a merge fills when the kept person's value is empty.
FILL_FIELDS = (
    'id_number', 'initials', 'email', 'position', 'pre_titulation', 'post_titulation',
    'institution', 'department', 'note',
)

# Part of the fingerprint, never changed by a merge.
NAME_FIELDS = ('first', 'middle', 'prelast', 'last', 'lineage')

# Relations to Person that the merge moves: (model, FK field name).
HANDLED_RELATIONS = {(model, 'person') for _, model in LINK_MODELS}


class MergeError(Exception):
    """A merge that is refused; the message is shown to the editor. Nothing was changed."""


class StaleMergeError(MergeError):
    """The data changed between the confirmation page and the merge."""


@dataclass
class MergedPersonPlan:
    """What a merge does with one merged person."""
    person: Person
    # role -> list of links (with ``publication`` loaded) that move to the kept person
    moved: dict = field(default_factory=dict)
    # role -> list of links that are deleted as duplicates
    dropped: dict = field(default_factory=dict)
    # field name -> value copied to the kept person
    filled: dict = field(default_factory=dict)
    # (field name, kept value, merged value): the kept value stays
    conflicts: list = field(default_factory=list)

    def moved_count(self):
        return sum(len(links) for links in self.moved.values())

    def dropped_count(self):
        return sum(len(links) for links in self.dropped.values())


@dataclass
class MergePlan:
    kept: Person
    merged: list            # MergedPersonPlan, in pk order
    blockers: list          # messages; a plan with blockers can't be carried out
    fingerprint: str

    def moved_counts(self):
        """role -> number of links moved, over all merged persons (every role listed)."""
        return {role: sum(len(m.moved.get(role, ())) for m in self.merged)
                for role, _ in LINK_MODELS}

    def dropped_counts(self):
        return {role: sum(len(m.dropped.get(role, ())) for m in self.merged)
                for role, _ in LINK_MODELS}

    def filled_fields(self):
        """Names of the fields filled, in FILL_FIELDS order."""
        filled = {name for m in self.merged for name in m.filled}
        return [name for name in FILL_FIELDS if name in filled]


def person_relations():
    """(model, field name, related name) of every relation pointing to Person, as Django
    knows it: reverse FKs and one-to-ones (the FK on the other model) and M2M fields (as
    their through model's FK to Person)."""
    found = []
    for rel in Person._meta.related_objects:
        if rel.many_to_many:
            through = rel.through
            for f in through._meta.get_fields():
                if getattr(f, 'remote_field', None) and f.many_to_one and \
                        f.remote_field.model is Person:
                    found.append((through, f.name, rel.get_accessor_name()))
        else:
            found.append((rel.related_model, rel.field.name, rel.get_accessor_name()))
    # An M2M through a link model and the link model's own FK are the same relation.
    unique = {}
    for model, name, accessor in found:
        unique.setdefault((model, name), accessor)
    return [(model, name, accessor) for (model, name), accessor in unique.items()]


def unhandled_relations():
    """The relations of ``person_relations`` that a merge doesn't move."""
    return [(model, name, accessor) for model, name, accessor in person_relations()
            if (model, name) not in HANDLED_RELATIONS]


def _check_input(kept, merged_list):
    if kept is None or kept.pk is None:
        raise MergeError("The person to keep doesn't exist.")
    merged_list = list(merged_list)
    if not merged_list:
        raise MergeError("No persons were chosen to merge.")
    pks = {p.pk for p in merged_list}
    if kept.pk in pks:
        raise MergeError("A person can't be merged into itself.")
    return sorted(pks)


def _load(kept_pk, merged_pks, lock=False):
    """The kept person and the merged persons fresh from the database (locked with ``lock``).
    MergeError when one of them no longer exists."""
    query = Person.objects.select_for_update() if lock else Person.objects.all()
    persons = {p.pk: p for p in query.filter(pk__in=[kept_pk, *merged_pks]).order_by('pk')}
    if kept_pk not in persons:
        raise MergeError(f"The person to keep (pk {kept_pk}) no longer exists.")
    missing = [pk for pk in merged_pks if pk not in persons]
    if missing:
        raise MergeError(
            "Person(s) with pk " + ', '.join(str(pk) for pk in missing) + " no longer exist.")
    return persons[kept_pk], [persons[pk] for pk in merged_pks]


def _links(model, person_pks):
    """person pk -> links of ``model`` (publication loaded), in pk order."""
    result = {pk: [] for pk in person_pks}
    for link in (model.objects.filter(person_id__in=person_pks)
                 .select_related('publication').order_by('pk')):
        result[link.person_id].append(link)
    return result


def _empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _build(kept, merged_persons):
    """The MergePlan for loaded persons."""
    pks = [kept.pk] + [p.pk for p in merged_persons]
    plans = [MergedPersonPlan(person=p) for p in merged_persons]
    digest = {'kept': kept.pk, 'persons': {}, 'links': {}}
    for p in [kept, *merged_persons]:
        digest['persons'][p.pk] = {name: getattr(p, name) or ''
                                   for name in NAME_FIELDS + FILL_FIELDS}

    for role, model in LINK_MODELS:
        links = _links(model, pks)
        digest['links'][role] = {pk: [(link.pk, link.publication_id) for link in links[pk]]
                                 for pk in pks}
        taken = {link.publication_id for link in links[kept.pk]}
        for plan in plans:
            moved, dropped = [], []
            for link in links[plan.person.pk]:
                if link.publication_id in taken:
                    dropped.append(link)
                else:
                    moved.append(link)
                    taken.add(link.publication_id)
            plan.moved[role] = moved
            plan.dropped[role] = dropped

    values = {name: getattr(kept, name) for name in FILL_FIELDS}
    for plan in plans:
        for name in FILL_FIELDS:
            theirs = getattr(plan.person, name)
            if _empty(theirs):
                continue
            if _empty(values[name]):
                values[name] = theirs
                plan.filled[name] = theirs
            elif str(values[name]).strip() != str(theirs).strip():
                plan.conflicts.append((name, values[name], theirs))

    blockers = []
    for model, name, accessor in unhandled_relations():
        count = model._base_manager.filter(**{f'{name}__in': pks[1:]}).count()
        if count:
            blockers.append(
                f"{count} row(s) of {model._meta.label} ({accessor}) point to a person to be "
                f"merged; the merge can't move them.")

    raw = json.dumps(digest, sort_keys=True, default=str)
    fingerprint = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return MergePlan(kept=kept, merged=plans, blockers=blockers, fingerprint=fingerprint)


def plan_merge(kept, merged_list):
    """What merging the persons ``merged_list`` into ``kept`` would change (a MergePlan).
    Writes nothing. MergeError for an empty list, a merge into itself or a person that
    doesn't exist (any more)."""
    merged_pks = _check_input(kept, merged_list)
    kept, merged_persons = _load(kept.pk, merged_pks)
    return _build(kept, merged_persons)


def merge_persons(kept, merged_list, user, expected_plan=None):
    """Merge the persons ``merged_list`` into ``kept`` (see the module docstring), in one
    transaction, and return the MergePlan that was carried out.

    ``expected_plan``: the fingerprint (or the MergePlan) the editor confirmed; when the data
    changed since, StaleMergeError and nothing changes. MergeError (nothing changed) for the
    cases of ``plan_merge`` and for a plan with blockers."""
    merged_pks = _check_input(kept, merged_list)
    expected = getattr(expected_plan, 'fingerprint', expected_plan)
    with transaction.atomic():
        kept, merged_persons = _load(kept.pk, merged_pks, lock=True)
        plan = _build(kept, merged_persons)
        if expected is not None and expected != plan.fingerprint:
            raise StaleMergeError(
                "The persons or their reports changed after the confirmation page was shown. "
                "Nothing was merged; please check the changes again.")
        if plan.blockers:
            raise MergeError("The merge can't be done: " + ' '.join(plan.blockers))

        for role, model in LINK_MODELS:
            for item in plan.merged:
                moved = [link.pk for link in item.moved[role]]
                dropped = [link.pk for link in item.dropped[role]]
                if moved:
                    count = model.objects.filter(pk__in=moved, person=item.person).update(
                        person=kept)
                    if count != len(moved):
                        raise StaleMergeError("A link changed during the merge; nothing was merged.")
                if dropped:
                    model.objects.filter(pk__in=dropped, person=item.person).delete()
            left = model.objects.filter(person__in=merged_persons).count()
            if left:
                raise StaleMergeError("A link changed during the merge; nothing was merged.")

        filled = {}
        for item in plan.merged:
            filled.update(item.filled)
        for name, value in filled.items():
            setattr(kept, name, value)
        kept.modified_by = user
        kept.save(update_fields=[*filled, 'modified_by', 'modified_date'])

        clear_markers(kept)
        Person.objects.filter(pk__in=merged_pks).delete()

        logger.info(
            "merge persons: user=%s kept=%s deleted=%s moved=%s dropped=%s filled=%s",
            getattr(user, 'pk', None), kept.pk, merged_pks,
            ','.join(f'{role}:{n}' for role, n in plan.moved_counts().items()),
            ','.join(f'{role}:{n}' for role, n in plan.dropped_counts().items()),
            ','.join(plan.filled_fields()) or '-')
    return plan
