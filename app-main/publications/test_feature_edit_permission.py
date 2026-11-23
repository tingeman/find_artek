"""Action ``edit_feature`` (permissions.EDIT_FEATURE, plan "features" T4).

EDIT_FEATURE = Feature.is_editable_by: change_feature (artek_editor), or edit_own_feature
(dtu_user) and listed on a report the feature belongs to. Users get their rights from the
role groups of migration 0003, as at a CAS login. Checked through user_may and through
FeaturePermissionMixin (as DELETE_FEATURE): anonymous -> login redirect, not allowed -> 403,
unknown feature -> 404.
"""
import datetime

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View

from publications.models import Feature
from publications.permissions import (
    DENIED_MESSAGES, EDIT_FEATURE, FEATURE_ACTIONS, FeaturePermissionMixin, user_may,
)
from publications.test_factories import make_user
from publications.test_report_access import ReportAccessTestBase


class EditFeatureView(FeaturePermissionMixin, View):
    permission = EDIT_FEATURE

    def get(self, request, *args, **kwargs):
        return HttpResponse(f'edit {self.feature.pk}')


class EditFeaturePermissionTests(ReportAccessTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.superuser = make_user('root', superuser=True)
        cls.feature = Feature.objects.create(name='On own report', date=datetime.date(2000, 1, 1))
        cls.feature.publications.add(cls.pub)
        cls.orphan = Feature.objects.create(name='On no report', date=datetime.date(2000, 1, 1))

    def test_action_is_a_feature_action(self):
        self.assertIn(EDIT_FEATURE, FEATURE_ACTIONS)
        self.assertIn(EDIT_FEATURE, DENIED_MESSAGES)

    def test_matrix(self):
        expected = [
            # user,                 feature on the report, feature on no report
            (AnonymousUser(),        False, False),
            (self.dtu_own,           True,  False),   # dtu_user listed on the report
            (self.dtu_not_own,       False, False),   # dtu_user not listed
            (self.editor,            True,  True),    # artek_editor: change_feature
            (self.superuser,         True,  True),
        ]
        for user, on_report, orphan in expected:
            with self.subTest(user=str(user)):
                self.assertIs(user_may(user, EDIT_FEATURE, self.feature), on_report)
                self.assertIs(user_may(user, EDIT_FEATURE, self.orphan), orphan)
                # Same rule as the model method.
                self.assertIs(self.feature.is_editable_by(user), on_report)

    def test_needs_a_feature(self):
        with self.assertRaises(ValueError):
            user_may(self.editor, EDIT_FEATURE)

    def get(self, user, pk):
        request = RequestFactory().get(f'/feature/{pk}/edit/')
        request.user = user
        request.session = {}
        return EditFeatureView.as_view()(request, pk=pk)

    def test_mixin(self):
        response = self.get(AnonymousUser(), self.feature.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response['Location'])
        response = self.get(self.dtu_not_own, self.feature.pk)
        self.assertEqual(response.status_code, 403)
        self.assertIn(DENIED_MESSAGES[EDIT_FEATURE], response.content.decode())
        for user in (self.dtu_own, self.editor, self.superuser):
            with self.subTest(user=user.username):
                response = self.get(user, self.feature.pk)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content.decode(), f'edit {self.feature.pk}')

    def test_mixin_unknown_feature_is_404(self):
        from django.http import Http404
        with self.assertRaises(Http404):
            self.get(self.editor, self.orphan.pk + 1000)
