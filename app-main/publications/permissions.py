"""Access control of the report write views (plan "registration" T4, roadmap FA-R53 S2).

One rule per action, taken from the model methods (Publication.is_editable_by,
is_deletable_by, is_verifiable_by) and Django permissions, so views, templates and tests
share it:

- ``add``:    ``publications.add_publication``
- ``edit``:   ``Publication.is_editable_by`` (change_publication, or edit_own_publication and own)
- ``delete``: ``Publication.is_deletable_by`` (delete_publication, or delete_own_publication and own)
- ``verify``: ``Publication.is_verifiable_by`` (verify_publication)

Active superusers pass every check (Django's has_perm).

``PublicationPermissionMixin`` puts this in front of a class-based view: a request with a
method the view doesn't accept gets 405, an anonymous user is redirected to LOGIN_URL with
``next``, a logged-in user who may not do the action gets 403, everything else proceeds.
"""
from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404, render

from publications.models import Publication

ADD = 'add'
EDIT = 'edit'
DELETE = 'delete'
VERIFY = 'verify'

ACTIONS = (ADD, EDIT, DELETE, VERIFY)

DENIED_MESSAGES = {
    ADD: "You do not have permissions to add reports!",
    EDIT: "You do not have permissions to edit this publication!",
    DELETE: "You do not have permission to delete this publication.",
    VERIFY: "You do not have permissions to verify or unverify this report!",
}


def user_may(user, action, publication=None):
    """True if ``user`` may do ``action`` (one of ACTIONS) on ``publication``.

    ``publication`` is required for every action except ``add``. Anonymous users get False.
    """
    if action not in ACTIONS:
        raise ValueError(f"Unknown publication action: {action!r}")
    if not getattr(user, 'is_authenticated', False):
        return False
    if action == ADD:
        return user.has_perm('publications.add_publication')
    if publication is None:
        raise ValueError(f"Action {action!r} needs a publication")
    if action == EDIT:
        return publication.is_editable_by(user)
    if action == DELETE:
        return publication.is_deletable_by(user)
    return publication.is_verifiable_by(user)


class PublicationPermissionMixin(AccessMixin):
    """Require login and the permission for ``permission`` on the publication of the URL.

    Put it first in the bases, and don't override ``dispatch`` in the view (or call
    ``super().dispatch`` before doing anything): the check must run before any view code.

    - ``permission``: one of ACTIONS; or override ``get_required_permission()``.
    - ``publication_url_kwarg``: URL keyword of the publication pk. Without it in the URL
      (add mode) there is no publication and only ``add`` can be checked.

    After the check, ``self.publication`` holds the publication (or None).
    """
    permission = None
    publication_url_kwarg = 'pk'
    denied_template_name = 'publications/access_denied.html'

    def get_required_permission(self):
        return self.permission

    def get_permission_publication(self):
        pk = self.kwargs.get(self.publication_url_kwarg)
        if pk is None:
            return None
        return get_object_or_404(Publication, pk=pk)

    def permission_denied_response(self, action):
        # base_template is what BaseView.get_context_data adds; set here so that the
        # mixin doesn't depend on the view's context methods.
        context = {
            'base_template': getattr(self, 'base_template', 'publications/base.html'),
            'error': DENIED_MESSAGES[action],
        }
        return render(self.request, self.denied_template_name, context, status=403)

    def dispatch(self, request, *args, **kwargs):
        # A method the view doesn't accept is refused before anything else, also for
        # anonymous users (verify/unverify by GET is 405, not a login redirect).
        if request.method.lower() not in self.http_method_names:
            return self.http_method_not_allowed(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return self.handle_no_permission()   # redirect to LOGIN_URL with next
        action = self.get_required_permission()
        self.publication = self.get_permission_publication()
        if not user_may(request.user, action, self.publication):
            return self.permission_denied_response(action)
        return super().dispatch(request, *args, **kwargs)


class ReportFormPermissionMixin(PublicationPermissionMixin):
    """Add/edit workflow (form, review, finalize): ``add`` without a pk, ``edit`` with one."""

    def get_required_permission(self):
        return EDIT if self.publication_url_kwarg in self.kwargs else ADD
