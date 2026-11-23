"""Small fixes from the browser checks (plan "features" T15).

- Return target: "Edit coordinates" and "Edit on map" started from the feature page carry
  ``next=feature`` (query string, then a hidden field, also through the warning confirm
  page) and return to the feature page, with ``?report=`` only if the page had one. Started
  from the report page they return to the report as before. ``next`` is a fixed flag: any
  other value (a URL) is ignored, so there is no open redirect. Adding a feature still
  returns to the report.
- Feature page: the reports the feature belongs to that the user may see, with number,
  title and link; hidden reports are neither named nor counted; no row without any.
- "Delete all features" confirm page: each feature links to its page (``?report=``) and
  shows its number of files and images.
- Coordinate form: the EPSG list has the light blue box of the help text.
- Empty folders: after a feature's file or image, or the feature, is deleted, the folders
  then empty inside ``reports/<year>/<number>/features/<id>/`` (the folder itself included)
  are removed; folders that still hold anything and folders above it stay.

Every file is a tiny fixture written to a temporary MEDIA_ROOT; never real media.
"""
import datetime
import os

from django.contrib.auth.models import Permission
from django.contrib.gis.geos import LineString, MultiLineString, MultiPoint, Point
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape

from publications.models import Feature, Publication
from publications.test_factories import make_user, page_path
from publications.test_feature_coordinates import form_data
from publications.test_feature_delete import FeatureDeleteTestBase
from publications.test_feature_map_edit import POINT, FeatureMapTestBase, attributes, collection
from publications.test_feature_media import FeatureMediaTestBase, png_upload, text_upload
from publications.utils_models import (
    feature_media_root, remove_empty_dirs_below, remove_empty_feature_dirs,
)

DAY = datetime.date(2003, 8, 1)


def feature_page(feature, report=None):
    url = reverse('publications:feature', kwargs={'pk': feature.pk})
    return url if report is None else f'{url}?report={report.pk}'


def report_page(report):
    return reverse('publications:report', kwargs={'pk': report.pk})


