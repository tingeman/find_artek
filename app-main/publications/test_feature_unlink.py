"""Remove a shared feature from one report on its delete page (plan "features" T14).

DeleteFeatureView with ``action=unlink``: a feature that belongs to more than one report
cannot be deleted (T7a), but it can be removed from the report named by ``report`` when the
user may see that report and has ``add_feature`` on it (the rule of
DeleteReportFeaturesView). Only that link goes; the feature, its other links, its files and
images stay. Hidden (confidential) reports are never named or counted.

Users from ReportAccessTestBase: author ``dtu_own`` and supervisor ``staff_own`` of ``pub``
(not listed on ``other_pub``), artek_editor ``editor``.
"""
from django.contrib.auth.models import Permission
from django.urls import reverse

from publications.models import Feature, Publication
from publications.test_factories import make_user, page_path
from publications.test_feature_delete import FeatureDeleteTestBase

ALERT_ID = 'id="delete-feature-shared"'
BUTTON_ID = 'id="unlink-feature"'


class UnlinkFeatureTests(FeatureDeleteTestBase):

    def path(self, feature, report=None):
        url = page_path('delete_feature', pk=feature.pk)
        return f'{url}?report={report.pk}' if report else url

    def unlink(self, feature, report=None, report_pk=None):
        data = {'action': 'unlink'}
        if report is not None:
            data['report'] = report.pk
        elif report_pk is not None:
            data['report'] = report_pk
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(page_path('delete_feature', pk=feature.pk), data)

    def report_url(self, report):
        return reverse('publications:report', kwargs={'pk': report.pk})

    def secret_report(self, number='99-05'):
        return Publication.objects.create(type=self.pubtype, title='Secret report',
                                          number=number, year=1999, confidential=True)

    def assertUnchanged(self, feature, reports):
        self.assertTrue(Feature.objects.filter(pk=feature.pk).exists())
        self.assertEqual(set(feature.publications.all()), set(reports))

    # --- the remove button

    def test_button_shown_with_add_feature_on_the_report(self):
        feature = self.feature('On both', self.pub, self.other_pub)
        for user in (self.dtu_own, self.editor):
            with self.subTest(user=user.username):
                self.login(user)
                response = self.client.get(self.path(feature, self.pub))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['unlink_report'], self.pub)
                self.assertContains(response, BUTTON_ID)
                self.assertContains(response, 'Remove from report 99-01')
                self.assertContains(response, 'name="action" value="unlink"')
                self.assertContains(response, f'name="report" value="{self.pub.pk}"')
                self.assertContains(response, ALERT_ID)
                self.assertContains(response, 'You can remove it from report')
                self.assertNotContains(response, 'Yes, delete feature')
        self.assertUnchanged(feature, [self.pub, self.other_pub])

    def test_no_button_without_add_feature_on_the_report(self):
        # dtu_own may delete the feature (listed on pub) but is not listed on other_pub.
        feature = self.feature('On both', self.pub, self.other_pub)
        self.login(self.dtu_own)
        response = self.client.get(self.path(feature, self.other_pub))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['unlink_report'])
        self.assertNotContains(response, BUTTON_ID)
        self.assertContains(response, ALERT_ID)
        self.assertContains(response, 'open this page from the report it should be removed from')

    def test_no_button_without_a_usable_report(self):
        not_its_report = Publication.objects.create(
            type=self.pubtype, title='Unrelated report', number='99-06', year=1999,
            verified=True)
        feature = self.feature('On both', self.pub, self.other_pub)
        self.login(self.editor)
        for query in ('', f'?report={not_its_report.pk}', '?report=abc'):
            with self.subTest(query=query):
                response = self.client.get(page_path('delete_feature', pk=feature.pk) + query)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context['unlink_report'])
                self.assertNotContains(response, BUTTON_ID)
                # The visible reports of the feature are linked to their report pages.
                self.assertContains(response, 'id="delete-feature-shared-reports"')
                self.assertContains(response, f'href="{self.report_url(self.pub)}"')
                self.assertContains(response, f'href="{self.report_url(self.other_pub)}"')

    def test_not_shared_page_is_unchanged(self):
        feature = self.feature('Only here', self.pub)
        self.login(self.editor)
        response = self.client.get(self.path(feature, self.pub))
        self.assertFalse(response.context['shared'])
        self.assertContains(response, 'Yes, delete feature')
        self.assertContains(response, 'This cannot be undone.')
        self.assertNotContains(response, BUTTON_ID)
        self.assertNotContains(response, ALERT_ID)

    # --- POST action=unlink

    def test_unlink_removes_only_that_link(self):
        third = Publication.objects.create(type=self.pubtype, title='Third report',
                                           number='99-07', year=1999, verified=True)
        feature = self.feature('On three', self.pub, self.other_pub, third)
        fileobject = self.add_file(feature, 'kept.txt')
        image = self.add_image(feature, 'kept.jpg')
        self.login(self.editor)
        response = self.unlink(feature, self.other_pub)
        self.assertRedirects(response, self.report_url(self.other_pub),
                             fetch_redirect_response=False)
        self.assertUnchanged(feature, [self.pub, third])
        self.assertEqual(list(feature.files.all()), [fileobject])
        self.assertEqual(list(feature.images.all()), [image])
        self.assertRecordAndFileKept(fileobject)
        self.assertRecordAndFileKept(image)
        self.assertIn('Feature "On three" was removed from report 99-02; it stays on the other '
                      'report(s) it belongs to.', self.messages(response))

    def test_listed_author_unlinks_from_own_report(self):
        feature = self.feature('On both', self.pub, self.other_pub)
        self.login(self.dtu_own)
        response = self.unlink(feature, self.pub)
        self.assertRedirects(response, self.report_url(self.pub), fetch_redirect_response=False)
        self.assertUnchanged(feature, [self.other_pub])

    def test_refused_without_add_feature_on_the_report(self):
        feature = self.feature('On both', self.pub, self.other_pub)
        self.login(self.dtu_own)
        response = self.unlink(feature, self.other_pub)
        self.assertEqual(response.status_code, 302)
        self.assertUnchanged(feature, [self.pub, self.other_pub])
        self.assertTrue(any('was not removed' in m for m in self.messages(response)))

    def test_refused_without_a_usable_report(self):
        not_its_report = Publication.objects.create(
            type=self.pubtype, title='Unrelated report', number='99-06', year=1999,
            verified=True)
        feature = self.feature('On both', self.pub, self.other_pub)
        self.login(self.editor)
        for report_pk in (None, not_its_report.pk, 'abc', 999999):
            with self.subTest(report=report_pk):
                response = self.unlink(feature, report_pk=report_pk)
                self.assertEqual(response.status_code, 302)
                self.assertUnchanged(feature, [self.pub, self.other_pub])
                self.assertTrue(any('was not removed' in m for m in self.messages(response)))

    def test_refused_for_a_hidden_report_without_naming_it(self):
        # May edit every report (change_publication, so add_feature on the secret one too)
        # and delete every feature, but does not see the confidential report.
        helper = make_user('s990777')
        helper.user_permissions.add(*Permission.objects.filter(
            codename__in=('change_publication', 'delete_feature'),
            content_type__app_label='publications'))
        secret = self.secret_report()
        feature = self.feature('Shared with a secret', self.pub, secret)
        self.login(helper)
        page = self.client.get(self.path(feature, secret))
        self.assertEqual(page.status_code, 200)
        self.assertIsNone(page.context['unlink_report'])
        self.assertNotContains(page, BUTTON_ID)
        response = self.unlink(feature, secret)
        self.assertUnchanged(feature, [self.pub, secret])
        for text in (page.content.decode(), *self.messages(response)):
            self.assertNotIn('Secret report', text)
            self.assertNotIn('99-05', text)

    def test_message_and_page_never_reveal_hidden_reports(self):
        secret = self.secret_report()
        feature = self.feature('Shared with a secret', self.pub, self.other_pub, secret)
        self.login(self.dtu_own)
        page = self.client.get(self.path(feature, self.pub))
        self.assertContains(page, 'Remove from report 99-01')
        response = self.unlink(feature, self.pub)
        self.assertUnchanged(feature, [self.other_pub, secret])
        messages = self.messages(response)
        self.assertEqual(messages, ['Feature "Shared with a secret" was removed from report '
                                    '99-01; it stays on the other report(s) it belongs to.'])
        for text in (page.content.decode(), *messages):
            self.assertNotIn('Secret report', text)
            self.assertNotIn('99-05', text)
            self.assertNotIn('2 other', text)
            self.assertNotIn('1 other', text)

    def test_refused_for_a_feature_on_one_report(self):
        feature = self.feature('Only here', self.pub)
        fileobject = self.add_file(feature, 'kept.txt')
        self.login(self.editor)
        response = self.unlink(feature, self.pub)
        self.assertRedirects(response, self.report_url(self.pub), fetch_redirect_response=False)
        self.assertUnchanged(feature, [self.pub])
        self.assertRecordAndFileKept(fileobject)
        self.assertTrue(any('belongs to one report only' in m for m in self.messages(response)))

    def test_delete_of_a_shared_feature_stays_refused(self):
        feature = self.feature('On both', self.pub, self.other_pub)
        self.login(self.editor)
        for data in ({'report': self.pub.pk}, {'report': self.pub.pk, 'action': 'delete'}):
            with self.subTest(data=data):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(page_path('delete_feature', pk=feature.pk), data)
                self.assertRedirects(response, self.report_url(self.pub),
                                     fetch_redirect_response=False)
                self.assertUnchanged(feature, [self.pub, self.other_pub])
                self.assertTrue(any('cannot be deleted' in m for m in self.messages(response)))

    def test_access(self):
        feature = self.feature('On both', self.pub, self.other_pub)
        response = self.unlink(feature, self.pub)
        self.assertRedirectsToLogin(response)
        for user in (self.dtu_not_own, self.staff):
            with self.subTest(user=user.username):
                self.login(user)
                self.assertDenied(self.unlink(feature, self.pub))
        self.assertUnchanged(feature, [self.pub, self.other_pub])

    def test_cancel_returns_to_the_report(self):
        feature = self.feature('On both', self.pub, self.other_pub)
        self.login(self.editor)
        response = self.client.get(self.path(feature, self.other_pub))
        self.assertEqual(response.context['cancel_url'], self.report_url(self.other_pub))
