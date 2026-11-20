"""The thumbnail on the report page opens the report's PDF (same URL as the "download report
as pdf" link, so the media access check applies); a report without a PDF shows the plain
placeholder image without a link.

Found at the 2026.4 release checks: clicking the thumbnail did nothing.
"""
import re

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from publications.models import FileObject, Publication, PubType
from publications.test_upload_appendix_access import _app_path

PDF_NAME = 'reports/1998/98-71.pdf'   # no file on disk is needed: only the URL is rendered


class ReportThumbnailLinkTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')
        pdf = FileObject.objects.create(file=PDF_NAME)
        cls.with_pdf = Publication.objects.create(
            type=pubtype, number='98-71', title='Thumb link with pdf', year=1998,
            verified=True, file=pdf)
        cls.without_pdf = Publication.objects.create(
            type=pubtype, number='98-72', title='Thumb link without pdf', year=1998,
            verified=True)

    def page(self, pub):
        response = self.client.get(
            _app_path(reverse('publications:report', kwargs={'pk': pub.pk})))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_thumbnail_links_to_the_pdf(self):
        body = self.page(self.with_pdf)
        pdf_url = settings.MEDIA_URL + PDF_NAME
        link = re.search(
            r'<a href="([^"]*)"[^>]*class="report-thumbnail-link"[^>]*>\s*<img [^>]*alt="preview-picture"',
            body)
        self.assertIsNotNone(link, 'thumbnail is not wrapped in a link')
        self.assertEqual(link.group(1), pdf_url)
        # The same URL as the download link.
        self.assertIn(f'<a href="{pdf_url}" target="_blank">download report as pdf', body)

    def test_no_link_without_pdf(self):
        body = self.page(self.without_pdf)
        self.assertIn('alt="preview-picture"', body)
        self.assertNotIn('report-thumbnail-link', body)
        self.assertIn('No PDF file available', body)