class ReturnTargetTestBase(FeatureMapTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.point = Feature.objects.create(
            name='One point', type=Feature.SAMPLE, date=DAY, pos_quality='GPS (phase)',
            points=MultiPoint(Point(-50.5, 67.0), srid=4326))
        cls.point.publications.add(cls.pub, cls.public_pub)
        cls.line = Feature.objects.create(
            name='Line', date=DAY,
            lines=MultiLineString(LineString((-50, 67), (-51, 68)), srid=4326))
        cls.line.publications.add(cls.pub)
        cls.unrelated = Publication.objects.create(
            type=cls.pubtype, title='Unrelated report', number='99-07', year=1999,
            verified=True)

    def coords_path(self, feature, query=''):
        return page_path('edit_feature_coordinates', pk=feature.pk) + query

    def map_path(self, feature, query=''):
        return page_path('edit_feature_by_map', pk=feature.pk) + query

    def coords_data(self, x=-50.5, y=67.0, **extra):
        return form_data(x, y, 4326, name=self.point.name, **extra)

    def map_data(self, **extra):
        return dict(attributes(self.point.name), geojson_data=collection(POINT), **extra)


class FeaturePageEditLinkTests(ReturnTargetTestBase):

    def test_edit_links_carry_the_flag(self):
        self.login(self.editor)
        response = self.client.get(page_path('feature', pk=self.point.pk))
        coords = reverse('publications:edit_feature_coordinates', kwargs={'pk': self.point.pk})
        edit = reverse('publications:edit_feature_by_map', kwargs={'pk': self.point.pk})
        self.assertContains(response, f'href="{coords}?next=feature"')
        self.assertContains(response, f'href="{edit}?next=feature"')

    def test_edit_links_keep_the_report_of_the_page(self):
        self.login(self.editor)
        response = self.client.get(
            page_path('feature', pk=self.point.pk) + f'?report={self.public_pub.pk}')
        coords = reverse('publications:edit_feature_coordinates', kwargs={'pk': self.point.pk})
        edit = reverse('publications:edit_feature_by_map', kwargs={'pk': self.point.pk})
        query = escape(f'?next=feature&report={self.public_pub.pk}')
        self.assertContains(response, f'href="{coords}{query}"')
        self.assertContains(response, f'href="{edit}{query}"')


class EditCoordinatesReturnTests(ReturnTargetTestBase):

    def test_from_the_feature_page_returns_there(self):
        self.login(self.editor)
        response = self.client.get(self.coords_path(self.point, '?next=feature'))
        self.assertEqual(response.context['cancel_url'], feature_page(self.point))
        self.assertContains(response, '<input type="hidden" name="next" value="feature">')
        # The page had no report: none is added.
        self.assertNotContains(response, 'name="report"')
        response = self.client.post(self.coords_path(self.point),
                                    self.coords_data(next='feature'))
        self.assertRedirects(response, feature_page(self.point), fetch_redirect_response=False)

    def test_from_the_feature_page_keeps_the_report(self):
        self.login(self.editor)
        response = self.client.get(
            self.coords_path(self.point, f'?next=feature&report={self.public_pub.pk}'))
        self.assertEqual(response.context['cancel_url'],
                         feature_page(self.point, self.public_pub))
        self.assertContains(response,
                            f'<input type="hidden" name="report" value="{self.public_pub.pk}">')
        response = self.client.post(self.coords_path(self.point), self.coords_data(
            next='feature', report=self.public_pub.pk))
        self.assertRedirects(response, feature_page(self.point, self.public_pub),
                             fetch_redirect_response=False)

    def test_through_the_confirm_page(self):
        self.login(self.editor)
        data = self.coords_data(x=12.5, y=55.7, next='feature', report=self.pub.pk)
        response = self.client.post(self.coords_path(self.point), data)
        self.assertTemplateUsed(response, 'publications/feature_coordinates_confirm.html')
        self.assertContains(response, '<input type="hidden" name="next" value="feature">')
        self.assertContains(response, f'<input type="hidden" name="report" value="{self.pub.pk}">')
        self.assertEqual(response.context['cancel_url'], feature_page(self.point, self.pub))
        response = self.client.post(self.coords_path(self.point),
                                    dict(data, confirm_warnings='1'))
        self.assertRedirects(response, feature_page(self.point, self.pub),
                             fetch_redirect_response=False)
        self.assertEqual(Feature.objects.get(pk=self.point.pk).points.coords, ((12.5, 55.7),))

    def test_from_the_report_page_returns_to_the_report(self):
        self.login(self.editor)
        response = self.client.get(self.coords_path(self.point, f'?report={self.public_pub.pk}'))
        self.assertNotContains(response, 'name="next"')
        data = self.coords_data(x=12.5, y=55.7, report=self.public_pub.pk)
        response = self.client.post(self.coords_path(self.point), data)
        self.assertNotContains(response, 'name="next"')   # confirm page
        response = self.client.post(self.coords_path(self.point),
                                    dict(data, confirm_warnings='1'))
        self.assertRedirects(response, report_page(self.public_pub),
                             fetch_redirect_response=False)

    def test_no_open_redirect(self):
        self.login(self.editor)
        for value in ('https://evil.example/', '//evil.example/', '/find/reports/',
                      'Feature', 'feature/'):
            with self.subTest(next=value):
                response = self.client.get(self.coords_path(self.point, f'?next={value}'))
                self.assertEqual(response.context['cancel_url'], report_page(self.pub))
                response = self.client.post(self.coords_path(self.point), self.coords_data(
                    next=value, report=self.pub.pk))
                self.assertRedirects(response, report_page(self.pub),
                                     fetch_redirect_response=False)

    def test_report_not_of_the_feature_is_dropped(self):
        self.login(self.editor)
        response = self.client.post(self.coords_path(self.point), self.coords_data(
            next='feature', report=self.unrelated.pk))
        self.assertRedirects(response, feature_page(self.point), fetch_redirect_response=False)

    def test_redirect_to_the_map_edit_keeps_the_flag(self):
        self.login(self.editor)
        map_edit = reverse('publications:edit_feature_by_map', kwargs={'pk': self.line.pk})
        response = self.client.get(self.coords_path(self.line, '?next=feature'))
        self.assertRedirects(response, f'{map_edit}?next=feature',
                             fetch_redirect_response=False)
        response = self.client.get(
            self.coords_path(self.line, f'?next=feature&report={self.pub.pk}'))
        self.assertRedirects(response, f'{map_edit}?report={self.pub.pk}&next=feature',
                             fetch_redirect_response=False)

    def test_adding_a_feature_still_returns_to_the_report(self):
        self.login(self.editor)
        path = page_path('add_feature_coordinates', report_pk=self.pub.pk)
        response = self.client.post(path, form_data(-50.5, 67.0, 4326, name='Added',
                                                    next='feature'))
        self.assertRedirects(response, report_page(self.pub), fetch_redirect_response=False)
        path = page_path('add_feature_by_map', report_pk=self.pub.pk)
        response = self.client.post(path, dict(attributes('Drawn'), next='feature',
                                               geojson_data=collection(POINT)))
        self.assertRedirects(response, report_page(self.pub), fetch_redirect_response=False)


class EditOnMapReturnTests(ReturnTargetTestBase):

    def test_from_the_feature_page_returns_there(self):
        self.login(self.editor)
        response = self.client.get(self.map_path(self.point, '?next=feature'))
        self.assertEqual(response.context['cancel_url'], feature_page(self.point))
        self.assertContains(response, '<input type="hidden" name="next" value="feature">')
        response = self.client.post(self.map_path(self.point), self.map_data(next='feature'))
        self.assertRedirects(response, feature_page(self.point), fetch_redirect_response=False)

    def test_from_the_feature_page_keeps_the_report(self):
        self.login(self.editor)
        response = self.client.post(self.map_path(self.point), self.map_data(
            next='feature', report=self.public_pub.pk))
        self.assertRedirects(response, feature_page(self.point, self.public_pub),
                             fetch_redirect_response=False)

    def test_from_the_report_page_returns_to_the_report(self):
        self.login(self.editor)
        response = self.client.get(self.map_path(self.point, f'?report={self.public_pub.pk}'))
        self.assertNotContains(response, 'name="next"')
        response = self.client.post(self.map_path(self.point),
                                    self.map_data(report=self.public_pub.pk))
        self.assertRedirects(response, report_page(self.public_pub),
                             fetch_redirect_response=False)

    def test_no_open_redirect(self):
        self.login(self.editor)
        for value in ('https://evil.example/', '//evil.example/'):
            with self.subTest(next=value):
                response = self.client.post(self.map_path(self.point), self.map_data(
                    next=value, report=self.pub.pk))
                self.assertRedirects(response, report_page(self.pub),
                                     fetch_redirect_response=False)


class FeaturePageReportsTests(FeatureMapTestBase):
    """cls.pub ('Own report', unverified) is hidden from anonymous users; cls.public_pub
    ('Public report') is visible to everyone."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.shared = Feature.objects.create(name='On two reports', date=DAY)
        cls.shared.publications.add(cls.pub, cls.public_pub)
        cls.orphan = Feature.objects.create(name='On no report', date=DAY)

    def test_all_visible_reports_are_listed_with_links(self):
        self.login(self.editor)
        response = self.client.get(page_path('feature', pk=self.shared.pk))
        self.assertContains(response, 'id="feature-reports"')
        for report in (self.pub, self.public_pub):
            self.assertContains(response, f'href="{report_page(report)}"')
            self.assertContains(response, report.number)
            self.assertContains(response, report.title)
        self.assertContains(response, '<span class="property">Reports</span>', html=True)

    def test_hidden_report_is_neither_named_nor_counted(self):
        self.client.logout()
        response = self.client.get(page_path('feature', pk=self.shared.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{report_page(self.public_pub)}"')
        self.assertContains(response, 'Public report')
        self.assertNotContains(response, f'href="{report_page(self.pub)}"')
        self.assertNotContains(response, 'Own report')
        # One visible report: singular label, nothing counts the hidden one.
        self.assertContains(response, '<span class="property">Report</span>', html=True)
        self.assertNotContains(response, '<span class="property">Reports</span>', html=True)
        self.assertEqual(list(response.context['visible_reports']), [self.public_pub])

    def test_no_row_without_visible_reports(self):
        self.login(self.editor)
        response = self.client.get(page_path('feature', pk=self.orphan.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="feature-reports"')


class DeleteAllConfirmPageTests(FeatureDeleteTestBase):

    def setUp(self):
        super().setUp()
        self.with_media = self.feature('With media', self.pub)
        self.add_file(self.with_media, 'one.txt')
        self.add_file(self.with_media, 'two.txt')
        self.add_image(self.with_media, 'photo.jpg')
        self.shared = self.feature('Shared', self.pub, self.other_pub)
        self.add_image(self.shared, 'a.jpg')
        self.add_image(self.shared, 'b.jpg')
        self.bare = self.feature('Bare', self.pub)

    def test_features_link_to_their_page_with_counts(self):
        self.login(self.editor)
        response = self.client.get(page_path('delete_report_features', pk=self.pub.pk))
        self.assertEqual(response.status_code, 200)
        for feature in (self.with_media, self.shared, self.bare):
            self.assertContains(response, f'href="{feature_page(feature, self.pub)}"')
        self.assertContains(response, '2 files, 1 image')
        self.assertContains(response, '0 files, 2 images')
        self.assertContains(response, '0 files, 0 images')
        counts = {f.pk: (f.file_count, f.image_count)
                  for f in response.context['to_delete'] + response.context['to_unlink']}
        self.assertEqual(counts, {self.with_media.pk: (2, 1), self.shared.pk: (0, 2),
                                  self.bare.pk: (0, 0)})

    def test_kept_features_link_too(self):
        # May add features to the report (change_publication) but is not listed on it, so
        # may not delete "With media" and "Bare" (as test_feature_delete).
        helper = make_user('s990777')
        helper.user_permissions.add(Permission.objects.get(
            codename='change_publication', content_type__app_label='publications'))
        self.login(helper)
        response = self.client.get(page_path('delete_report_features', pk=self.pub.pk))
        self.assertEqual(response.context['kept'], [self.bare, self.with_media])
        self.assertContains(response, f'href="{feature_page(self.with_media, self.pub)}"')
        self.assertContains(response, '2 files, 1 image')

    def test_counts_add_no_query_per_feature(self):
        # Files and images added to the features do not change the number of queries, and
        # neither do more features for the editor (counts annotated in one query).
        self.login(self.editor)
        path = page_path('delete_report_features', pk=self.pub.pk)
        self.client.get(path)
        with CaptureQueriesContext(connection) as before:
            self.client.get(path)
        for i in range(4):
            feature = self.feature(f'Extra {i}', self.pub)
            self.add_file(feature, f'extra{i}.txt')
            self.add_image(feature, f'extra{i}.jpg')
            self.add_file(self.bare, f'bare{i}.txt')
        with CaptureQueriesContext(connection) as after:
            response = self.client.get(path)
        self.assertContains(response, '4 files, 0 images')
        self.assertEqual(len(after), len(before),
                         [q['sql'] for q in after.captured_queries])


class SridListStyleTests(FeatureMapTestBase):

    def test_epsg_list_has_the_help_box_style(self):
        self.login(self.editor)
        for path in (page_path('add_feature_coordinates', report_pk=self.pub.pk),):
            response = self.client.get(path)
            self.assertContains(
                response, '<details class="mt-2 mb-0 alert alert-info srid-help-box" '
                          'id="srid-help">')
            # The same classes as the help box of the page.
            self.assertContains(response, '<div class="alert alert-info coordinate-help">')


class EmptyFolderMediaTests(FeatureMediaTestBase):
    """Delete a feature's file or image (DeleteFeatureMediaView)."""

    def uploaded(self, feature, kind, upload):
        self.login(self.editor)
        self.upload(feature, kind, [upload], self.pub)
        return (feature.images if kind == 'image' else feature.files).latest('pk')

    def post_delete(self, feature, kind, record):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                page_path(f'delete_feature_{kind}', pk=feature.pk, record_pk=record.pk),
                {'report': self.pub.pk})

    def test_file_delete_removes_the_empty_feature_folder(self):
        feature = self.feature('Feature', self.pub)
        fileobject = self.uploaded(feature, 'file', text_upload())
        folder = self.full(self.feature_dir(feature))
        self.assertTrue(os.path.isdir(folder))
        self.post_delete(feature, 'file', fileobject)
        self.assertFalse(os.path.exists(folder))
        # Never above the feature folder.
        self.assertTrue(os.path.isdir(self.full('reports/1999/99-01/features')))

    def test_image_delete_removes_img_thumbs_and_the_feature_folder(self):
        feature = self.feature('Feature', self.pub)
        image = self.uploaded(feature, 'image', png_upload())
        folder = self.full(self.feature_dir(feature))
        self.assertTrue(os.path.isdir(os.path.join(folder, 'img', 'thumbs')))
        self.post_delete(feature, 'image', image)
        self.assertFalse(os.path.exists(folder))
        self.assertTrue(os.path.isdir(self.full('reports/1999/99-01/features')))

    def test_folders_that_still_hold_files_stay(self):
        feature = self.feature('Feature', self.pub)
        fileobject = self.uploaded(feature, 'file', text_upload())
        image = self.uploaded(feature, 'image', png_upload())
        other_image = self.uploaded(feature, 'image', png_upload('other.png'))
        folder = self.full(self.feature_dir(feature))
        self.post_delete(feature, 'image', image)
        # img/ and thumbs/ still hold the other image.
        self.assertTrue(os.path.isfile(self.full(other_image.image.name)))
        self.assertTrue(os.path.isdir(os.path.join(folder, 'img', 'thumbs')))
        self.post_delete(feature, 'image', other_image)
        # img/ is gone, the feature folder still holds the file.
        self.assertFalse(os.path.exists(os.path.join(folder, 'img')))
        self.assertTrue(os.path.isfile(self.full(fileobject.file.name)))
        self.post_delete(feature, 'file', fileobject)
        self.assertFalse(os.path.exists(folder))

    def test_file_delete_keeps_a_folder_with_an_image(self):
        feature = self.feature('Feature', self.pub)
        fileobject = self.uploaded(feature, 'file', text_upload())
        self.uploaded(feature, 'image', png_upload())
        folder = self.full(self.feature_dir(feature))
        self.post_delete(feature, 'file', fileobject)
        self.assertTrue(os.path.isdir(os.path.join(folder, 'img', 'thumbs')))

    def test_shared_file_is_kept_with_its_folder(self):
        feature = self.feature('Feature', self.pub)
        other = self.feature('Other', self.pub)
        fileobject = self.uploaded(feature, 'file', text_upload())
        other.files.add(fileobject)
        self.post_delete(feature, 'file', fileobject)
        self.assertTrue(os.path.isfile(self.full(fileobject.file.name)))


