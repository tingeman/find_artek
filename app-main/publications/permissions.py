"""Access control of the write views (plan "registration" T4/T5, roadmap FA-R53 S2/S3).

One rule per action, taken from the model methods (Publication.is_editable_by,
is_deletable_by, is_verifiable_by, Feature.is_deletable_by) and Django permissions, so views,
templates and tests share it.

On a publication or a feature:

- ``view``:        ``visibility.can_view_publication`` / ``visibility.can_view_feature``
                   (roadmap FA-R75; the only action that can be True for anonymous users)

On a publication:

- ``edit``:        ``Publication.is_editable_by`` (change_publication, or edit_own_publication and own)
- ``delete``:      ``Publication.is_deletable_by`` (delete_publication, or delete_own_publication and own)
- ``verify``:      ``Publication.is_verifiable_by`` (verify_publication)
- ``add_feature``: ``publications.add_feature`` and ``Publication.is_editable_by``

On a feature:

- ``delete_feature``: ``Feature.is_deletable_by`` (delete_feature, or delete_own_feature and
                      listed on a report the feature belongs to)

Without an object (a plain Django permission):

- ``add``:         ``publications.add_publication`` (add a report)
- ``manage``:      ``publications.change_publication`` (editor tools: change report number,
                   Excel import)
- ``bulk_delete``: ``publications.delete_publication``
- ``add_person``:  ``publications.add_person``

Active superusers pass every check (Django's has_perm; for ``view`` the visibility rule).

``PermissionMixin`` (and its subclasses for a publication or a feature in the URL) puts this in
front of a class-based view: a request with a method the view doesn't accept gets 405, an
anonymous user is redirected to LOGIN_URL with ``next``, an unknown object is 404, a logged-in
user who may not do the action gets 403, everything else proceeds. ``view`` differs (the report
and feature pages, plan PLAN_confidential T3): anonymous users are checked like everyone else
and only redirected to the login when the entry is hidden from them, and a logged-in user who
may not see the entry gets 404, so that its existence isn't confirmed. ``permission_required`` does
the same for function views (or answers with JSON 401/403 for ajax endpoints).
"""
from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from publications.models import Feature, Publication
from publications.visibility import can_view_feature, can_view_publication

VIEW = 'view'
ADD = 'add'
EDIT = 'edit'
DELETE = 'delete'
VERIFY = 'verify'
ADD_FEATURE = 'add_feature'
DELETE_FEATURE = 'delete_feature'
MANAGE = 'manage'
BULK_DELETE = 'bulk_delete'
ADD_PERSON = 'add_person'

# Actions that are a plain Django permission, without an object.
GLOBAL_PERMISSIONS = {
    ADD: 'publications.add_publication',
    MANAGE: 'publications.change_publication',
    BULK_DELETE: 'publications.delete_publication',
    ADD_PERSON: 'publications.add_person',
}
PUBLICATION_ACTIONS = (EDIT, DELETE, VERIFY, ADD_FEATURE)
FEATURE_ACTIONS = (DELETE_FEATURE,)
# Actions on a publication or a feature (decided by the object's type).
OBJECT_ACTIONS = (VIEW,)

ACTIONS = tuple(GLOBAL_PERMISSIONS) + PUBLICATION_ACTIONS + FEATURE_ACTIONS + OBJECT_ACTIONS

DENIED_MESSAGES = {
    VIEW: "You do not have permission to see this entry.",
    ADD: "You do not have permissions to add reports!",
    EDIT: "You do not have permissions to edit this publication!",
    DELETE: "You do not have permission to delete this publication.",
    VERIFY: "You do not have permissions to verify or unverify this report!",
    ADD_FEATURE: "You do not have permissions to add features to this publication!",
    DELETE_FEATURE: "You do not have permission to delete this feature.",
    MANAGE: "Only ARTEK editors may use this function.",
    BULK_DELETE: "Only ARTEK editors may delete publications in bulk.",
    ADD_PERSON: "You do not have permissions to add persons!",
}


def user_may(user, action, obj=None):
    """True if ``user`` may do ``action`` (one of ACTIONS).

    ``obj`` is the publication for PUBLICATION_ACTIONS, the feature for FEATURE_ACTIONS and
    either for OBJECT_ACTIONS; it is ignored for the actions in GLOBAL_PERMISSIONS. Anonymous
    users get False, except for ``view`` (publications.visibility decides).
    """
    if action not in ACTIONS:
        raise ValueError(f"Unknown action: {action!r}")
    if action == VIEW:
        if isinstance(obj, Publication):
            return can_view_publication(user, obj)
        if isinstance(obj, Feature):
            return can_view_feature(user, obj)
        raise ValueError(f"Action {action!r} needs a publication or a feature, not {obj!r}")
    if not getattr(user, 'is_authenticated', False):
        return False
    if action in GLOBAL_PERMISSIONS:
        return user.has_perm(GLOBAL_PERMISSIONS[action])
    if obj is None:
        raise ValueError(f"Action {action!r} needs an object")
    if action == EDIT:
        return obj.is_editable_by(user)
    if action == DELETE:
        return obj.is_deletable_by(user)
    if action == VERIFY:
        return bool(obj.is_verifiable_by(user))
    if action == ADD_FEATURE:
        return user.has_perm('publications.add_feature') and obj.is_editable_by(user)
    # DELETE_FEATURE
    return obj.is_deletable_by(user)


