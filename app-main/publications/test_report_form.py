"""The add/edit report form end to end (plan "registration" T7, roadmap FA-R55).

Form (ReportFormView) -> review (ReportReviewView) -> finalize (ReportFinalizeView), through
the real views with the test client:

- adding a report with persons, topics, keywords (one typed new one) and a PDF;
- replacing and deleting the PDF of an existing report;
- unknown topics are a form error; new keywords are only created when the report is saved;
- a failure during finalize leaves no report, no keyword and no moved file behind;
- a PDF of several MB passes the form;
- session data entered for one report (or the add form) is never saved onto another one.

MEDIA_ROOT is a temporary directory per test. The PDF fixture is a generated one-page PDF
(test_fixtures/one_page.pdf), not a real report. File moves happen in transaction.on_commit,
so the finalize requests run inside captureOnCommitCallbacks(execute=True).
"""
import os
import re
import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from publications.models import (
    Authorship, FileObject, Keyword, Person, Publication, Supervisorship, Topic,
)
from publications.roles import ARTEK_EDITOR, ARTEK_STAFF
from publications.test_factories import make_user, page_path, report_type
from publications.views import (
    REPORT_FORM_DATA_KEY, ReportFinalizeView, get_report_form_data, report_form_target,
    store_report_form_data,
)

FIXTURE_PDF = os.path.join(os.path.dirname(__file__), 'test_fixtures', 'one_page.pdf')
YEAR = 2025


def _fixture_bytes():
    with open(FIXTURE_PDF, 'rb') as f:
        return f.read()


def _failing_after_handle_files():
    """ReportFinalizeView._handle_files that does its work (database rows changed, file moves
    registered for after the commit) and then fails, as the last step of the save would."""
    original = ReportFinalizeView._handle_files

    def failing(view, *args, **kwargs):
        original(view, *args, **kwargs)
        raise RuntimeError('forced failure')
    return failing


# No DTU directory: typed initials or a study number would make the person step ask LDAP
# (release-2026-7 T12); the directory lookup is tested with LDAP mocked in
# test_person_ldap_lookup.
@override_settings(USE_LDAP=False)
class ReportFormTestBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pubtype = report_type()
        cls.topic = Topic.objects.create(topic='Permafrost')
        cls.other_topic = Topic.objects.create(topic='Hydrology')
        cls.keyword = Keyword.objects.create(keyword='Ice')
        cls.author1 = Person.objects.create(first='Ann', last='Author')
        cls.author2 = Person.objects.create(first='Bob', last='Writer')
        cls.supervisor = Person.objects.create(first='Sue', last='Pervisor', initials='supv')

        cls.editor = make_user('edtr', ARTEK_EDITOR)
        cls.staff = make_user('stfo', ARTEK_STAFF)

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='test_report_form_')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=self.media_root)
        media.enable()
        self.addCleanup(media.disable)
        self.client.force_login(self.editor)

    # --- helpers ---------------------------------------------------------------------------

    def media(self, *parts):
        return os.path.join(self.media_root, *parts)

    def temp_files(self):
        """Files under MEDIA_ROOT/temp/ (relative paths)."""
        found = []
        for root, _dirs, files in os.walk(self.media('temp')):
            found += [os.path.relpath(os.path.join(root, f), self.media_root) for f in files]
        return found

    def pdf(self, content=None, name='my report.pdf'):
        return SimpleUploadedFile(name, _fixture_bytes() if content is None else content,
                                  content_type='application/pdf')

    def form_data(self, title='New report', **extra):
        data = {
            'title': title,
            'type': str(self.pubtype.pk),
            'year': str(YEAR),
            'abstract': 'An abstract',
            'comment': '',
            'authors': [str(self.author1.pk), str(self.author2.pk)],
            'supervisors': [str(self.supervisor.pk)],
            'publication_topics': [str(self.topic.pk)],
            'publication_keywords': [str(self.keyword.pk), 'Thaw slumps'],
        }
        data.update(extra)
        return data

    def finalize(self, path):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(path)
        return response, callbacks

    def make_report(self, number, title='Existing report', with_pdf=False):
        pub = Publication.objects.create(type=self.pubtype, title=title, number=number,
                                         year=YEAR, verified=True)
        Authorship.objects.create(publication=pub, person=self.author1, author_id=0)
        if with_pdf:
            name = f'reports/{YEAR}/{number}.pdf'
            os.makedirs(self.media('reports', str(YEAR), 'thumbs'), exist_ok=True)
            with open(self.media(name), 'wb') as f:
                f.write(b'%PDF-1.4 old version')
            with open(self.media('reports', str(YEAR), 'thumbs', f'{number}_thumb.jpg'), 'wb') as f:
                f.write(b'thumb')
            pub.file = FileObject.objects.create(file=name, created_by=self.editor)
            pub.save()
        return pub


