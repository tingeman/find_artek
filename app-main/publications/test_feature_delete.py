"""Delete a feature, and all features of a report (plan "features" T7).

- DeleteFeatureView (``delete_feature``: Feature.is_deletable_by): GET is the confirmation
  page (feature, files, images, reports) and changes nothing; POST deletes the feature with
  its files and images. A file or image another feature or report still uses keeps its
  record and file; files are removed only after the commit, and not when another record
  names the same file. Returns to the report named by ``report``.
- DeleteReportFeaturesView (``add_feature`` on the report): features that belong to other
  reports too are only unlinked from this report; features only on this report are deleted
  when the user has ``delete_feature`` on them, otherwise kept and named.

Users from ReportAccessTestBase (roles of migration 0003): author ``dtu_own`` and
supervisor ``staff_own`` of ``pub``, ``dtu_not_own`` and ``staff`` not listed, artek_editor
``editor``. The files are tiny fixtures written to a temporary MEDIA_ROOT.
"""
import datetime
import os
import shutil
import tempfile

from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.test import override_settings
from django.urls import reverse

from publications.models import (
    Appendenciesship, Feature, FileObject, ImageObject, ImageObjectship, Publication,
)
from publications.test_factories import make_user, page_path
from publications.test_report_access import ReportAccessTestBase


