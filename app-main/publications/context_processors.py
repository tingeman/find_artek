import hashlib

from django.conf import settings

def URL_PREFIX(request):
    return {
        'URL_PREFIX': settings.URL_PREFIX
    }


ANONYMOUS_AUTH_MARKER = 'anon'


def AUTH_MARKER(request):
    """A marker for the login state, rendered by base.html (FA-R75, PLAN_confidential T6).

    The page JS clears its sessionStorage caches of API data (``reportData*``,
    ``featureData*``) when the marker differs from the one stored on the previous page, so
    data loaded while logged in doesn't survive a logout and anonymous data doesn't stay
    stale after a login.

    ``anon`` for anonymous users. For logged-in users the first 16 hex characters of the
    SHA-256 of the session key: Django rotates the key at login and flushes the session at
    logout, so the marker changes on every login, and it reveals neither the user id nor
    the username (nor the session key itself).
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'AUTH_MARKER': ANONYMOUS_AUTH_MARKER}
    session = getattr(request, 'session', None)
    session_key = getattr(session, 'session_key', None) or ''
    digest = hashlib.sha256(session_key.encode()).hexdigest()[:16]
    return {'AUTH_MARKER': digest}
