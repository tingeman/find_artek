"""Write the template of the Excel feature import (plan "features" T10).

    python manage.py make_feature_import_template [--output PATH]

Default output: the template in the app's static files,
``publications/static/publications/docs/ARTEK_feature_list.xlsx`` (committed; run this again
after changing ``publications.feature_import.COLUMNS`` or the help texts). Sheets "Features"
(column names and made-up examples) and "Help" (columns, rules, EPSG codes for Greenland).
Writes no database rows and reads no media files.
"""
import os

from django.core.management.base import BaseCommand

from publications import feature_import

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'static', *feature_import.TEMPLATE_STATIC_PATH.split('/'))


class Command(BaseCommand):
    help = 'Write the Excel template of the feature import (sheets Features and Help).'

    def add_arguments(self, parser):
        parser.add_argument('--output', default=DEFAULT_OUTPUT,
                            help=f'Where to write the .xlsx file (default: {DEFAULT_OUTPUT}).')

    def handle(self, *args, **options):
        output = options['output']
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        feature_import.build_template_workbook().save(output)
        self.stdout.write(self.style.SUCCESS(f'Template written to {output}'))
