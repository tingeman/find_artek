"""Count who may download the files under MEDIA_ROOT (roadmap FA-R75, plan PLAN_confidential T5).

Read-only. Walks MEDIA_ROOT, classifies every file (report PDF, appendix, thumbnail, feature
file, feature image, temp upload, unowned) with the rule of the checked media view
(publications.media_access) and prints, per class, how many files anonymous users may download
(public), only some logged-in users (restricted), or only artek_editor and superusers
(editors_only). Never prints file contents; ``--list-unowned`` prints the paths (relative to
MEDIA_ROOT) of the files nothing owns, which the view hides from everyone but editors.

    python manage.py check_media_access [--list-unowned]
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from publications.media_access import CLASSES, LEVELS, UNOWNED, walk_media_files


class Command(BaseCommand):
    help = ('Count the files under MEDIA_ROOT per class (report PDF, appendix, thumbnail, '
            'feature file/image, temp, unowned) and access level (public, restricted, '
            'editors_only). Read-only.')

    def add_arguments(self, parser):
        parser.add_argument('--list-unowned', action='store_true',
                            help='Also print the paths of the unowned files (relative to MEDIA_ROOT).')

    def handle(self, *args, **options):
        root = settings.MEDIA_ROOT
        if not os.path.isdir(root):
            self.stderr.write(f'MEDIA_ROOT {root} is not a directory.')
            return

        counts = {cls: dict.fromkeys(LEVELS, 0) for cls in CLASSES}
        unowned = []
        for relpath, cls, level in walk_media_files():
            counts[cls][level] += 1
            if cls == UNOWNED:
                unowned.append(relpath)

        width = max(len(cls) for cls in CLASSES + ('total',))
        self.stdout.write(f'{"class":<{width}}  ' + '  '.join(f'{lv:>12}' for lv in LEVELS)
                          + f'  {"total":>8}')
        totals = dict.fromkeys(LEVELS, 0)
        for cls in CLASSES:
            row = counts[cls]
            for lv in LEVELS:
                totals[lv] += row[lv]
            self.stdout.write(f'{cls:<{width}}  ' + '  '.join(f'{row[lv]:>12}' for lv in LEVELS)
                              + f'  {sum(row.values()):>8}')
        self.stdout.write(f'{"total":<{width}}  ' + '  '.join(f'{totals[lv]:>12}' for lv in LEVELS)
                          + f'  {sum(totals.values()):>8}')

        if options['list_unowned']:
            self.stdout.write('')
            self.stdout.write(f'Unowned files ({len(unowned)}):')
            for relpath in unowned:
                self.stdout.write(relpath)