class FeatureDeleteTestBase(ReportAccessTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_pub = Publication.objects.create(
            type=cls.pubtype, title='Other report', number='99-02', year=1999, verified=True)

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='find_artek_feature_delete_')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

    # --- fixtures

    def feature(self, name, *pubs):
        feature = Feature.objects.create(name=name, date=datetime.date(1999, 7, 1))
        feature.publications.add(*pubs)
        return feature

    def write(self, relpath):
        full = self.full(relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(b'made-up feature file\n')
        return relpath

    def full(self, relpath):
        return os.path.join(self.media_root, *str(relpath).split('/'))

    def add_file(self, feature, name):
        fileobject = FileObject.objects.create(
            file=self.write(f'reports/1999/99-01/features/{feature.pk}/{name}'))
        feature.files.add(fileobject)
        return fileobject

    def add_image(self, feature, name, caption='Made-up photo'):
        image = ImageObject.objects.create(
            image=self.write(f'reports/1999/99-01/features/{feature.pk}/img/{name}'),
            caption=caption)
        ImageObjectship.objects.create(imageobject=image, feature=feature)
        return image

    # --- assertions

    def assertRecordAndFileGone(self, record):
        self.assertFalse(type(record).objects.filter(pk=record.pk).exists())
        name = record.image.name if isinstance(record, ImageObject) else record.file.name
        self.assertFalse(os.path.exists(self.full(name)), name)

    def assertRecordAndFileKept(self, record):
        self.assertTrue(type(record).objects.filter(pk=record.pk).exists())
        name = record.image.name if isinstance(record, ImageObject) else record.file.name
        self.assertTrue(os.path.exists(self.full(name)), name)

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class DeleteFeatureTests(FeatureDeleteTestBase):

    def path(self, feature, report=None):
        url = page_path('delete_feature', pk=feature.pk)
        return f'{url}?report={report.pk}' if report else url

    def post(self, feature, report=None):
        data = {'report': report.pk} if report else {}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(page_path('delete_feature', pk=feature.pk), data)

    def test_files_and_images_are_deleted(self):
        feature = self.feature('With media', self.pub)
        fileobject = self.add_file(feature, 'data.txt')
        image = self.add_image(feature, 'photo.jpg')
        self.login(self.editor)
        response = self.post(feature, self.pub)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Feature.objects.filter(pk=feature.pk).exists())
        self.assertRecordAndFileGone(fileobject)
        self.assertRecordAndFileGone(image)
        self.assertFalse(ImageObjectship.objects.filter(imageobject_id=image.pk).exists())

    def test_files_are_removed_only_after_the_commit(self):
        feature = self.feature('With media', self.pub)
        fileobject = self.add_file(feature, 'data.txt')
        image = self.add_image(feature, 'photo.jpg')
        self.login(self.editor)
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.client.post(page_path('delete_feature', pk=feature.pk))
        self.assertFalse(FileObject.objects.filter(pk=fileobject.pk).exists())
        self.assertTrue(os.path.exists(self.full(fileobject.file.name)))
        self.assertTrue(os.path.exists(self.full(image.image.name)))
        for callback in callbacks:
            callback()
        self.assertFalse(os.path.exists(self.full(fileobject.file.name)))
        self.assertFalse(os.path.exists(self.full(image.image.name)))

    def test_file_and_image_used_elsewhere_are_kept(self):
        feature = self.feature('Doomed', self.pub)
        neighbour = self.feature('Neighbour', self.pub)
        shared_file = self.add_file(feature, 'shared.txt')
        neighbour.files.add(shared_file)
        appendix_file = self.add_file(feature, 'appendix.txt')
        Appendenciesship.objects.create(publication=self.other_pub, fileobject=appendix_file)
        shared_image = self.add_image(feature, 'shared.jpg')
        ImageObjectship.objects.create(imageobject=shared_image, feature=neighbour)
        own_file = self.add_file(feature, 'own.txt')
        self.login(self.editor)

        page = self.client.get(self.path(feature, self.pub))
        self.assertEqual(dict((f.pk, kept) for f, kept in page.context['files']),
                         {shared_file.pk: True, appendix_file.pk: True, own_file.pk: False})
        self.assertEqual([(i.pk, kept) for i, kept in page.context['images']],
                         [(shared_image.pk, True)])

        self.post(feature, self.pub)
        self.assertFalse(Feature.objects.filter(pk=feature.pk).exists())
        self.assertRecordAndFileKept(shared_file)
        self.assertRecordAndFileKept(appendix_file)
        self.assertRecordAndFileKept(shared_image)
        self.assertRecordAndFileGone(own_file)
        self.assertEqual(list(neighbour.files.all()), [shared_file])
        self.assertEqual(list(neighbour.images.all()), [shared_image])
        self.assertTrue(Appendenciesship.objects.filter(fileobject=appendix_file).exists())

    def test_file_name_used_by_another_record_stays_on_disk(self):
        feature = self.feature('Doomed', self.pub)
        fileobject = self.add_file(feature, 'twin.txt')
        twin = FileObject.objects.create(file=fileobject.file.name)
        image = self.add_image(feature, 'twin.jpg')
        image_twin = ImageObject.objects.create(image=image.image.name, caption='')
        self.login(self.editor)
        self.post(feature)
        self.assertFalse(FileObject.objects.filter(pk=fileobject.pk).exists())
        self.assertFalse(ImageObject.objects.filter(pk=image.pk).exists())
        self.assertRecordAndFileKept(twin)
        self.assertRecordAndFileKept(image_twin)

    def test_missing_file_still_deletes_the_records(self):
        feature = self.feature('Doomed', self.pub)
        fileobject = FileObject.objects.create(file='reports/1999/99-01/never-written.txt')
        feature.files.add(fileobject)
        self.login(self.editor)
        with self.assertLogs('publications.views', level='WARNING') as logs:
            response = self.post(feature)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(FileObject.objects.filter(pk=fileobject.pk).exists())
        self.assertIn('already missing', '\n'.join(logs.output))

    def test_returns_to_the_report_it_was_started_from(self):
        feature = self.feature('On both', self.pub, self.other_pub)
        self.login(self.editor)
        page = self.client.get(self.path(feature, self.other_pub))
        self.assertContains(page, f'name="report" value="{self.other_pub.pk}"')
        self.assertEqual(page.context['cancel_url'],
                         reverse('publications:report', kwargs={'pk': self.other_pub.pk}))
        response = self.post(feature, self.other_pub)
        self.assertRedirects(response,
                             reverse('publications:report', kwargs={'pk': self.other_pub.pk}),
                             fetch_redirect_response=False)

    def test_without_report_returns_to_the_first_report(self):
        feature = self.feature('On both', self.pub, self.other_pub)
        self.login(self.editor)
        response = self.post(feature)
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)

    def test_report_not_of_the_feature_is_ignored(self):
        feature = self.feature('On pub', self.pub)
        self.login(self.editor)
        response = self.post(feature, self.other_pub)
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)

    def test_feature_without_report_returns_to_the_report_list(self):
        feature = self.feature('Orphan')
        self.login(self.editor)
        response = self.post(feature)
        self.assertRedirects(response, reverse('publications:reports'),
                             fetch_redirect_response=False)

    def test_get_lists_everything_and_changes_nothing(self):
        feature = self.feature('Listed feature', self.pub, self.other_pub)
        fileobject = self.add_file(feature, 'listed-data.txt')
        image = self.add_image(feature, 'listed-photo.jpg', caption='Listed caption')
        self.login(self.editor)
        response = self.client.get(self.path(feature, self.pub))
        self.assertEqual(response.status_code, 200)
        for text in ('Listed feature', 'listed-data.txt', 'listed-photo.jpg', 'Listed caption',
                     'Own report', 'Other report'):
            self.assertContains(response, text)
        self.assertTrue(Feature.objects.filter(pk=feature.pk).exists())
        self.assertRecordAndFileKept(fileobject)
        self.assertRecordAndFileKept(image)
        self.assertEqual(feature.publications.count(), 2)

    def test_hidden_reports_are_neither_named_nor_counted(self):
        secret = Publication.objects.create(type=self.pubtype, title='Secret report',
                                            number='99-03', year=1999, confidential=True)
        feature = self.feature('Shared with a secret', self.pub, secret)
        self.login(self.dtu_own)
        response = self.client.get(self.path(feature, self.pub))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('hidden_report_count', response.context)
        self.assertNotContains(response, 'Secret report')
        self.assertNotContains(response, '99-03')
        self.assertNotContains(response, 'cannot see')

    def test_access(self):
        feature = self.feature('Access', self.pub)
        self.assertRedirectsToLogin(self.client.get(self.path(feature)))
        self.assertRedirectsToLogin(self.client.post(self.path(feature)))
        for user in (self.dtu_not_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(self.path(feature)))
                self.assertDenied(self.client.post(self.path(feature)))
        self.assertTrue(Feature.objects.filter(pk=feature.pk).exists())
        for user in (self.dtu_own, self.staff_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertEqual(self.client.get(self.path(feature)).status_code, 200)
        self.login(self.dtu_own)
        self.post(feature)
        self.assertFalse(Feature.objects.filter(pk=feature.pk).exists())
        self.login(self.editor)
        self.assertEqual(self.client.get(page_path('delete_feature', pk=feature.pk)).status_code,
                         404)

    def test_report_page_delete_link_names_the_report(self):
        feature = self.feature('Linked', self.pub)
        self.login(self.editor)
        response = self.client.get(page_path('report', pk=self.pub.pk))
        url = reverse('publications:delete_feature', kwargs={'pk': feature.pk})
        self.assertContains(response, f'{url}?report={self.pub.pk}')


class DeleteReportFeaturesTests(FeatureDeleteTestBase):

    def setUp(self):
        super().setUp()
        self.only_here = self.feature('Only here', self.pub)
        self.only_file = self.add_file(self.only_here, 'only.txt')
        self.only_image = self.add_image(self.only_here, 'only.jpg')
        self.shared = self.feature('Shared', self.pub, self.other_pub)
        self.shared_file = self.add_file(self.shared, 'shared.txt')
        self.elsewhere = self.feature('Elsewhere', self.other_pub)

    def path(self, report=None):
        return page_path('delete_report_features', pk=(report or self.pub).pk)

    def confirm(self, report=None):
        """GET the confirmation page and POST what it lists, as the browser does."""
        page = self.client.get(self.path(report))
        self.assertEqual(page.status_code, 200)
        data = {'delete': [f.pk for f in page.context['to_delete']],
                'unlink': [f.pk for f in page.context['to_unlink']]}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.path(report), data)

    def assertUntouched(self):
        self.assertEqual(set(Feature.objects.filter(publications=self.pub)),
                         {self.only_here, self.shared})
        self.assertRecordAndFileKept(self.only_file)
        self.assertRecordAndFileKept(self.only_image)

    def test_editor_deletes_and_unlinks(self):
        self.login(self.editor)
        response = self.confirm()
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': self.pub.pk}),
                             fetch_redirect_response=False)
        self.assertFalse(Feature.objects.filter(pk=self.only_here.pk).exists())
        self.assertRecordAndFileGone(self.only_file)
        self.assertRecordAndFileGone(self.only_image)
        # The shared feature stays on the other report, with its file.
        self.shared.refresh_from_db()
        self.assertEqual(list(self.shared.publications.all()), [self.other_pub])
        self.assertRecordAndFileKept(self.shared_file)
        self.assertEqual(list(self.shared.files.all()), [self.shared_file])
        self.assertTrue(Feature.objects.filter(pk=self.elsewhere.pk).exists())
        self.assertFalse(Feature.objects.filter(publications=self.pub).exists())
        self.assertEqual(self.messages(response),
                         ['Report 99-01: 1 feature(s) deleted; 1 feature(s) that belong to '
                          'other reports too removed from this report.'])

    def test_listed_author_deletes_and_unlinks(self):
        self.login(self.dtu_own)
        self.confirm()
        self.assertFalse(Feature.objects.filter(pk=self.only_here.pk).exists())
        self.assertEqual(list(self.shared.publications.all()), [self.other_pub])

    def test_user_who_may_add_but_not_delete_keeps_the_feature(self):
        # May edit every report (change_publication) and so add features to this one, but
        # is not listed on it: delete_own_feature does not cover "Only here". The stock
        # roles never give this combination; it is the case design note 3 guards against.
        helper = make_user('s990777')
        helper.user_permissions.add(Permission.objects.get(
            codename='change_publication', content_type__app_label='publications'))
        self.login(helper)
        page = self.client.get(self.path())
        self.assertEqual(page.context['kept'], [self.only_here])
        self.assertEqual(page.context['to_unlink'], [self.shared])
        self.assertEqual(page.context['to_delete'], [])
        self.assertContains(page, 'Kept: you may not delete these features')
        self.assertContains(page, 'Only here')
        response = self.confirm()
        self.assertTrue(Feature.objects.filter(pk=self.only_here.pk,
                                               publications=self.pub).exists())
        self.assertRecordAndFileKept(self.only_file)
        self.assertRecordAndFileKept(self.only_image)
        self.assertEqual(list(self.shared.publications.all()), [self.other_pub])
        self.assertIn('1 feature(s) kept, you may not delete them: "Only here".',
                      self.messages(response))

    def test_get_changes_nothing(self):
        self.login(self.editor)
        response = self.client.get(self.path())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['to_delete'], [self.only_here])
        self.assertEqual(response.context['to_unlink'], [self.shared])
        self.assertEqual(response.context['kept'], [])
        self.assertUntouched()
        self.assertEqual(self.shared.publications.count(), 2)

    def test_only_the_confirmed_features_are_touched(self):
        self.login(self.editor)
        page = self.client.get(self.path())
        late = self.feature('Added after the confirmation page', self.pub)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.path(), {
                'delete': [f.pk for f in page.context['to_delete']],
                # a feature listed for unlinking must not be deleted, and vice versa
                'unlink': [self.only_here.pk]})
        self.assertFalse(Feature.objects.filter(pk=self.only_here.pk).exists())
        self.assertTrue(Feature.objects.filter(pk=late.pk, publications=self.pub).exists())
        self.assertEqual(self.shared.publications.count(), 2)

    def test_post_without_confirmed_features_changes_nothing(self):
        self.login(self.editor)
        response = self.client.post(self.path())
        self.assertEqual(response.status_code, 302)
        self.assertUntouched()
        self.assertEqual(self.messages(response),
                         ['Report 99-01: no feature was deleted or removed.'])

    def test_report_without_features(self):
        empty = Publication.objects.create(type=self.pubtype, title='Empty report',
                                           number='99-04', year=1999)
        self.login(self.editor)
        response = self.client.get(self.path(empty))
        self.assertContains(response, 'This report has no features.')

    def test_access(self):
        for method in ('get', 'post'):
            with self.subTest(user='anonymous', method=method):
                self.assertRedirectsToLogin(getattr(self.client, method)(self.path()))
        # Not listed on pub (dtu_user and artek_staff): may not edit it, so may not add.
        for user in (self.dtu_not_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.client.get(self.path()))
                self.assertDenied(self.client.post(self.path(), {
                    'delete': [self.only_here.pk], 'unlink': [self.shared.pk]}))
        self.assertUntouched()
        for user in (self.dtu_own, self.staff_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertEqual(self.client.get(self.path()).status_code, 200)
        self.login(self.editor)
        self.assertEqual(self.client.get(page_path(
            'delete_report_features', pk=self.other_pub.pk + 1000)).status_code, 404)

    def test_report_page_link(self):
        link = reverse('publications:delete_report_features', kwargs={'pk': self.pub.pk})
        for user, shown in ((self.dtu_not_own, False), (self.dtu_own, True),
                            (self.editor, True)):
            with self.subTest(user=getattr(user, 'username', 'anonymous')):
                if user is None:
                    self.client.logout()
                else:
                    self.login(user)
                response = self.client.get(page_path('report', pk=self.pub.pk))
                self.assertEqual(response.status_code, 200)
                if shown:
                    self.assertContains(response, link)
                    self.assertContains(response, 'Delete all features')
                else:
                    self.assertNotContains(response, link)

    def test_no_link_when_the_report_has_no_features(self):
        empty = Publication.objects.create(type=self.pubtype, title='Empty report',
                                           number='99-04', year=1999)
        self.login(self.editor)
        response = self.client.get(page_path('report', pk=empty.pk))
        self.assertNotContains(response, 'Delete all features')