class EmptyFolderFeatureDeleteTests(FeatureDeleteTestBase):
    """Delete the whole feature (_delete_feature: DeleteFeatureView, DeleteReportFeaturesView)."""

    def post_delete(self, feature):
        self.login(self.editor)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(page_path('delete_feature', pk=feature.pk),
                                    {'report': self.pub.pk})

    def folder(self, feature):
        return self.full(f'reports/1999/99-01/features/{feature.pk}')

    def test_feature_delete_removes_its_folders(self):
        feature = self.feature('With media', self.pub)
        self.add_file(feature, 'data.txt')
        self.add_image(feature, 'photo.jpg')
        os.makedirs(os.path.join(self.folder(feature), 'img', 'thumbs'))   # empty, from before
        folder = self.folder(feature)
        self.post_delete(feature)
        self.assertFalse(os.path.exists(folder))
        self.assertTrue(os.path.isdir(self.full('reports/1999/99-01/features')))

    def test_feature_without_files_removes_left_over_empty_folders(self):
        feature = self.feature('Bare', self.pub)
        os.makedirs(os.path.join(self.folder(feature), 'img', 'thumbs'))
        folder = self.folder(feature)
        self.post_delete(feature)
        self.assertFalse(os.path.exists(folder))

    def test_folder_with_a_file_still_in_use_stays(self):
        feature = self.feature('With media', self.pub)
        other = self.feature('Other', self.pub)
        fileobject = self.add_file(feature, 'data.txt')
        image = self.add_image(feature, 'photo.jpg')
        other.files.add(fileobject)      # still used: record and file stay
        folder = self.folder(feature)
        self.post_delete(feature)
        self.assertTrue(os.path.isfile(self.full(fileobject.file.name)))
        self.assertFalse(os.path.exists(self.full(image.image.name)))
        self.assertFalse(os.path.exists(os.path.join(folder, 'img')))
        self.assertTrue(os.path.isdir(folder))

    def test_unknown_files_in_the_folder_are_kept(self):
        feature = self.feature('With media', self.pub)
        self.add_file(feature, 'data.txt')
        stray = self.write(f'reports/1999/99-01/features/{feature.pk}/img/stray.txt')
        self.post_delete(feature)
        self.assertTrue(os.path.isfile(self.full(stray)))

    def test_other_features_folders_are_untouched(self):
        feature = self.feature('Deleted', self.pub)
        self.add_file(feature, 'data.txt')
        neighbour = self.feature('Neighbour', self.pub)
        empty_neighbour = os.path.join(self.folder(neighbour), 'img', 'thumbs')
        os.makedirs(empty_neighbour)
        self.post_delete(feature)
        self.assertTrue(os.path.isdir(empty_neighbour))

    def test_delete_all_features_removes_the_folders(self):
        feature = self.feature('Only here', self.pub)
        self.add_file(feature, 'only.txt')
        self.add_image(feature, 'only.jpg')
        folder = self.folder(feature)
        self.login(self.editor)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(page_path('delete_report_features', pk=self.pub.pk),
                             {'delete': [feature.pk]})
        self.assertFalse(Feature.objects.filter(pk=feature.pk).exists())
        self.assertFalse(os.path.exists(folder))


