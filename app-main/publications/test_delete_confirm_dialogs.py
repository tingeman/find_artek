"""Browser confirm dialogs only on the buttons that really delete (plan "features" T20).

A link or button that only opens a confirmation or review page has no ``confirm()``: the
page it opens asks. The button on that page that performs the deletion (the POST) asks once
more with a JS ``confirm()`` in one short style ("Delete this ...? This cannot be undone.",
"Remove this ... from ...?"). Cancel and Back buttons never ask, and no form has an
``onsubmit`` dialog (that would also fire for a Cancel submit button).

Also: the lists in the "cannot be deleted yet" alert of the report delete page are indented
so their numbers stay inside the box (base.css sets every padding to 0).

Users from ReportAccessTestBase: artek_editor ``editor``. Files are tiny fixtures written to
a temporary MEDIA_ROOT (FeatureDeleteTestBase).
"""
from html.parser import HTMLParser

from django.urls import reverse

from publications.models import Appendenciesship, FileObject, Publication
from publications.test_factories import page_path
from publications.test_feature_delete import FeatureDeleteTestBase
from publications.test_person_merge import MergeFixture

CANCEL_WORDS = ('Cancel', 'Back')


class _Clickables(HTMLParser):
    """Every <a>, <button> and <form> of a page: (tag, attrs, text)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self._open = []

    def handle_starttag(self, tag, attrs):
        if tag in ('a', 'button', 'form'):
            item = [tag, dict(attrs), '']
            self.items.append(item)
            if tag != 'form':
                self._open.append(item)

    def handle_endtag(self, tag):
        if tag in ('a', 'button') and self._open:
            self._open.pop()

    def handle_data(self, data):
        for item in self._open:
            item[2] += data


def clickables(html):
    parser = _Clickables()
    parser.feed(html)
    return [(tag, attrs, ' '.join(text.split())) for tag, attrs, text in parser.items]


class ConfirmAssertions:

    def page(self, path, method='get', data=None):
        response = getattr(self.client, method)(path, data or {})
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()

    def element(self, html, **match):
        """The single <a>/<button> whose attributes contain ``match``."""
        found = [(tag, attrs, text) for tag, attrs, text in clickables(html)
                 if tag != 'form' and all(attrs.get(k) == v for k, v in match.items())]
        self.assertEqual(len(found), 1, f'{match}: {found}')
        return found[0]

    def assertAsks(self, html, question, **match):
        _, attrs, _ = self.element(html, **match)
        self.assertEqual(attrs.get('onclick'), f"return confirm('{question}');")

    def assertDoesNotAsk(self, html, **match):
        _, attrs, _ = self.element(html, **match)
        self.assertNotIn('onclick', attrs)

    def assertCancelNeverAsks(self, html, expect_cancel=True):
        items = clickables(html)
        cancels = [(tag, attrs, text) for tag, attrs, text in items
                   if tag != 'form' and any(text.endswith(word) or text == word
                                            for word in CANCEL_WORDS)]
        if expect_cancel:
            self.assertTrue(cancels, 'no Cancel/Back button on the page')
        for tag, attrs, text in cancels:
            with self.subTest(cancel=text):
                self.assertNotIn('confirm(', attrs.get('onclick', ''))
        for tag, attrs, _ in items:
            if tag == 'form':
                self.assertNotIn('onsubmit', attrs)

    def confirm_count(self, html):
        return html.count('confirm(')


class DeleteConfirmDialogTests(ConfirmAssertions, FeatureDeleteTestBase):

    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def appendix(self, publication, name='appendix.txt'):
        fileobject = FileObject.objects.create(file=self.write(f'reports/1999/appendices/{name}'))
        Appendenciesship.objects.create(publication=publication, fileobject=fileobject)
        return fileobject

    # --- links that only open a confirmation page: no dialog

    def test_report_page_links_never_ask(self):
        feature = self.feature('Borehole A', self.pub)
        appendix = self.appendix(self.pub)
        html = self.page(page_path('report', pk=self.pub.pk))
        self.assertEqual(self.confirm_count(html), 0)
        self.assertDoesNotAsk(
            html, href=reverse('publications:delete_report', kwargs={'pk': self.pub.pk}),
            id='delete-report-link')
        self.assertDoesNotAsk(html, id='delete-all-features-link')
        self.assertDoesNotAsk(
            html, href=reverse('publications:delete_appendix',
                               kwargs={'pk': self.pub.pk, 'file_pk': appendix.pk}))
        self.assertDoesNotAsk(
            html, href=reverse('publications:delete_feature', kwargs={'pk': feature.pk})
            + f'?report={self.pub.pk}')

    def test_report_delete_page_with_features_never_asks(self):
        self.feature('Borehole A', self.pub)
        html = self.page(page_path('delete_report', pk=self.pub.pk))
        self.assertIn('id="delete-report-has-features"', html)
        self.assertEqual(self.confirm_count(html), 0)
        self.assertDoesNotAsk(html, id='delete-report-features-link')
        self.assertCancelNeverAsks(html)

    def test_bulk_delete_selection_page_never_asks(self):
        html = self.page(page_path('bulk_delete_publications'))
        self.assertEqual(self.confirm_count(html), 0)
        self.assertDoesNotAsk(html, name='delete', value='1')
        self.assertCancelNeverAsks(html)

    # --- the buttons that delete: one dialog each, Cancel never asks

    def test_report_delete_button_asks(self):
        html = self.page(page_path('delete_report', pk=self.other_pub.pk))
        self.assertAsks(html, 'Delete this report? This cannot be undone.',
                        name='action', value='delete')
        self.assertEqual(self.confirm_count(html), 1)
        self.assertDoesNotAsk(html, name='action', value='cancel')
        self.assertCancelNeverAsks(html)

    def test_delete_all_features_button_asks(self):
        self.feature('Borehole A', self.pub)
        html = self.page(page_path('delete_report_features', pk=self.pub.pk))
        self.assertAsks(html, 'Delete and remove the features listed? This cannot be undone.',
                        id='delete-report-features')
        self.assertEqual(self.confirm_count(html), 1)
        self.assertCancelNeverAsks(html)

    def test_delete_feature_button_asks(self):
        feature = self.feature('Borehole A', self.pub)
        html = self.page(page_path('delete_feature', pk=feature.pk) + f'?report={self.pub.pk}')
        self.assertAsks(html, 'Delete this feature? This cannot be undone.', id='delete-feature')
        self.assertEqual(self.confirm_count(html), 1)
        self.assertCancelNeverAsks(html)

    def test_remove_shared_feature_from_report_asks(self):
        feature = self.feature('Shared pit', self.pub, self.other_pub)
        html = self.page(page_path('delete_feature', pk=feature.pk) + f'?report={self.pub.pk}')
        # The number goes through escapejs ('-' becomes \u002D); the dialog shows 99-01.
        self.assertAsks(html, r'Remove this feature from report 99\u002D01?',
                        id='unlink-feature')
        self.assertNotIn('id="delete-feature"', html)
        self.assertEqual(self.confirm_count(html), 1)
        self.assertCancelNeverAsks(html)

    def test_remove_question_escapes_the_report_number(self):
        Publication.objects.filter(pk=self.pub.pk).update(number="99-'01")
        feature = self.feature('Shared pit', self.pub, self.other_pub)
        html = self.page(page_path('delete_feature', pk=feature.pk) + f'?report={self.pub.pk}')
        self.assertAsks(html, 'Remove this feature from report 99\\u002D\\u002701?',
                        id='unlink-feature')

    def test_delete_feature_file_and_image_buttons_ask(self):
        feature = self.feature('Borehole A', self.pub)
        fileobject = self.add_file(feature, 'data.txt')
        image = self.add_image(feature, 'photo.png')
        for kind, record in (('file', fileobject), ('image', image)):
            with self.subTest(kind=kind):
                html = self.page(page_path(f'delete_feature_{kind}', pk=feature.pk,
                                           record_pk=record.pk) + f'?report={self.pub.pk}')
                self.assertIn('id="feature-media-deleted"', html)
                self.assertAsks(html, f'Delete this {kind}? This cannot be undone.',
                                id='delete-feature-media')
                self.assertEqual(self.confirm_count(html), 1)
                self.assertCancelNeverAsks(html)

    def test_shared_feature_file_only_asks_to_remove(self):
        feature = self.feature('Borehole A', self.pub)
        other = self.feature('Borehole B', self.pub)
        fileobject = self.add_file(feature, 'data.txt')
        other.files.add(fileobject)
        html = self.page(page_path('delete_feature_file', pk=feature.pk,
                                   record_pk=fileobject.pk) + f'?report={self.pub.pk}')
        self.assertIn('id="feature-media-kept"', html)
        self.assertAsks(html, 'Remove this file from the feature?', id='delete-feature-media')

    def test_delete_appendix_button_asks(self):
        appendix = self.appendix(self.pub)
        html = self.page(page_path('delete_appendix', pk=self.pub.pk, file_pk=appendix.pk))
        self.assertAsks(html, 'Delete this appendix? This cannot be undone.',
                        id='delete-appendix')
        self.assertEqual(self.confirm_count(html), 1)
        self.assertCancelNeverAsks(html)

    def test_bulk_delete_confirm_button_asks(self):
        free = Publication.objects.create(type=self.pubtype, title='Free report',
                                          number='99-03', year=1999, verified=True)
        html = self.page(page_path('bulk_delete_publications'), 'post',
                         {'selected_publications': [str(free.pk), str(self.other_pub.pk)]})
        self.assertAsks(html, 'Delete 2 reports? This cannot be undone.',
                        id='bulk-delete-confirm')
        self.assertEqual(self.confirm_count(html), 1)
        self.assertDoesNotAsk(html, name='cancel', value='1')
        self.assertCancelNeverAsks(html)
        html = self.page(page_path('bulk_delete_publications'), 'post',
                         {'selected_publications': [str(free.pk)]})
        self.assertAsks(html, 'Delete 1 report? This cannot be undone.',
                        id='bulk-delete-confirm')

    # --- T20 item 2: the alert's lists stay inside the box

    def test_delete_warning_lists_are_indented(self):
        self.feature('Borehole A', self.pub)
        html = self.page(page_path('delete_report', pk=self.pub.pk))
        style = html.split('.delete-warning ol,', 1)[1].split('}', 1)[0]
        self.assertIn('.delete-warning ul', style)
        self.assertIn('padding-left: 2em', style)
        self.assertIn('list-style: decimal outside', html)


class PersonMergeConfirmDialogTests(ConfirmAssertions, MergeFixture):

    def test_merge_button_asks_and_back_does_not(self):
        self.client.force_login(self.editor)
        html = self.page(page_path('person_merge_confirm', pk=self.kept.pk), 'post',
                         {'merge': [str(self.dup.pk)]})
        self.assertAsks(html, 'Merge these persons? The others are deleted. '
                              'This cannot be undone.', id='person-merge-do')
        self.assertEqual(self.confirm_count(html), 1)
        self.assertCancelNeverAsks(html)
