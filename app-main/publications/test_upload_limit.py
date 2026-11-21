"""One upload limit per file for report PDFs and appendices (plan release-2026-7 T1, FA-R88).

settings.MAX_UPLOAD_SIZE_MB (300, nginx's client_max_body_size on /find/) is read by both
forms at validation time, named in their messages and help texts, and rendered on the file
inputs as data-max-size-mb for the browser's check (file-upload.js).

No large files: the end-to-end tests lower the limit to 1 MB with override_settings, and the
tests at the real 300 MB limit give a small SimpleUploadedFile a patched ``size``.
"""
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from publications.forms.publication import AddEditReportForm, UploadAppendixForm
from publications.models import Publication
from publications.test_factories import app_path, page_path, report_type
from publications.test_report_form import ReportFormTestBase

MB = 1024 * 1024


def _sized_file(name, size, content=b'%PDF-1.4\n'):
    """A small uploaded file that reports ``size`` bytes."""
    f = SimpleUploadedFile(name, content, content_type='application/pdf')
    f.size = size
    return f


def _real_file(name, size):
    """An uploaded file of exactly ``size`` bytes (for limits lowered to 1 MB)."""
    head = b'%PDF-1.4\n'
    return SimpleUploadedFile(name, head + b'0' * (size - len(head)),
                              content_type='application/pdf')


class UploadLimitSettingTests(SimpleTestCase):

    def test_limit_is_300_mb(self):
        # Must not exceed nginx's client_max_body_size 300M on /find/ (dtu_sus_web_server).
        self.assertEqual(settings.MAX_UPLOAD_SIZE_MB, 300)


class ReportPdfLimitTests(TestCase):
    """AddEditReportForm.clean_pdffile at the real limit, with a patched file size."""

    def clean_pdffile(self, uploaded):
        form = AddEditReportForm()
        form.cleaned_data = {'pdffile': uploaded}
        return form.clean_pdffile()

    def test_exactly_the_limit_is_accepted(self):
        uploaded = _sized_file('report.pdf', 300 * MB)
        self.assertIs(self.clean_pdffile(uploaded), uploaded)

    def test_one_byte_over_the_limit_is_refused_with_the_limit_in_the_message(self):
        with self.assertRaisesMessage(ValidationError, 'File size cannot exceed 300 MB.'):
            self.clean_pdffile(_sized_file('report.pdf', 300 * MB + 1))

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_limit_is_read_from_settings_at_validation_time(self):
        self.assertTrue(self.clean_pdffile(_sized_file('report.pdf', MB)))
        with self.assertRaisesMessage(ValidationError, 'File size cannot exceed 1 MB.'):
            self.clean_pdffile(_sized_file('report.pdf', MB + 1))

    def test_help_text_and_input_name_the_limit(self):
        form = AddEditReportForm()
        self.assertIn('300 MB', form.fields['pdffile'].help_text)
        self.assertIn('data-max-size-mb="300"', str(form['pdffile']))

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_help_text_and_input_follow_the_setting(self):
        form = AddEditReportForm()
        self.assertIn('max 1 MB', form.fields['pdffile'].help_text)
        self.assertIn('data-max-size-mb="1"', str(form['pdffile']))


@override_settings(MAX_UPLOAD_SIZE_MB=1)
class ReportPdfLimitEndToEndTests(ReportFormTestBase):
    """The add-report form through the view, with the limit lowered to 1 MB."""

    def test_pdf_of_exactly_the_limit_passes_the_form(self):
        response = self.client.post(page_path('add_report'),
                                    {**self.form_data(), 'pdffile': _real_file('big.pdf', MB)})
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)

    def test_pdf_one_byte_over_the_limit_is_a_form_error_naming_the_limit(self):
        response = self.client.post(page_path('add_report'),
                                    {**self.form_data(), 'pdffile': _real_file('big.pdf', MB + 1)})
        self.assertEqual(response.status_code, 200)
        errors = response.context['form'].errors['pdffile']
        self.assertEqual(errors, ['File size cannot exceed 1 MB.'])
        self.assertFalse(Publication.objects.filter(title='New report').exists())


class AddReportPageTests(ReportFormTestBase):

    def test_add_report_page_passes_the_limit_to_the_browser(self):
        response = self.client.get(page_path('add_report'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-max-size-mb="300"')
        self.assertContains(response, 'id="pdf-upload"')
        self.assertContains(response, 'max 300 MB')
        self.assertContains(response, 'publications/js/file-upload.js')


class AppendixLimitTests(SimpleTestCase):

    def form(self, *files):
        return UploadAppendixForm(data={}, files=MultiValueDict({'appendix_files': list(files)}))

    def test_exactly_the_limit_is_accepted(self):
        form = self.form(_sized_file('a.pdf', 300 * MB))
        self.assertTrue(form.is_valid(), form.errors)

    def test_one_byte_over_the_limit_is_refused_per_file(self):
        form = self.form(_sized_file('ok.pdf', 300 * MB), _sized_file('big.pdf', 300 * MB + 1))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['appendix_files'],
                         ['File "big.pdf" is too large. Maximum file size is 300 MB per file.'])

    def test_several_files_each_below_the_limit_are_accepted(self):
        # The limit is per file; nginx limits the whole request.
        form = self.form(_sized_file('a.pdf', 200 * MB), _sized_file('b.pdf', 200 * MB))
        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_limit_is_read_from_settings_at_validation_time(self):
        self.assertTrue(self.form(_real_file('a.pdf', MB)).is_valid())
        form = self.form(_real_file('a.pdf', MB + 1))
        self.assertFalse(form.is_valid())
        self.assertIn('1 MB per file', form.errors['appendix_files'][0])

    def test_help_text_and_input_name_the_limit(self):
        form = UploadAppendixForm()
        self.assertIn('300 MB per file', form.fields['appendix_files'].help_text)
        self.assertIn('data-max-size-mb="300"', str(form['appendix_files']))
        self.assertEqual(form.max_size_mb, 300)

    def test_help_text_does_not_grow_with_each_form(self):
        UploadAppendixForm()
        text = UploadAppendixForm().fields['appendix_files'].help_text
        self.assertEqual(text.count('per file'), 1)


class AppendixPageLimitTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.publication = Publication.objects.create(
            type=report_type(), title='Test report', number='99-01', year=1999, verified=True)
        cls.url = reverse('publications:upload_appendix', kwargs={'pk': cls.publication.pk})
        cls.path = app_path(cls.url)
        cls.editor = User.objects.create_user('editor')
        cls.editor.user_permissions.add(
            Permission.objects.get(codename='change_publication',
                                   content_type__app_label='publications'))

    def setUp(self):
        self.client.force_login(self.editor)

    def test_page_shows_the_limit_and_passes_it_to_the_browser(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-max-size-mb="300"')
        self.assertContains(response, 'Each file can be up to 300 MB.')
        self.assertNotContains(response, 'contact support')

    @override_settings(MAX_UPLOAD_SIZE_MB=1)
    def test_too_large_file_is_refused_with_a_message_naming_the_limit(self):
        response = self.client.post(self.path, {
            'action': 'upload', 'appendix_files': _real_file('big.pdf', MB + 1)})
        self.assertEqual(response.status_code, 302)
        # The message is shown on the page the upload redirects to.
        response = self.client.get(self.path)
        self.assertContains(response, 'File &quot;big.pdf&quot; is too large. '
                                      'Maximum file size is 1 MB per file.')
        self.assertEqual(self.client.session.get(f'appendix_upload_{self.publication.pk}', []), [])
