"""Shared helpers for the test modules of ``publications`` and ``api``.

No tests here (discovery imports the module because of its name and finds no TestCase).
Everything is made up: no names, study numbers or files from the real database.
"""

from django.contrib.auth.models import Group, User
from django.urls import get_script_prefix, reverse

from publications.models import Authorship, Publication, PubType
from publications.roles import DTU_USER


def app_path(url):
    """The path the test client must request for a reversed URL.

    With FORCE_SCRIPT_NAME ('/find' in the production settings the release gate uses),
    reverse() includes the prefix, but the test client sends its path as PATH_INFO, so the
    prefix has to be removed. Without a prefix (development settings) the URL is unchanged.
    """
    prefix = get_script_prefix()
    return '/' + url[len(prefix):] if url.startswith(prefix) else url


def page_path(name, **kwargs):
    """Test client path of the ``publications:<name>`` URL."""
    return app_path(reverse(f'publications:{name}', kwargs=kwargs))


def api_path(name, **kwargs):
    """Test client path of the ``api:<name>`` URL."""
    return app_path(reverse(f'api:{name}', kwargs=kwargs))


def make_user(username, *group_names, superuser=False, password='x'):
    """A user in ``dtu_user`` plus the named role groups (roles.py: members of artek_staff
    and artek_editor are also in dtu_user). ``superuser=True`` makes a superuser. The groups
    come from the data migration 0003_registration_groups."""
    if superuser:
        user = User.objects.create_superuser(username, password=password)
    else:
        user = User.objects.create_user(username, password=password)
    user.groups.add(*(Group.objects.get(name=name) for name in (DTU_USER, *group_names)))
    return user


def report_type():
    """The PubType of student reports."""
    return PubType.objects.create(type='STUDENTREPORT')


def make_report(pubtype, number, *, verified, confidential, title=None, year=1999, authors=(),
                **fields):
    """A report ``number`` with title ``Report <number>`` unless given. ``authors`` are
    Persons, listed in that order (author_id 0, 1, ...). Other model fields via ``fields``."""
    pub = Publication.objects.create(
        type=pubtype, number=number, title=f'Report {number}' if title is None else title,
        year=year, verified=verified, confidential=confidential, **fields)
    for author_id, person in enumerate(authors):
        Authorship.objects.create(publication=pub, person=person, author_id=author_id)
    return pub
