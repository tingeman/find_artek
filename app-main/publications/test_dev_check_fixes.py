"""Fixes from the owner's dev checks (plan release-2026-7 T11).

- The marker legend (report list, report page) and the person page heading: only the sign is
  red and bold, the parentheses are plain text, as in the per-name marker.
- The report form: the edit page has ``action == 'edit'`` and the report in its context, so
  it is titled "Edit report" and shows the report summary; the add page is "New report". No
  Bootstrap 5 stylesheet on top of base.html's Bootstrap 4.
- The merge page has a "Confirm person" button (to person_confirm) for a person with marked
  links only; posting it clears the markers and ends on the person page with a message.
- The page scripts changed in this release are included with ``?v=<STATIC_ASSET_VERSION>``.

Everything is made up factory data.
"""
import datetime
import re

from django.conf import settings
from django.template import Context, Template
from django.templatetags.static import static
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from publications.models import Authorship, Feature
from publications.roles import ARTEK_EDITOR
from publications.test_factories import (
    make_person, make_report, make_user, page_path, report_type,
)

RED_SIGN = '<span style="color:red; font-weight:bold;">{}</span>'
VERSIONED_SCRIPTS = (
    'publications/js/file-upload.js',
    'publications/js/class/my-reports-class.js',
    'publications/js/map/find-artek-map.js',   # replaced my-map-class.js (features T3)
)


class FixFixture(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pubtype = report_type()
        cls.marked = make_person('Ann', 'Alpha')
        cls.plain = make_person('Bob', 'Beta')
        cls.pub = make_report(cls.pubtype, '11-01', verified=True, confidential=False,
                              title='Fix report', year=2011,
                              authors=[cls.marked, cls.plain])
        Authorship.objects.filter(publication=cls.pub, person=cls.marked).update(
            exact_match=True, match_string='Ann Alpha')
        cls.editor = make_user('edit911', ARTEK_EDITOR)
        cls.superuser = make_user('super911', superuser=True)

    def get(self, path, user=None):
        self.client.force_login(user or self.editor)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response


class MarkerLegendTests(FixFixture):

    def assertSignsOnlyRed(self, html):
        for sign in '!?':
            self.assertIn(f'({RED_SIGN.format(sign)})', html)
            # No red span around a parenthesis.
            self.assertNotIn(f'color:red; font-weight:bold;">({sign})', html)
        self.assertNotIn('font-weight:bold;">(!)/(?)', html)

    def test_legend_on_report_list_and_report_page(self):
        for name, kwargs in (('reports', {}), ('report', {'pk': self.pub.pk})):
            with self.subTest(page=name):
                html = self.get(page_path(name, **kwargs)).content.decode()
                self.assertIn('person-marker-legend', html)
                legend = html[html.index('person-marker-legend'):]
                self.assertSignsOnlyRed(legend[:legend.index('</div>')])

    def test_person_page_heading(self):
        html = self.get(page_path('person', pk=self.marked.pk)).content.decode()
        heading = html[html.index('id="confirm-person"'):]
        self.assertSignsOnlyRed(heading[:heading.index('</h5>')])


class ReportFormContextTests(FixFixture):

    def test_edit_page(self):
        response = self.get(page_path('edit_report', pk=self.pub.pk))
        self.assertEqual(response.context['action'], 'edit')
        self.assertEqual(response.context['publication'], self.pub)
        html = response.content.decode()
        self.assertRegex(html, r'<title>[^<]*Edit report')
        self.assertNotIn('New report', html)
        # The summary: number, title linked to the report page, authors.
        self.assertContains(response, 'class="report-block"')
        self.assertContains(response, '11-01')
        self.assertContains(response, f'href="{reverse("publications:report", kwargs={"pk": self.pub.pk})}"')
        self.assertContains(response, 'Alpha')
        self.assertContains(response, 'var isEditMode = "edit" === "edit";')

    def test_add_page(self):
        response = self.get(page_path('add_report'))
        self.assertEqual(response.context['action'], 'add')
        self.assertIsNone(response.context['publication'])
        html = response.content.decode()
        self.assertRegex(html, r'<title>[^<]*New report')
        self.assertNotIn('Edit report', html)
        self.assertNotContains(response, 'class="report-block"')
        self.assertContains(response, 'var isEditMode = "add" === "edit";')

    def test_no_bootstrap_5_on_the_form(self):
        for path in (page_path('add_report'), page_path('edit_report', pk=self.pub.pk)):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertNotContains(response, 'bootstrap@5')
                self.assertContains(response, 'bootstrap@4.6.2')


class MergePageConfirmTests(FixFixture):

    def test_confirm_button_for_a_marked_person_only(self):
        response = self.get(page_path('person_merge', pk=self.marked.pk))
        self.assertContains(response, 'Not a duplicate')
        self.assertContains(
            response,
            f'action="{reverse("publications:person_confirm", kwargs={"pk": self.marked.pk})}"')
        self.assertContains(response, 'Confirm person')

        response = self.get(page_path('person_merge', pk=self.plain.pk))
        self.assertNotContains(response, 'Not a duplicate')
        self.assertNotContains(response, 'Confirm person')
        self.assertNotContains(
            response, reverse('publications:person_confirm', kwargs={'pk': self.plain.pk}))

    def test_posting_it_clears_the_markers_and_ends_on_the_person_page(self):
        self.client.force_login(self.editor)
        response = self.client.post(page_path('person_confirm', pk=self.marked.pk))
        # The Location holds the script prefix ('/find' with the production settings), so
        # the person page is fetched by its test client path rather than followed.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'],
                         reverse('publications:person', kwargs={'pk': self.marked.pk}))
        self.assertContains(self.get(page_path('person', pk=self.marked.pk)), 'confirmed')
        link = Authorship.objects.get(publication=self.pub, person=self.marked)
        self.assertFalse(link.exact_match)
        # Now unmarked: the merge page shows no confirm button any more.
        self.assertNotContains(self.get(page_path('person_merge', pk=self.marked.pk)),
                               'Confirm person')


