"""Person tools for editors (plan release-2026-7 T7, roadmap FA-R66; the merge page follows in T8).

``PersonConfirmView``: POST ``person/<pk>/confirm/`` clears the duplicate markers of all links
of the person (person_links.clear_markers) and goes back to the person page. Needs
``merge_person`` (permissions.MERGE_PERSON): anonymous users are sent to the login, other
users get 403, a GET is 405.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from publications.models import Person
from publications.permissions import MERGE_PERSON, PermissionMixin
from publications.person_links import clear_markers
from publications.views import BaseView


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
