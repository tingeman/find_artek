"""Tests of UploadAppendixForm's multi-file field (Django 4.2.1+, CVE-2023-31047).

No database needed. Run with:
    python manage.py test publications.test_upload_appendix_form --settings find_artek.development_settings
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.utils.datastructures import MultiValueDict

from publications.forms.publication import MultipleFileInput, UploadAppendixForm


def _file(name, content=b'x'):
    return SimpleUploadedFile(name, content)


class UploadAppendixFormTests(SimpleTestCase):

    def test_widget_renders_multiple(self):
        html = str(UploadAppendixForm()['appendix_files'])
        self.assertIn('multiple', html)
        self.assertIn('type="file"', html)
        self.assertIsInstance(UploadAppendixForm().fields['appendix_files'].widget, MultipleFileInput)

    def test_several_valid_files(self):
        files = MultiValueDict({'appendix_files': [_file('a.pdf'), _file('b.docx'), _file('c.png')]})
        form = UploadAppendixForm(data={}, files=files)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual([f.name for f in form.cleaned_data['appendix_files']], ['a.pdf', 'b.docx', 'c.png'])

    def test_single_file(self):
        form = UploadAppendixForm(data={}, files=MultiValueDict({'appendix_files': [_file('a.pdf')]}))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data['appendix_files']), 1)

    def test_no_files_is_valid(self):
        form = UploadAppendixForm(data={}, files=MultiValueDict())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data['appendix_files'])

    def test_bad_extension_in_any_file_is_rejected(self):
        # Not only the last file: the first one is the bad one here.
        files = MultiValueDict({'appendix_files': [_file('evil.exe'), _file('ok.pdf')]})
        form = UploadAppendixForm(data={}, files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('appendix_files', form.errors)

    def test_empty_file_is_rejected(self):
        files = MultiValueDict({'appendix_files': [_file('ok.pdf'), _file('empty.pdf', b'')]})
        form = UploadAppendixForm(data={}, files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('appendix_files', form.errors)
