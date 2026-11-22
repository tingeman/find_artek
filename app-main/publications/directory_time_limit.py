"""A total time limit for DTU directory (LDAP) lookups.

ldap3's ``connect_timeout`` and ``receive_timeout`` don't cover name resolution: when the
server name doesn't resolve, ``getaddrinfo`` can block for minutes and the request (report
form person step, CAS login) hangs with it. ``call_with_time_limit`` runs the lookup in a
daemon thread and waits at most ``settings.DIRECTORY_LOOKUP_TIME_LIMIT`` seconds (default
``DEFAULT_TIME_LIMIT``) in total; after that it raises ``DirectoryTimeout`` and the caller
handles it like an unreachable directory. A stuck thread ends by itself when the blocked call
returns; as a daemon thread it doesn't hold up the process at exit.

At most ``MAX_RUNNING`` lookups run at the same time, so stuck threads can't pile up: a lookup
that finds no free slot within the time limit raises ``DirectoryTimeout`` too.

The function run in the thread must only talk to the directory (ldap3), never use the
database: a Django connection opened in that thread would not be closed.
"""
import threading
import time

from django.conf import settings

DEFAULT_TIME_LIMIT = 8  # seconds, connect + bind + search, name resolution included
MAX_RUNNING = 4

_slots = threading.BoundedSemaphore(MAX_RUNNING)


class DirectoryTimeout(Exception):
    """The directory lookup didn't finish within the time limit."""


def time_limit():
    return float(getattr(settings, 'DIRECTORY_LOOKUP_TIME_LIMIT', DEFAULT_TIME_LIMIT))


def call_with_time_limit(func, *args, **kwargs):
    """``func(*args, **kwargs)`` in a worker thread; its result, or its exception re-raised.
    Raises DirectoryTimeout when it takes longer than time_limit() seconds in total."""
    limit = time_limit()
    deadline = time.monotonic() + limit
    if not _slots.acquire(timeout=limit):
        raise DirectoryTimeout(f'no free lookup slot within {limit:g} s')
    outcome = {}
    done = threading.Event()

    def run():
        try:
            outcome['value'] = func(*args, **kwargs)
        except BaseException as exc:  # handed to the caller
            outcome['error'] = exc
        finally:
            _slots.release()
            done.set()

    threading.Thread(target=run, name='directory-lookup', daemon=True).start()
    if not done.wait(max(0.0, deadline - time.monotonic())):
        raise DirectoryTimeout(f'no answer within {limit:g} s')
    if 'error' in outcome:
        raise outcome['error']
    return outcome['value']