class EmptyFolderHelperTests(FeatureDeleteTestBase):
    """utils_models.feature_media_root / remove_empty_feature_dirs / remove_empty_dirs_below
    directly: they never leave the feature's folder."""

    def test_feature_media_root(self):
        root = os.path.realpath(self.media_root)
        expected = os.path.join(root, 'reports', '1999', '99-01', 'features', '7')
        self.assertEqual(feature_media_root(
            self.full('reports/1999/99-01/features/7/img/thumbs/x.jpg'), 7), expected)
        self.assertEqual(feature_media_root(
            self.full('reports/1999/99-01/features/7/x.txt'), 7), expected)
        for path, pk in [
                (self.full('reports/1999/99-01/features/8/x.txt'), 7),    # other feature
                (self.full('reports/1999/99-01/features/x.txt'), 7),      # above
                (self.full('reports/1999/99-01/x.pdf'), 7),
                (self.full('features/99-01/x.txt'), 7),                    # legacy place
                (self.full('reports/19x9/99-01/features/7/x.txt'), 7),    # no year
                (os.path.join(os.path.dirname(root), 'reports', '1999', '99-01', 'features',
                              '7', 'x.txt'), 7)]:                          # outside
            with self.subTest(path=path):
                self.assertIsNone(feature_media_root(path, pk))

    def test_walk_stops_at_the_feature_folder(self):
        features = self.full('reports/1999/99-01/features')
        thumbs = os.path.join(features, '7', 'img', 'thumbs')
        os.makedirs(thumbs)
        remove_empty_feature_dirs(os.path.join(thumbs, 'gone.jpg'), 7)
        self.assertFalse(os.path.exists(os.path.join(features, '7')))
        self.assertTrue(os.path.isdir(features))   # empty, but above the feature folder

    def test_walk_stops_at_a_non_empty_folder(self):
        img = self.full('reports/1999/99-01/features/7/img')
        os.makedirs(os.path.join(img, 'thumbs'))
        kept = self.write('reports/1999/99-01/features/7/img/kept.jpg')
        remove_empty_feature_dirs(os.path.join(img, 'thumbs', 'gone.jpg'), 7)
        self.assertFalse(os.path.exists(os.path.join(img, 'thumbs')))
        self.assertTrue(os.path.isfile(self.full(kept)))

    def test_nothing_happens_outside_a_folder_of_the_feature(self):
        other = self.full('reports/1999/99-01/features/8/img')
        os.makedirs(other)
        remove_empty_feature_dirs(os.path.join(other, 'x.jpg'), 7)
        self.assertTrue(os.path.isdir(other))
        legacy = self.full('features/99-01')
        os.makedirs(legacy)
        remove_empty_feature_dirs(os.path.join(legacy, 'x.jpg'), 7)
        self.assertTrue(os.path.isdir(legacy))

    def test_sweep_keeps_non_empty_folders(self):
        folder = self.full('reports/1999/99-01/features/7')
        os.makedirs(os.path.join(folder, 'img', 'thumbs'))
        os.makedirs(os.path.join(folder, 'empty'))
        kept = self.write('reports/1999/99-01/features/7/kept.txt')
        remove_empty_dirs_below(folder)
        self.assertFalse(os.path.exists(os.path.join(folder, 'img')))
        self.assertFalse(os.path.exists(os.path.join(folder, 'empty')))
        self.assertTrue(os.path.isfile(self.full(kept)))
        remove_empty_dirs_below(self.full('reports/1999/99-01/features/404'))   # missing: no error
