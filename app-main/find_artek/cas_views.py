"""CAS login view of find_artek (django-cas-ng's LoginView, routed as ``cas_ng_login``).

django-cas-ng 5.1 checks ``?next=`` at login (CAS_CHECK_NEXT, default True): a next page on
another host raises its RedirectException, which Django would turn into a 500. Up to 5.0.1
the check never ran at login and such a next page was followed after the CAS login (an open
redirect). Here the exception becomes SuspiciousOperation, i.e. a 400 Bad Request that is
logged on the ``django.security`` logger: a crafted link is a client error, not a server
error, and the user is never sent to the other host.

dispatch stays csrf_exempt as in django-cas-ng (the CAS server POSTs single-logout requests).
"""
from django.core.exceptions import SuspiciousOperation
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_cas_ng.utils import RedirectException
from django_cas_ng.views import LoginView as CasNgLoginView


class LoginView(CasNgLoginView):

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except RedirectException as exc:
            raise SuspiciousOperation(f'CAS login: {exc}') from exc
