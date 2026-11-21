"""Person tools for editors (plan release-2026-7 T7/T8, roadmap FA-R66, FA-R58 merge part).

All views need ``merge_person`` (permissions.MERGE_PERSON): anonymous users are sent to the
login, other users get 403, a wrong method is 405.

- ``PersonConfirmView``: POST ``person/<pk>/confirm/`` clears the duplicate markers of all
  links of the person (person_links.clear_markers) and goes back to the person page.
- ``PersonMergeView``: GET ``person/<pk>/merge/``: the person to keep, the candidates from the
  person matcher (workflows.person.get_person_matches, confidence >= 0.6) with a checkbox each,
  and an autocomplete field to add any other person. Submits to the confirmation.
- ``PersonMergeConfirmView``: POST ``person/<pk>/merge/confirm/``: what the merge would change
  (person_merge.plan_merge); writes nothing. Its "Merge" button posts the plan's fingerprint.
- ``PersonMergeDoView``: POST ``person/<pk>/merge/do/``: person_merge.merge_persons with that
  fingerprint, then the kept person's page.

Reports are listed as the viewer may see them (visibility.visible_publications); the others
only as a count. Identifiers through person_privacy.
"""
from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django_select2.forms import HeavySelect2MultipleWidget

from publications import person_privacy
from publications.models import Person, Publication
from publications.permissions import MERGE_PERSON, PermissionMixin
from publications.person_links import LINK_MODELS, clear_markers
from publications.person_merge import MergeError, plan_merge, merge_persons
from publications.views import BaseView
from publications.visibility import visible_publications
from publications.workflows.person import get_person_matches

# Matches below this confidence are not offered (as in the report form's disambiguation).
CANDIDATE_CONFIDENCE = 0.6


class PersonConfirmView(PermissionMixin, BaseView):
    """"Confirm person": the person is no duplicate; its links lose their markers."""
    permission = MERGE_PERSON
    http_method_names = ['post']

    def post(self, request, pk):
        person = get_object_or_404(Person, pk=pk)
        cleared = clear_markers(person)
        messages.success(
            request,
            f"Person {person.get_full_name()} confirmed: the duplicate markers of {cleared} "
            f"link(s) were cleared.")
        return redirect('publications:person', pk=person.pk)


class AddPersonsForm(forms.Form):
    """The autocomplete field of the merge page (any person, by name or study number)."""
    others = forms.Field(
        required=False, label="Other persons",
        widget=HeavySelect2MultipleWidget(
            data_view='publications:person-autocomplete',
            attrs={'data-minimum-input-length': 3,
                   'data-placeholder': 'Type a name or study number',
                   'style': 'width: 100%;'}))


def visible_ids(user, publication_ids):
    """The pks of ``publication_ids`` that ``user`` may see."""
    return set(visible_publications(Publication.objects.filter(pk__in=set(publication_ids)),
                                    user).values_list('pk', flat=True))


def link_rows(links, shown_ids):
    """(visible links, number of hidden ones) of ``links`` (publication loaded)."""
    shown = [link for link in links if link.publication_id in shown_ids]
    return shown, len(links) - len(shown)


def person_summaries(user, persons):
    """For each person: its name, identifiers as ``user`` may see them, and per role the
    reports it is linked to (visible ones listed, the others counted)."""
    pks = [p.pk for p in persons]
    links = {}
    for role, model in LINK_MODELS:
        links[role] = {pk: [] for pk in pks}
        for link in (model.objects.filter(person_id__in=pks).select_related('publication')
                     .order_by('publication__number', 'pk')):
            links[role][link.person_id].append(link)
    shown_ids = visible_ids(user, [link.publication_id for per_role in links.values()
                                   for per_person in per_role.values() for link in per_person])
    summaries = []
    for person in persons:
        roles = []
        for role, _ in LINK_MODELS:
            shown, hidden = link_rows(links[role][person.pk], shown_ids)
            roles.append({'role': role, 'links': shown, 'hidden': hidden,
                          'count': len(shown) + hidden})
        summaries.append({
            'person': person,
            'email': person_privacy.visible_email(user, person),
            'id_number': person_privacy.visible_id_number(user, person),
            'roles': roles,
        })
    return summaries


def candidates(person):
    """(Person, confidence) of the persons the matcher finds for ``person``'s name, without
    the person itself, best first."""
    matches = get_person_matches(person.get_full_name()).get('all_matches', [])
    return [(m['person'], m['confidence']) for m in matches
            if m['person'].pk != person.pk and m['confidence'] >= CANDIDATE_CONFIDENCE]


