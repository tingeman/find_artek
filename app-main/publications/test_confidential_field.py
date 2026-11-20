"""FA-R75 (plan PLAN_confidential, T1): the field Publication.confidential and its migration.

Migration 0004 adds the field and sets it on every report whose comment mentions
"confidential" (case-insensitive); the comment text stays unchanged.
"""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from publications.models import Publication
from publications.test_factories import report_type

APP = 'publications'
BEFORE = [(APP, '0003_registration_groups')]
AFTER = [(APP, '0004_publication_confidential')]


class ConfidentialFieldTests(TestCase):

    def test_default_is_false(self):
        self.assertFalse(Publication().confidential)

    def test_saved_publication_defaults_to_false(self):
        pubtype = report_type()
        pub = Publication.objects.create(type=pubtype, title='New report', year=2026)
        pub.refresh_from_db()
        self.assertFalse(pub.confidential)

    def test_flag_can_be_set(self):
        pubtype = report_type()
        pub = Publication.objects.create(
            type=pubtype, title='Secret report', year=2026, confidential=True)
        pub.refresh_from_db()
        self.assertTrue(pub.confidential)


class ConfidentialMigrationTests(TransactionTestCase):
    """Migrates the test database back to 0003 and forward again; ends at the latest state."""

    # The flush after a TransactionTestCase would also remove the groups that migration 0003
    # creates; restore the database content afterwards so later tests still find them.
    serialized_rollback = True

    COMMENTS = {
        'upper': ('Report is CONFIDENTIAL until 2030', True),
        'lower': ('confidential', True),
        'mixed': ('Strictly Confidential.', True),
        'public': ('public report', False),
        'empty': ('', False),
    }

    def _migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        executor.loader.build_graph()
        return executor.loader.project_state(targets).apps

    def _latest(self):
        executor = MigrationExecutor(connection)
        return executor.loader.graph.leaf_nodes()

    def tearDown(self):
        # Always leave the test database at the latest migrations.
        self._migrate(self._latest())
        super().tearDown()

    def test_flag_set_from_comment_and_reversible(self):
        old_apps = self._migrate(BEFORE)
        OldPubType = old_apps.get_model(APP, 'PubType')
        OldPublication = old_apps.get_model(APP, 'Publication')
        self.assertNotIn('confidential',
                         [f.name for f in OldPublication._meta.get_fields()])
        pubtype = OldPubType.objects.create(type='STUDENTREPORT')
        ids = {}
        for key, (comment, _) in self.COMMENTS.items():
            ids[key] = OldPublication.objects.create(
                type=pubtype, title=f'Report {key}', year=2020, comment=comment).pk

        new_apps = self._migrate(AFTER)
        NewPublication = new_apps.get_model(APP, 'Publication')
        for key, (comment, expected) in self.COMMENTS.items():
            with self.subTest(comment=comment):
                pub = NewPublication.objects.get(pk=ids[key])
                self.assertIs(pub.confidential, expected)
                self.assertEqual(pub.comment, comment)

        # Backwards to 0003 (drops the column, data step is a no-op) and forward again.
        old_apps = self._migrate(BEFORE)
        OldPublication = old_apps.get_model(APP, 'Publication')
        for key, (comment, _) in self.COMMENTS.items():
            self.assertEqual(OldPublication.objects.get(pk=ids[key]).comment, comment)

        new_apps = self._migrate(AFTER)
        NewPublication = new_apps.get_model(APP, 'Publication')
        flagged = set(NewPublication.objects.filter(confidential=True).values_list('pk', flat=True))
        self.assertEqual(flagged, {ids['upper'], ids['lower'], ids['mixed']})