class VersionedScriptTests(FixFixture):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.feature = Feature.objects.create(name='BH-911', date=datetime.date(2011, 7, 1))
        cls.feature.publications.add(cls.pub)

    def pages(self):
        """name -> (path, scripts the page includes)."""
        reports, maps, upload = VERSIONED_SCRIPTS[1], VERSIONED_SCRIPTS[2], VERSIONED_SCRIPTS[0]
        return {
            'add_report': (page_path('add_report'), [upload]),
            'edit_report': (page_path('edit_report', pk=self.pub.pk), [upload]),
            # features T3: the front page no longer prefetches (no browser cache since
            # FA-R89), and the map pages don't load the report-list class.
            'map': (page_path('map'), [maps]),
            'reports': (page_path('reports'), [reports]),
            'report': (page_path('report', pk=self.pub.pk), [maps]),
            'person': (page_path('person', pk=self.marked.pk), [reports]),
            'feature': (page_path('feature', pk=self.feature.pk), [maps]),
        }

    def test_scripts_carry_the_version(self):
        version = settings.STATIC_ASSET_VERSION
        self.assertTrue(version)
        for name, (path, scripts) in self.pages().items():
            html = self.get(path, self.superuser).content.decode()
            # Comments are ignored (base.html used to keep a commented-out include).
            html = re.sub(r'<!--.*?-->', '', html, flags=re.S)
            for script in scripts:
                with self.subTest(page=name, script=script):
                    self.assertIn(f'<script src="{static(script)}?v={version}"', html)
                    # No unversioned copy of the script on the page.
                    self.assertNotRegex(html, re.escape(static(script)) + r'"')

    @override_settings(STATIC_ASSET_VERSION='2099.1')
    def test_version_comes_from_the_setting(self):
        html = self.get(page_path('add_report')).content.decode()
        self.assertIn(f'{static(VERSIONED_SCRIPTS[0])}?v=2099.1"', html)


class VersionedStaticTagTests(SimpleTestCase):

    @override_settings(STATIC_ASSET_VERSION='2026.7')
    def test_tag_appends_the_version_to_the_static_url(self):
        rendered = Template(
            "{% load static_version %}{% versioned_static 'publications/js/file-upload.js' %}"
        ).render(Context())
        self.assertEqual(rendered, static('publications/js/file-upload.js') + '?v=2026.7')

    @override_settings(STATIC_URL='/find/static/', STATIC_ASSET_VERSION='2026.7')
    def test_tag_keeps_the_url_prefix(self):
        rendered = Template(
            "{% load static_version %}{% versioned_static 'publications/js/file-upload.js' %}"
        ).render(Context())
        self.assertTrue(rendered.startswith('/find/static/publications/js/file-upload.js?v='),
                        rendered)