def chosen_pks(request):
    """The pks posted in ``merge`` (checkboxes, hidden fields) and ``others`` (autocomplete),
    without duplicates, in pk order. ValueError for anything that isn't a pk."""
    values = request.POST.getlist('merge') + request.POST.getlist('others')
    return sorted({int(value) for value in values if str(value).strip()})


class _MergeBase(PermissionMixin, BaseView):
    permission = MERGE_PERSON

    def back(self, kept):
        return redirect('publications:person_merge', pk=kept.pk)

    def chosen_persons(self, request):
        """The persons chosen on the merge page; MergeError for bad input or missing persons."""
        try:
            pks = chosen_pks(request)
        except ValueError:
            raise MergeError("The chosen persons could not be read.")
        persons = list(Person.objects.filter(pk__in=pks).order_by('pk'))
        missing = sorted(set(pks) - {p.pk for p in persons})
        if missing:
            raise MergeError("Person(s) with pk " + ', '.join(map(str, missing))
                             + " no longer exist.")
        return persons


class PersonMergeView(_MergeBase):
    """The merge page: the kept person, the candidates, the autocomplete."""
    http_method_names = ['get']
    template_name = 'publications/person_merge.html'

    def get(self, request, pk):
        kept = get_object_or_404(Person, pk=pk)
        found = candidates(kept)
        confidence = {p.pk: c for p, c in found}
        summaries = person_summaries(request.user, [kept] + [p for p, _ in found])
        for summary in summaries[1:]:
            summary['confidence'] = confidence[summary['person'].pk]
        context = self.get_context_data()
        context.update({
            'person': kept,
            'kept': summaries[0],
            'candidates': summaries[1:],
            'show_id_number': person_privacy.can_view_id_number(request.user),
            'form': AddPersonsForm(),
        })
        return render(request, self.template_name, context)


class PersonMergeConfirmView(_MergeBase):
    """The confirmation: what the merge would change. Writes nothing."""
    http_method_names = ['post']
    template_name = 'publications/person_merge_confirm.html'

    def post(self, request, pk):
        kept = get_object_or_404(Person, pk=pk)
        try:
            plan = plan_merge(kept, self.chosen_persons(request))
        except MergeError as error:
            messages.error(request, str(error))
            return self.back(kept)
        all_links = [link for item in plan.merged
                     for per_role in (item.moved, item.dropped)
                     for links in per_role.values() for link in links]
        shown_ids = visible_ids(request.user, [link.publication_id for link in all_links])
        merged = []
        for item in plan.merged:
            roles = []
            for role, _ in LINK_MODELS:
                moved, moved_hidden = link_rows(item.moved[role], shown_ids)
                dropped, dropped_hidden = link_rows(item.dropped[role], shown_ids)
                roles.append({'role': role, 'moved': moved, 'moved_hidden': moved_hidden,
                              'dropped': dropped, 'dropped_hidden': dropped_hidden})
            merged.append({
                'person': item.person,
                'id_number': person_privacy.visible_id_number(request.user, item.person),
                'roles': roles,
                'filled': list(item.filled.items()),
                'conflicts': item.conflicts,
            })
        context = self.get_context_data()
        context.update({
            'person': plan.kept,
            'plan': plan,
            'merged': merged,
            'totals': [(role, moved, plan.dropped_counts()[role])
                       for role, moved in plan.moved_counts().items()],
            'show_id_number': person_privacy.can_view_id_number(request.user),
        })
        return render(request, self.template_name, context)


class PersonMergeDoView(_MergeBase):
    """Carries out the confirmed merge."""
    http_method_names = ['post']

    def post(self, request, pk):
        kept = get_object_or_404(Person, pk=pk)
        fingerprint = request.POST.get('fingerprint', '')
        try:
            if not fingerprint:
                raise MergeError("The merge was not confirmed.")
            merged = self.chosen_persons(request)
            names = [str(p) for p in merged]
            plan = merge_persons(kept, merged, request.user, expected_plan=fingerprint)
        except MergeError as error:
            messages.error(request, str(error))
            return self.back(kept)
        moved = sum(plan.moved_counts().values())
        dropped = sum(plan.dropped_counts().values())
        filled = ', '.join(plan.filled_fields()) or 'none'
        messages.success(
            request,
            f"Merged {len(names)} person(s) into {plan.kept.get_full_name()}: "
            f"{'; '.join(names)}. {moved} link(s) moved, {dropped} duplicate link(s) dropped, "
            f"fields filled: {filled}.")
        return redirect('publications:person', pk=plan.kept.pk)
