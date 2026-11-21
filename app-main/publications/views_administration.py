"""The "Administration" page (plan release-2026-7 T6, roadmap FA-R100).

Replaces the header's "Add" drop-down. A page of picture tiles in the style of the front page,
laid out like the classic version's administration page (``add_menu_2.html``, URL ``/pubs/add/``),
in the classic order without the "Backup" tile (backups are done by dtu_sus_web_server):

1. Add report              -> ``publications:add_report`` (action ``add``)
2. Add feature             -> greyed: features are added from a report's page
3. Add person              -> greyed: not available yet (FA-R58)
4. Import reports from Excel -> ``publications:add_reports_from_file_upload`` (action ``manage``)
5. Import features from Excel -> greyed: not available yet (FA-R63)
6. Django admin            -> ``admin:index``, only shown to ``user.is_staff``

A tile the user may not use, or that isn't built yet, is greyed out with the reason and is not
a link. The page itself has the same guard as the old menu: anonymous users are redirected to
the login (LOGIN_URL with ``next``), logged-in users with neither ``add`` nor ``manage`` get 403.
The page only shows links; every target view checks its own permission.
"""
from dataclasses import dataclass
from typing import Optional

from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _

from publications.permissions import ADD, MANAGE, access_denied_response, user_may
from publications.views import BaseView

DENIED_MESSAGE = "Only users who may add reports or ARTEK editors may open the administration page."


@dataclass(frozen=True)
class Tile:
    key: str                      # CSS class suffix: admin-tile-<key>
    title: str
    image: Optional[str]          # static path, or None for a plain styled tile
    url: Optional[str] = None     # None: greyed out, not a link
    reason: Optional[str] = None  # shown on a greyed tile

    @property
    def enabled(self):
        return self.url is not None


def may_open_administration(user):
    """The page guard, the same as the header link's condition in base.html."""
    return user_may(user, ADD) or user_may(user, MANAGE)


def administration_tiles(user):
    """The tiles for ``user`` in display order."""
    may_add = user_may(user, ADD)
    may_manage = user_may(user, MANAGE)
    tiles = [
        Tile('add-report', _('Add report'), 'publications/img/reports_3_190x150.jpg',
             url=reverse('publications:add_report') if may_add else None,
             reason=None if may_add else _('Needs permission to add reports')),
        Tile('add-feature', _('Add feature'), 'publications/img/add_feature_190x150.png',
             reason=_("Open a report to add features")),
        Tile('add-person', _('Add person'), 'publications/img/add_person_190x150.png',
             reason=_('Not available yet')),
        Tile('import-reports', _('Import reports from Excel'),
             'publications/img/reports_file_190x150.png',
             url=reverse('publications:add_reports_from_file_upload') if may_manage else None,
             reason=None if may_manage else _('Needs the editor role')),
        Tile('import-features', _('Import features from Excel'),
             'publications/img/add_feature_file_190x150.png',
             reason=_('Not available yet')),
    ]
    if user.is_staff:
        tiles.append(Tile('django-admin', _('Django admin'), None, url=reverse('admin:index')))
    return tiles


class AdministrationView(AccessMixin, BaseView):
    template_name = 'publications/administration.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()   # redirect to LOGIN_URL with next
        if not may_open_administration(request.user):
            return access_denied_response(request, ADD, error=DENIED_MESSAGE)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, **kwargs):
        context = self.get_context_data(**kwargs)
        context['tiles'] = administration_tiles(request.user)
        return render(request, self.template_name, context)