def access_denied_response(request, action, base_template='publications/base.html',
                           template_name='publications/access_denied.html'):
    """The 403 page shown when a logged-in user may not do ``action``."""
    context = {'base_template': base_template, 'error': DENIED_MESSAGES[action]}
    return render(request, template_name, context, status=403)


class PermissionMixin(AccessMixin):
    """Require login and the permission for ``permission``.

    Put it first in the bases, and don't override ``dispatch`` in the view (or call
    ``super().dispatch`` before doing anything): the check must run before any view code.

    - ``permission``: one of ACTIONS; or override ``get_required_permission()``.
    - ``get_permission_object()``: the object the action is checked on (None here; the
      subclasses below take it from the URL).
    """
    permission = None
    denied_template_name = 'publications/access_denied.html'

    def get_required_permission(self):
        return self.permission

    def get_permission_object(self):
        return None

    def permission_denied_response(self, action):
        # base_template is what BaseView.get_context_data adds; set here so that the
        # mixin doesn't depend on the view's context methods.
        return access_denied_response(
            self.request, action,
            base_template=getattr(self, 'base_template', 'publications/base.html'),
            template_name=self.denied_template_name)

    def dispatch(self, request, *args, **kwargs):
        # A method the view doesn't accept is refused before anything else, also for
        # anonymous users (verify/unverify by GET is 405, not a login redirect).
        if request.method.lower() not in self.http_method_names:
            return self.http_method_not_allowed(request, *args, **kwargs)
        action = self.get_required_permission()
        # VIEW is the only action anonymous users may have: they are checked like everyone
        # else and sent to the login only when the entry is hidden from them.
        if not request.user.is_authenticated and action != VIEW:
            return self.handle_no_permission()   # redirect to LOGIN_URL with next
        obj = self.get_permission_object()
        if not user_may(request.user, action, obj):
            if not request.user.is_authenticated:
                return self.handle_no_permission()
            if action == VIEW:
                # Not 403: a hidden entry looks like a missing one.
                raise Http404("No such entry.")
            return self.permission_denied_response(action)
        return super().dispatch(request, *args, **kwargs)


class PublicationPermissionMixin(PermissionMixin):
    """``PermissionMixin`` on the publication of the URL.

    - ``publication_url_kwarg``: URL keyword of the publication pk. Without it in the URL
      (add mode) there is no publication and only actions without an object can be checked.

    After the check, ``self.publication`` holds the publication (or None).
    """
    publication_url_kwarg = 'pk'

    def get_permission_publication(self):
        pk = self.kwargs.get(self.publication_url_kwarg)
        if pk is None:
            return None
        return get_object_or_404(Publication, pk=pk)

    def get_permission_object(self):
        self.publication = self.get_permission_publication()
        return self.publication


class FeaturePermissionMixin(PermissionMixin):
    """``PermissionMixin`` on the feature of the URL (``feature_url_kwarg``).

    After the check, ``self.feature`` holds the feature."""
    feature_url_kwarg = 'pk'

    def get_permission_object(self):
        self.feature = get_object_or_404(Feature, pk=self.kwargs[self.feature_url_kwarg])
        return self.feature


class ReportFormPermissionMixin(PublicationPermissionMixin):
    """Add/edit workflow (form, review, finalize): ``add`` without a pk, ``edit`` with one."""

    def get_required_permission(self):
        return EDIT if self.publication_url_kwarg in self.kwargs else ADD


def permission_required(action, json_response=False):
    """Decorator for function views that need ``action`` (an action without an object).

    Anonymous: redirect to LOGIN_URL with ``next``, or with ``json_response`` a JSON 401.
    Not allowed: 403 with the access-denied page, or with ``json_response`` a JSON 403.
    Put it below ``require_http_methods`` so that a wrong method is 405 first.
    """
    if action not in GLOBAL_PERMISSIONS:
        raise ValueError(f"permission_required takes an action without an object, not {action!r}")

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if json_response:
                    return JsonResponse({'error': 'Login required'}, status=401)
                return redirect_to_login(request.get_full_path())
            if not user_may(request.user, action):
                if json_response:
                    return JsonResponse({'error': DENIED_MESSAGES[action]}, status=403)
                return access_denied_response(request, action)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
