"""A report that still has features cannot be deleted (plan "features" T13, owner 2026-11-23).

The same rule holds for the bulk delete (BulkDeletePublicationsView: reports with features
are listed apart, skipped and named in an error) and the Django admin (PublicationAdmin:
no delete permission on such a report, the "Delete selected" action leaves it).

DeleteReportView: while the report has features, GET shows no delete button but an alert
(``delete-report-has-features``) with the number of features, the two ways to remove them
("Delete all features", only linked for users with ``add_feature`` on the report, or one by
one on the report page) and the report's features with links to their pages. POST changes
nothing and returns to the report with an error. Other reports a feature belongs to are
never named. Without features the delete works as before.

Users from ReportAccessTestBase (roles of migration 0003): supervisor ``staff_own`` of
``pub`` (may delete it, own), artek_editor ``editor``. The appendix file is a tiny fixture in
a temporary MEDIA_ROOT.
"""
import datetime
import os
import shutil
import tempfile

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, override_settings
from django.urls import reverse

from publications.admin import PublicationAdmin
from publications.models import Appendenciesship, Feature, FileObject, Publication
from publications.test_factories import app_path, make_user, page_path
from publications.test_report_access import ReportAccessTestBase


class ReportDeleteWithFeaturesTests(ReportAccessTestBase):

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='find_artek_report_delete_features_')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

    # --- fixtures

    def feature(self, name, *pubs):
        feature = Feature.objects.create(name=name, date=datetime.date(1999, 7, 1))
        feature.publications.add(*pubs)
        return feature

    def appendix(self, name='appendix.txt'):
        relpath = f'reports/1999/appendices/{name}'
        full = self.full(relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(b'made-up appendix\n')
        fileobject = FileObject.objects.create(file=relpath)
        Appendenciesship.objects.create(publication=self.pub, fileobject=fileobject)
        return fileobject

    def full(self, relpath):
        return os.path.join(self.media_root, *str(relpath).split('/'))

    def path(self):
        return page_path('delete_report', pk=self.pub.pk)

    def get(self, user):
        self.login(user)
        response = self.client.get(self.path())
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def post_delete(self, user):
        self.login(user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.path(), {'action': 'delete'})

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def delete_only_user(self):
        """A user who may delete any report but has no ``add_feature`` (no role group)."""
        user = User.objects.create_user('delonly')
        user.user_permissions.add(Permission.objects.get(
            content_type__app_label='publications', codename='delete_publication'))
        return user

    # --- GET

    def test_page_with_features_has_alert_and_no_delete_button(self):
        self.feature('Borehole A', self.pub)
        self.feature('Borehole B', self.pub)
        for user in (self.staff_own, self.editor):
            with self.subTest(user=user.username):
                html = self.get(user)
                self.assertIn('id="delete-report-has-features"', html)
                self.assertIn('This report still has <strong>2 features</strong>', html)
                self.assertIn('must have no features before it can be deleted', html)
                self.assertIn('Delete all features', html)
                self.assertIn('one by one', html)
                self.assertNotIn('value="delete"', html)
                self.assertNotIn('class="btn-delete"', html)
                # The cancel button stays.
                self.assertIn('value="cancel"', html)

    def test_page_lists_the_features_with_links(self):
        first = self.feature('Borehole A', self.pub)
        second = self.feature('Pit B', self.pub)
        html = self.get(self.editor)
        for feature in (first, second):
            url = reverse('publications:feature', kwargs={'pk': feature.pk})
            self.assertIn(f'href="{url}?report={self.pub.pk}"', html)
            self.assertIn(feature.name, html)

    def test_one_feature_singular(self):
        self.feature('Borehole A', self.pub)
        html = self.get(self.editor)
        self.assertIn('This report still has <strong>1 feature</strong>', html)

    def test_delete_all_link_for_users_who_may_use_it(self):
        self.feature('Borehole A', self.pub)
        url = reverse('publications:delete_report_features', kwargs={'pk': self.pub.pk})
        for user in (self.staff_own, self.editor):
            with self.subTest(user=user.username):
                html = self.get(user)
                self.assertIn('id="delete-report-features-link"', html)
                self.assertIn(f'href="{url}"', html)
                self.assertNotIn('an ARTEK editor can', html)

    def test_no_delete_all_link_without_add_feature(self):
        self.feature('Borehole A', self.pub)
        user = self.delete_only_user()
        html = self.get(user)
        url = reverse('publications:delete_report_features', kwargs={'pk': self.pub.pk})
        self.assertIn('id="delete-report-has-features"', html)
        self.assertNotIn('id="delete-report-features-link"', html)
        self.assertNotIn(f'href="{url}"', html)
        self.assertIn('an ARTEK editor can', html)
        self.assertNotIn('value="delete"', html)

    def test_page_without_features_unchanged(self):
        html = self.get(self.editor)
        self.assertNotIn('delete-report-has-features', html)
        self.assertIn('value="delete"', html)
        self.assertIn('class="btn-delete"', html)

    def test_hidden_other_report_is_not_named(self):
        hidden = Publication.objects.create(
            type=self.pubtype, title='Secret shared report', number='88-77', year=1988,
            verified=True, confidential=True)
        self.feature('Shared borehole', self.pub, hidden)
        self.feature('Own borehole', self.pub)
        html = self.get(self.staff_own)   # not listed on ``hidden``, may not see it
        self.assertIn('This report still has <strong>2 features</strong>', html)
        self.assertIn('Shared borehole', html)
        self.assertNotIn('Secret shared report', html)
        self.assertNotIn('88-77', html)
        self.assertNotIn(f'report={hidden.pk}"', html)
        self.assertNotIn(reverse('publications:report', kwargs={'pk': hidden.pk}) + '"', html)

    # --- POST

    def test_post_with_features_changes_nothing(self):
        shared_with = Publication.objects.create(
            type=self.pubtype, title='Other report', number='99-02', year=1999, verified=True)
        own = self.feature('Borehole A', self.pub)
        shared = self.feature('Shared pit', self.pub, shared_with)
        appendix = self.appendix()
        features_before = Feature.objects.count()
        for user in (self.staff_own, self.editor):
            with self.subTest(user=user.username):
                self.client = self.client_class()   # fresh session: no messages left over
                response = self.post_delete(user)
                self.assertRedirects(
                    response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                    fetch_redirect_response=False)
                messages = self.messages(response)
                self.assertEqual(len(messages), 1, messages)
                self.assertIn('cannot be deleted', messages[0])
                self.assertIn('2 feature(s)', messages[0])
                self.assertIn('Delete all features', messages[0])
                self.assertNotIn('Other report', messages[0])
                self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())
                self.assertEqual(Feature.objects.count(), features_before)
                self.assertEqual(set(own.publications.values_list('pk', flat=True)),
                                 {self.pub.pk})
                self.assertEqual(set(shared.publications.values_list('pk', flat=True)),
                                 {self.pub.pk, shared_with.pk})
                self.assertTrue(FileObject.objects.filter(pk=appendix.pk).exists())
                self.assertTrue(Appendenciesship.objects.filter(
                    publication=self.pub, fileobject=appendix).exists())
                self.assertTrue(os.path.exists(self.full(appendix.file.name)))

    def test_post_without_features_deletes_as_before(self):
        appendix = self.appendix()
        other = Publication.objects.create(
            type=self.pubtype, title='Other report', number='99-02', year=1999, verified=True)
        elsewhere = self.feature('Other borehole', other)
        response = self.post_delete(self.editor)
        self.assertRedirects(response, reverse('publications:reports'),
                             fetch_redirect_response=False)
        self.assertFalse(Publication.objects.filter(pk=self.pub.pk).exists())
        self.assertFalse(Appendenciesship.objects.filter(fileobject_id=appendix.pk).exists())
        self.assertFalse(os.path.exists(self.full(appendix.file.name)))
        self.assertTrue(Feature.objects.filter(pk=elsewhere.pk).exists())

    def test_cancel_with_features_returns_to_report(self):
        self.feature('Borehole A', self.pub)
        self.login(self.editor)
        response = self.client.post(self.path(), {'action': 'cancel'})
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())