class AddReportTests(ReportFormTestBase):

    def test_add_report_with_persons_topic_keywords_and_pdf(self):
        keywords_before = Keyword.objects.count()

        response = self.client.post(page_path('add_report'), {**self.form_data(), 'pdffile': self.pdf()})
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)
        # The PDF waits in MEDIA_ROOT/temp/ as a temporary FileObject; nothing else is saved.
        self.assertEqual(len(self.temp_files()), 1)
        temp_upload = FileObject.objects.get()
        self.assertTrue(temp_upload.file.name.startswith('temp/'))
        self.assertEqual(Keyword.objects.count(), keywords_before)
        self.assertFalse(Publication.objects.exists())

        response = self.client.get(page_path('add_report_review'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Thaw slumps')

        response, _ = self.finalize(page_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': pub.pk}),
                             fetch_redirect_response=False)

        self.assertFalse(pub.verified)
        self.assertEqual(pub.number, '25-01')
        self.assertEqual(pub.year, YEAR)
        self.assertEqual(pub.created_by, self.editor)
        self.assertEqual(pub.modified_by, self.editor)
        self.assertEqual([a.person for a in pub.authorship_set.order_by('author_id')],
                         [self.author1, self.author2])
        self.assertEqual([s.person for s in pub.supervisorship_set.all()], [self.supervisor])
        self.assertEqual(list(pub.publication_topics.all()), [self.topic])
        new_keyword = Keyword.objects.get(keyword='Thaw slumps')
        self.assertEqual(set(pub.publication_keywords.all()), {self.keyword, new_keyword})
        self.assertEqual(Keyword.objects.count(), keywords_before + 1)

        # The PDF is under reports/<year>/<number>.pdf; the temporary upload is gone.
        self.assertEqual(pub.file.file.name, f'reports/{YEAR}/25-01.pdf')
        with open(self.media('reports', str(YEAR), '25-01.pdf'), 'rb') as f:
            self.assertEqual(f.read(), _fixture_bytes())
        self.assertEqual(pub.file.created_by, self.editor)
        self.assertFalse(FileObject.objects.filter(pk=temp_upload.pk).exists())
        self.assertEqual(FileObject.objects.count(), 1)
        self.assertEqual(self.temp_files(), [])
        self.assertEqual(os.listdir(self.media('temp')), [])  # its <timestamp> dir too

        self.assertNotIn(REPORT_FORM_DATA_KEY, self.client.session)

    def test_typed_keyword_that_exists_is_reused(self):
        self.client.post(page_path('add_report'),
                         self.form_data(publication_keywords=['ice', 'Ice ', str(self.keyword.pk)]))
        self.finalize(page_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertEqual(list(pub.publication_keywords.all()), [self.keyword])
        self.assertEqual(Keyword.objects.count(), 1)

    def test_staff_may_create_keywords(self):
        self.client.force_login(self.staff)
        self.client.post(page_path('add_report'), self.form_data(publication_keywords=['Snow']))
        self.finalize(page_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertEqual([k.keyword for k in pub.publication_keywords.all()], ['Snow'])

    def test_unknown_topic_is_a_form_error(self):
        response = self.client.post(page_path('add_report'), {
            **self.form_data(publication_topics=[str(self.topic.pk), 'Glaciology']),
            'pdffile': self.pdf(),
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('publication_topics', form.errors)
        self.assertIn('Unknown topic "Glaciology"', form.errors['publication_topics'][0])
        # Nothing is stored: no session data, no temporary upload, no topic.
        self.assertIsNone(get_report_form_data(self.client.session, 'add'))
        self.assertFalse(FileObject.objects.exists())
        self.assertEqual(self.temp_files(), [])
        self.assertFalse(Topic.objects.filter(topic='Glaciology').exists())

    def test_unknown_topic_pk_is_a_form_error(self):
        response = self.client.post(page_path('add_report'),
                                    self.form_data(publication_topics=['999999']))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Unknown topic', response.context['form'].errors['publication_topics'][0])

    def test_pdf_of_several_mb_passes_the_form(self):
        size = 6 * 1024 * 1024
        content = b'%PDF-1.4\n' + b'0' * (size - 9)
        response = self.client.post(page_path('add_report'),
                                    {**self.form_data(), 'pdffile': self.pdf(content, 'big.pdf')})
        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)
        self.finalize(page_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertEqual(os.path.getsize(pub.file.file.path), size)
        self.assertEqual(self.temp_files(), [])

    def test_failure_in_finalize_leaves_no_report_no_keyword_and_no_moved_file(self):
        self.client.post(page_path('add_report'), {**self.form_data(), 'pdffile': self.pdf()})
        temp_upload = FileObject.objects.get()
        temp_path = temp_upload.file.path

        with mock.patch.object(ReportFinalizeView, '_handle_files', _failing_after_handle_files()):
            response, callbacks = self.finalize(page_path('add_report_finalize'))

        self.assertRedirects(response, reverse('publications:add_report_review'),
                             fetch_redirect_response=False)
        self.assertEqual(callbacks, [])  # no file operation was scheduled
        self.assertFalse(Publication.objects.exists())
        self.assertFalse(Authorship.objects.exists())
        self.assertFalse(Supervisorship.objects.exists())
        self.assertFalse(Keyword.objects.filter(keyword='Thaw slumps').exists())
        # The temporary upload is untouched and nothing is under reports/.
        self.assertEqual(list(FileObject.objects.all()), [temp_upload])
        self.assertTrue(os.path.exists(temp_path))
        self.assertFalse(os.path.exists(self.media('reports')))
        # The form data stays, so the user can try again.
        self.assertIsNotNone(get_report_form_data(self.client.session, 'add'))

        response, _ = self.finalize(page_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertEqual(pub.file.file.name, f'reports/{YEAR}/25-01.pdf')
        self.assertFalse(os.path.exists(temp_path))

    def test_posted_uploaded_file_id_is_ignored(self):
        """uploaded_file_id comes only from an upload in the same request, never from the POST:
        another report's file must not be moved into the new report."""
        other = self.make_report('25-07', with_pdf=True)
        other_file = other.file
        self.client.post(page_path('add_report'),
                         {**self.form_data(), 'uploaded_file_id': str(other_file.pk)})
        self.finalize(page_path('add_report_finalize'))
        pub = Publication.objects.get(title='New report')
        self.assertIsNone(pub.file)
        other.refresh_from_db()
        self.assertEqual(other.file, other_file)
        self.assertTrue(os.path.exists(self.media('reports', str(YEAR), '25-07.pdf')))

    def test_temporary_upload_of_another_user_is_refused(self):
        self.client.post(page_path('add_report'), self.form_data())
        foreign = FileObject.objects.create(file='temp/1/temp_1_x.pdf', created_by=self.staff)
        session = self.client.session
        data = get_report_form_data(session, 'add')
        data['uploaded_file_id'] = str(foreign.pk)
        store_report_form_data(session, 'add', data)
        session.save()

        response, _ = self.finalize(page_path('add_report_finalize'))
        self.assertRedirects(response, reverse('publications:add_report'),
                             fetch_redirect_response=False)
        self.assertFalse(Publication.objects.exists())
        self.assertTrue(FileObject.objects.filter(pk=foreign.pk).exists())


class EditReportFileTests(ReportFormTestBase):

    def test_edit_replaces_the_pdf(self):
        pub = self.make_report('25-07', with_pdf=True)
        old_file_pk = pub.file.pk

        response = self.client.post(page_path('edit_report', pk=pub.pk),
                                    {**self.form_data(title='Changed title'), 'pdffile': self.pdf()})
        self.assertRedirects(response, reverse('publications:edit_report_review', kwargs={'pk': pub.pk}),
                             fetch_redirect_response=False)
        self.assertEqual(self.client.get(page_path('edit_report_review', pk=pub.pk)).status_code, 200)

        response, _ = self.finalize(page_path('edit_report_finalize', pk=pub.pk))
        self.assertRedirects(response, reverse('publications:report', kwargs={'pk': pub.pk}),
                             fetch_redirect_response=False)

        pub.refresh_from_db()
        self.assertEqual(pub.title, 'Changed title')
        self.assertEqual(pub.number, '25-07')
        # The new PDF has the report's name; the old one is kept beside it as .old (without
        # a database row), the thumbnail is removed so that cron makes a new one.
        self.assertEqual(pub.file.file.name, f'reports/{YEAR}/25-07.pdf')
        self.assertNotEqual(pub.file.pk, old_file_pk)
        self.assertFalse(FileObject.objects.filter(pk=old_file_pk).exists())
        self.assertEqual(FileObject.objects.count(), 1)
        with open(self.media('reports', str(YEAR), '25-07.pdf'), 'rb') as f:
            self.assertEqual(f.read(), _fixture_bytes())
        with open(self.media('reports', str(YEAR), '25-07.pdf.old'), 'rb') as f:
            self.assertEqual(f.read(), b'%PDF-1.4 old version')
        self.assertFalse(os.path.exists(self.media('reports', str(YEAR), 'thumbs', '25-07_thumb.jpg')))
        self.assertEqual(self.temp_files(), [])

    def test_edit_adds_a_pdf_to_a_report_without_one(self):
        pub = self.make_report('25-08')
        self.client.post(page_path('edit_report', pk=pub.pk), {**self.form_data(), 'pdffile': self.pdf()})
        self.finalize(page_path('edit_report_finalize', pk=pub.pk))
        pub.refresh_from_db()
        self.assertEqual(pub.file.file.name, f'reports/{YEAR}/25-08.pdf')
        self.assertTrue(os.path.exists(self.media('reports', str(YEAR), '25-08.pdf')))

    def test_edit_deletes_the_pdf(self):
        pub = self.make_report('25-07', with_pdf=True)
        old_file_pk = pub.file.pk
        self.client.post(page_path('edit_report', pk=pub.pk), {**self.form_data(), 'delete_pdf': 'on'})
        self.finalize(page_path('edit_report_finalize', pk=pub.pk))
        pub.refresh_from_db()
        self.assertIsNone(pub.file)
        self.assertFalse(FileObject.objects.filter(pk=old_file_pk).exists())
        self.assertFalse(os.path.exists(self.media('reports', str(YEAR), '25-07.pdf')))

    def test_failure_in_edit_finalize_leaves_report_and_files_unchanged(self):
        pub = self.make_report('25-07', with_pdf=True)
        old_file = pub.file
        self.client.post(page_path('edit_report', pk=pub.pk),
                         {**self.form_data(title='Changed title'), 'pdffile': self.pdf()})

        with mock.patch.object(ReportFinalizeView, '_handle_files', _failing_after_handle_files()):
            response, callbacks = self.finalize(page_path('edit_report_finalize', pk=pub.pk))

        self.assertRedirects(response, reverse('publications:edit_report_review', kwargs={'pk': pub.pk}),
                             fetch_redirect_response=False)
        self.assertEqual(callbacks, [])
        pub.refresh_from_db()
        self.assertEqual(pub.title, 'Existing report')
        self.assertEqual(pub.file, old_file)
        self.assertEqual([a.person for a in pub.authorship_set.all()], [self.author1])
        with open(self.media('reports', str(YEAR), '25-07.pdf'), 'rb') as f:
            self.assertEqual(f.read(), b'%PDF-1.4 old version')
        self.assertFalse(os.path.exists(self.media('reports', str(YEAR), '25-07.pdf.old')))
        self.assertTrue(os.path.exists(self.media('reports', str(YEAR), 'thumbs', '25-07_thumb.jpg')))
        self.assertEqual(len(self.temp_files()), 1)


class SessionBindingTests(ReportFormTestBase):
    """Form data in the session belongs to the form it was entered in (add, or edit of one
    report). It is never reviewed or saved as another report."""

    def setUp(self):
        super().setUp()
        self.report_a = self.make_report('25-01', title='Report A')
        self.report_b = self.make_report('25-02', title='Report B')

    def assertUnchanged(self):
        self.assertEqual(Publication.objects.get(pk=self.report_a.pk).title, 'Report A')
        self.assertEqual(Publication.objects.get(pk=self.report_b.pk).title, 'Report B')
        self.assertEqual(Publication.objects.count(), 2)

    def test_edit_data_of_one_report_is_not_saved_onto_another(self):
        self.client.post(page_path('edit_report', pk=self.report_a.pk), self.form_data(title='Meant for A'))
        self.assertEqual(self.client.session['form_data_for'], report_form_target(self.report_a.pk))

        response, _ = self.finalize(page_path('edit_report_finalize', pk=self.report_b.pk))
        self.assertRedirects(response, reverse('publications:edit_report', kwargs={'pk': self.report_b.pk}),
                             fetch_redirect_response=False)
        self.assertUnchanged()

        response = self.client.get(page_path('edit_report_review', pk=self.report_b.pk))
        self.assertRedirects(response, reverse('publications:edit_report', kwargs={'pk': self.report_b.pk}),
                             fetch_redirect_response=False)

        # The data still belongs to report A and is saved there.
        self.finalize(page_path('edit_report_finalize', pk=self.report_a.pk))
        self.assertEqual(Publication.objects.get(pk=self.report_a.pk).title, 'Meant for A')
        self.assertEqual(Publication.objects.get(pk=self.report_b.pk).title, 'Report B')

    def test_add_data_is_not_saved_onto_an_existing_report(self):
        self.client.post(page_path('add_report'), self.form_data(title='Meant as new'))
        response, _ = self.finalize(page_path('edit_report_finalize', pk=self.report_b.pk))
        self.assertRedirects(response, reverse('publications:edit_report', kwargs={'pk': self.report_b.pk}),
                             fetch_redirect_response=False)
        self.assertUnchanged()

    def test_edit_data_is_not_saved_as_a_new_report(self):
        self.client.post(page_path('edit_report', pk=self.report_a.pk), self.form_data(title='Meant for A'))
        response, _ = self.finalize(page_path('add_report_finalize'))
        self.assertRedirects(response, reverse('publications:add_report'),
                             fetch_redirect_response=False)
        self.assertUnchanged()

    def test_session_data_without_form_binding_is_not_saved(self):
        """Form data in the old layout (no binding, e.g. a session from before T7)."""
        session = self.client.session
        session['form_data'] = {'title': ['Old session'], 'type': [str(self.pubtype.pk)],
                                'year': [str(YEAR)]}
        session.save()
        response, _ = self.finalize(page_path('edit_report_finalize', pk=self.report_b.pk))
        self.assertRedirects(response, reverse('publications:edit_report', kwargs={'pk': self.report_b.pk}),
                             fetch_redirect_response=False)
        self.finalize(page_path('add_report_finalize'))
        self.assertUnchanged()



class ConfidentialFormTests(ReportFormTestBase):
    """The confidential checkbox (plan confidential T4): set on add, kept or cleared on edit,
    shown on the review step. An unchecked box is absent from the POST and saves False."""

    CHECKED = re.compile(r'<input type="checkbox" name="confidential"[^>]*\bchecked\b')

    def add(self, **extra):
        self.client.post(page_path('add_report'), self.form_data(**extra))
        self.finalize(page_path('add_report_finalize'))
        return Publication.objects.get(title='New report')

    def test_add_with_confidential_checked_saves_true(self):
        self.assertTrue(self.add(confidential='on').confidential)

    def test_add_without_confidential_saves_false(self):
        self.assertFalse(self.add().confidential)

    def test_add_form_shows_the_checkbox_unchecked(self):
        response = self.client.get(page_path('add_report'))
        self.assertContains(response, 'name="confidential"')
        self.assertContains(response, 'Only the people listed on the report, artek_editor and '
                                      'superusers can see it.')
        self.assertNotRegex(response.content.decode(), self.CHECKED)

    def test_edit_form_opens_with_the_current_value_checked(self):
        pub = self.make_report('25-03')
        pub.confidential = True
        pub.save()
        response = self.client.get(page_path('edit_report', pk=pub.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context['form']['confidential'].value(), True)
        self.assertRegex(response.content.decode(), self.CHECKED)

        other = self.make_report('25-04')
        response = self.client.get(page_path('edit_report', pk=other.pk))
        self.assertIs(response.context['form']['confidential'].value(), False)
        self.assertNotRegex(response.content.decode(), self.CHECKED)

    def test_edit_changing_only_the_title_keeps_confidential(self):
        pub = self.make_report('25-03')
        pub.confidential = True
        pub.save()
        # The edit form opens checked, so the browser posts the box with the other fields.
        self.client.post(page_path('edit_report', pk=pub.pk),
                         self.form_data(title='Changed title', confidential='on'))
        self.finalize(page_path('edit_report_finalize', pk=pub.pk))
        pub.refresh_from_db()
        self.assertEqual(pub.title, 'Changed title')
        self.assertTrue(pub.confidential)

    def test_edit_clearing_confidential_saves_false(self):
        pub = self.make_report('25-03')
        pub.confidential = True
        pub.save()
        # Only the box changes (title as stored): the review step still counts it as a change.
        self.client.post(page_path('edit_report', pk=pub.pk), self.form_data(title='Existing report'))
        response = self.client.get(page_path('edit_report_review', pk=pub.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<span class="review-confidential">No</span>')
        self.finalize(page_path('edit_report_finalize', pk=pub.pk))
        pub.refresh_from_db()
        self.assertEqual(pub.title, 'Existing report')
        self.assertFalse(pub.confidential)

    def test_edit_setting_confidential_saves_true(self):
        pub = self.make_report('25-03')
        self.client.post(page_path('edit_report', pk=pub.pk),
                         self.form_data(title='Existing report', confidential='on'))
        self.finalize(page_path('edit_report_finalize', pk=pub.pk))
        pub.refresh_from_db()
        self.assertTrue(pub.confidential)

    def test_review_page_shows_the_value(self):
        self.client.post(page_path('add_report'), self.form_data(confidential='on'))
        response = self.client.get(page_path('add_report_review'))
        # Plain-text checks: the review page as a whole is not valid HTML (a stray </div>),
        # so html=True can't parse it.
        self.assertContains(response, '<th scope="row">Confidential</th>')
        self.assertContains(response, '<span class="review-confidential">Yes</span>')

        self.client.post(page_path('add_report'), self.form_data())
        response = self.client.get(page_path('add_report_review'))
        self.assertContains(response, '<span class="review-confidential">No</span>')