class BulkDeleteWithFeaturesTests(ReportAccessTestBase):
    """BulkDeletePublicationsView (editors only): reports with features are skipped."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.free = Publication.objects.create(
            type=cls.pubtype, title='Free report', number='99-03', year=1999, verified=True)
        cls.other = Publication.objects.create(
            type=cls.pubtype, title='Other report', number='99-04', year=1999, verified=True)

    def setUp(self):
        # cls.pub has an own feature and one shared with cls.other; cls.free has none.
        self.own = Feature.objects.create(name='Borehole A', date=datetime.date(1999, 7, 1))
        self.own.publications.add(self.pub)
        self.shared = Feature.objects.create(name='Shared pit', date=datetime.date(1999, 7, 1))
        self.shared.publications.add(self.pub, self.other)
        self.login(self.editor)

    def path(self):
        return page_path('bulk_delete_publications')

    def selection(self):
        return [str(self.pub.pk), str(self.free.pk)]

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def test_confirm_page_lists_blocked_reports_apart(self):
        response = self.client.post(self.path(), {'selected_publications': self.selection()})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual([p.pk for p in response.context['publications_to_delete']],
                         [self.free.pk])
        self.assertEqual([p.pk for p in response.context['blocked_publications']], [self.pub.pk])
        self.assertEqual(response.context['count'], 1)
        self.assertIn('You are about to delete 1 publication(s)', html)
        self.assertIn('id="bulk-delete-blocked"', html)
        self.assertIn('has 2 features, delete them first', html)
        delete_url = reverse('publications:delete_report', kwargs={'pk': self.pub.pk})
        self.assertIn(f'href="{delete_url}"', html)
        self.assertIn('Confirm delete', html)

    def test_confirm_page_without_deletable_reports_has_no_confirm_button(self):
        response = self.client.post(self.path(), {'selected_publications': [str(self.pub.pk)]})
        html = response.content.decode()
        self.assertEqual(response.context['count'], 0)
        self.assertIn('every selected report still has features', html)
        self.assertNotIn('Confirm delete', html)

    def test_confirmed_mixed_selection_skips_blocked_and_deletes_others(self):
        response = self.client.post(self.path(), {
            'selected_publications': self.selection(), 'confirm': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Publication.objects.filter(pk=self.free.pk).exists())
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())
        self.assertTrue(Publication.objects.filter(pk=self.other.pk).exists())
        self.assertEqual(set(self.own.publications.values_list('pk', flat=True)), {self.pub.pk})
        self.assertEqual(set(self.shared.publications.values_list('pk', flat=True)),
                         {self.pub.pk, self.other.pk})
        messages = self.messages(response)
        errors = [m for m in messages if m.startswith('Not deleted')]
        self.assertEqual(len(errors), 1, messages)
        self.assertIn('99-01 (2 feature(s))', errors[0])
        self.assertNotIn('99-04', errors[0])          # not in the selection
        self.assertIn('Deleted 1 publication(s).', messages)

    def test_confirmed_selection_of_only_blocked_deletes_nothing(self):
        response = self.client.post(self.path(), {
            'selected_publications': [str(self.pub.pk)], 'confirm': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())
        messages = self.messages(response)
        self.assertFalse(any(m.startswith('Deleted') for m in messages), messages)
        self.assertTrue(any(m.startswith('Not deleted') for m in messages), messages)

    def test_without_features_deletes_as_before(self):
        Feature.objects.filter(pk__in=[self.own.pk, self.shared.pk]).delete()
        response = self.client.post(self.path(), {
            'selected_publications': self.selection(), 'confirm': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Publication.objects.filter(pk__in=[self.pub.pk, self.free.pk]).exists())
        self.assertEqual(self.messages(response), ['Deleted 2 publication(s).'])


class AdminDeleteWithFeaturesTests(ReportAccessTestBase):
    """PublicationAdmin: no delete permission on a report with features; the "Delete
    selected" action leaves it."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin_user = make_user('adminsu', superuser=True)
        cls.free = Publication.objects.create(
            type=cls.pubtype, title='Free report', number='99-03', year=1999, verified=True)

    def setUp(self):
        self.feature = Feature.objects.create(name='Borehole A', date=datetime.date(1999, 7, 1))
        self.feature.publications.add(self.pub)
        self.model_admin = PublicationAdmin(Publication, admin.site)
        self.request = RequestFactory().get('/')
        self.request.user = self.admin_user

    def test_publication_uses_publication_admin(self):
        self.assertIsInstance(admin.site._registry[Publication], PublicationAdmin)

    def test_has_delete_permission(self):
        self.assertFalse(self.model_admin.has_delete_permission(self.request, self.pub))
        self.assertTrue(self.model_admin.has_delete_permission(self.request, self.free))
        self.assertTrue(self.model_admin.has_delete_permission(self.request))   # list level

    def test_delete_page_refused_with_features(self):
        self.client.force_login(self.admin_user)
        url = app_path(reverse('admin:publications_publication_delete', args=[self.pub.pk]))
        self.assertEqual(self.client.post(url, {'post': 'yes'}).status_code, 403)
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())

    def test_delete_selected_action_leaves_blocked_report(self):
        self.client.force_login(self.admin_user)
        url = app_path(reverse('admin:publications_publication_changelist'))
        self.client.post(url, {
            'action': 'delete_selected', 'post': 'yes',
            '_selected_action': [str(self.pub.pk), str(self.free.pk)]})
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())
        self.assertEqual(list(self.feature.publications.values_list('pk', flat=True)),
                         [self.pub.pk])

    def test_delete_queryset_skips_blocked_report(self):
        request = RequestFactory().post('/')
        request.user = self.admin_user
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        self.model_admin.delete_queryset(
            request, Publication.objects.filter(pk__in=[self.pub.pk, self.free.pk]))
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())
        self.assertFalse(Publication.objects.filter(pk=self.free.pk).exists())
        self.assertEqual(list(self.feature.publications.values_list('pk', flat=True)),
                         [self.pub.pk])
        messages = [str(m) for m in request._messages]
        self.assertEqual(len(messages), 1, messages)
        self.assertIn('99-01', messages[0])
