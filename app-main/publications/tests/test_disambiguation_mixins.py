from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from unittest.mock import Mock, patch

from publications import models
from publications.mixins import disambiguation as disambiguation_mixins


class DummyParent:
    """Simple parent providing a clean() method that returns cleaned_data."""
    def __init__(self, *args, **kwargs):
        pass

    def clean(self):
        return getattr(self, 'cleaned_data', {})


class TestPersonDisambiguationMixins(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='tester', password='pw')

    def _attach_session(self, request):
        """Attach a real Django session to the request using SessionMiddleware."""
        # SessionMiddleware requires a get_response callable in newer Django
        middleware = SessionMiddleware(get_response=lambda req: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_check_disambiguation_needed_uses_service(self):
        # Build a minimal form-like object using the mixin
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        request = self.factory.get('/some/path/')
        request.user = self.user
        request = self._attach_session(request)

        form = F(request=request)
        form.cleaned_data = {'authors': ['Alice Smith']}
        form.fields = {'authors': None}

        # Attach a mocked service that reports names need resolution
        mock_service = Mock()
        mock_service.extract_persons_needing_disambiguation.return_value = ['Alice Smith']
        form.person_service = mock_service

        self.assertTrue(form.check_disambiguation_needed('authors'))
        mock_service.extract_persons_needing_disambiguation.assert_called()

    def test_start_disambiguation_workflow_starts_and_returns_redirect(self):
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        request = self.factory.post('/some/path/', data={'authors': ['Alice Smith']})
        request.user = self.user
        request = self._attach_session(request)

        form = F(request=request)
        form.cleaned_data = {'authors': ['Alice Smith']}
        form.fields = {'authors': None}

        # Control the service behaviour
        mock_service = Mock()
        mock_service.extract_persons_needing_disambiguation.return_value = ['Alice Smith']
        mock_service.start_workflow = Mock()
        form.person_service = mock_service

        # Patch reverse and redirect so we don't depend on URLconf
        with patch('publications.mixins.disambiguation.reverse', return_value='/review/'), \
             patch('publications.mixins.disambiguation.redirect', return_value='REDIRECT'):
            res = form.start_disambiguation_workflow('authors')

        self.assertEqual(res, 'REDIRECT')
        self.assertTrue(mock_service.start_workflow.called)

    def test_clean_creates_person_from_updated_form_data(self):
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        request = self.factory.get('/form/')
        request.user = self.user
        request = self._attach_session(request)

        # Put updated form data into session to simulate finalized workflow
        request.session['updated_form_data'] = {'authors': ['CREATE:John Doe']}
        request.session['workflow_updated_fields'] = ['authors']
        request.session.save()

        form = F(request=request)
        form.cleaned_data = {'authors': []}
        form.fields = {'authors': None}

        # Call clean() which should process the session-updated data
        cleaned = form.clean()

        # The cleaned_data for 'authors' should now be a QuerySet containing the new Person
        self.assertIn('authors', cleaned)
        self.assertIsInstance(cleaned['authors'], QuerySet)
        persons = list(cleaned['authors'])
        self.assertEqual(len(persons), 1)
        self.assertIn('John', persons[0].first)

        # Session keys should be removed
        self.assertNotIn('updated_form_data', request.session)
        self.assertNotIn('workflow_updated_fields', request.session)

    def test_has_and_get_workflow_redirect(self):
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        form = F(request=None)
        form._workflow_redirect = 'X'
        self.assertTrue(form.has_workflow_redirect())
        self.assertEqual(form.get_workflow_redirect(), 'X')

    def test_multiple_fields_only_some_need_disambiguation(self):
        """If multiple fields are given, only fields needing disambiguation should start workflows."""
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        request = self.factory.post('/multi/', data={'authors': ['Alice Smith'], 'supervisors': ['Existing Person']})
        request.user = self.user
        request = self._attach_session(request)

        form = F(request=request)
        form.cleaned_data = {'authors': ['Alice Smith'], 'supervisors': ['Existing Person']}
        form.fields = {'authors': None, 'supervisors': None}

        # Mock service to require disambiguation only for authors
        mock_service = Mock()
        mock_service.extract_persons_needing_disambiguation.side_effect = [['Alice Smith'], []]
        mock_service.start_workflow = Mock()
        form.person_service = mock_service

        with patch('publications.mixins.disambiguation.reverse', return_value='/review/'), \
             patch('publications.mixins.disambiguation.redirect', return_value='REDIR'):
            res = form.start_disambiguation_workflow(['authors', 'supervisors'])

        self.assertEqual(res, 'REDIR')
        # Only one workflow should be started (for authors)
        self.assertEqual(mock_service.start_workflow.call_count, 1)

    def test_clean_handles_mixed_create_and_existing_ids(self):
        """clean() should create missing persons for CREATE: and preserve existing IDs."""
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        # Create an existing person to reference
        existing = models.Person(created_by=self.user, modified_by=self.user)
        existing.set_names('Existing Person')
        existing.save()

        request = self.factory.get('/form2/')
        request.user = self.user
        request = self._attach_session(request)

        request.session['updated_form_data'] = {'authors': [f'CREATE:New Person', str(existing.pk)]}
        request.session['workflow_updated_fields'] = ['authors']
        request.session.save()

        form = F(request=request)
        form.cleaned_data = {'authors': []}
        form.fields = {'authors': None}

        cleaned = form.clean()
        self.assertIn('authors', cleaned)
        qs = list(cleaned['authors'])
        # Should contain two persons: newly created and the existing one
        self.assertEqual(len(qs), 2)
        names = [p.get_full_name() for p in qs]
        self.assertTrue(any('New Person' in n for n in names))
        self.assertTrue(any('Existing Person' in n for n in names))

    def test_start_disambiguation_uses_edit_mode_review_url(self):
        """When form is in edit mode (instance with pk), start_workflow should be given edit review_url."""
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        request = self.factory.post('/edit/', data={'authors': ['Alice Smith']})
        request.user = self.user
        request = self._attach_session(request)

        # Create a form instance with a pk to simulate edit mode
        form = F(request=request)
        form.instance = Mock()
        form.instance.pk = 123
        form.cleaned_data = {'authors': ['Alice Smith']}
        form.fields = {'authors': None}

        mock_service = Mock()
        mock_service.extract_persons_needing_disambiguation.return_value = ['Alice Smith']
        mock_service.start_workflow = Mock()
        form.person_service = mock_service

        # Ensure reverse is called with kwargs when in edit mode
        with patch('publications.mixins.disambiguation.reverse', return_value='/edit_review/'), \
             patch('publications.mixins.disambiguation.redirect', return_value='RED'):
            res = form.start_disambiguation_workflow('authors')

        self.assertEqual(res, 'RED')
        # Inspect how start_workflow was called and check kwargs included review_url
        self.assertTrue(mock_service.start_workflow.called)
        called_args, called_kwargs = mock_service.start_workflow.call_args
        self.assertIn('review_url', called_kwargs)
        self.assertEqual(called_kwargs['review_url'], '/edit_review/')

    def test_ordering_preserved_in_resolved_list(self):
        """Ensure the ordering of resolved person IDs is preserved in the queryset."""
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        # Create two existing persons
        p1 = models.Person(created_by=self.user, modified_by=self.user)
        p1.set_names('First Person')
        p1.save()
        p2 = models.Person(created_by=self.user, modified_by=self.user)
        p2.set_names('Second Person')
        p2.save()

        request = self.factory.get('/order/')
        request.user = self.user
        request = self._attach_session(request)

        # Mix existing IDs and CREATE: entries in a specific order
        request.session['updated_form_data'] = {'authors': [str(p2.pk), 'CREATE:Alice Z', str(p1.pk)]}
        request.session['workflow_updated_fields'] = ['authors']
        request.session.save()

        form = F(request=request)
        form.cleaned_data = {'authors': []}
        form.fields = {'authors': None}

        cleaned = form.clean()
        qs = list(cleaned['authors'])
        # Order should match p2, (new Alice), p1
        self.assertEqual(qs[0].pk, p2.pk)
        self.assertEqual(qs[2].pk, p1.pk)
        self.assertIn('Alice', qs[1].first)

    def test_multiple_create_entries(self):
        """Multiple CREATE: entries should all result in created Person objects in order."""
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        request = self.factory.get('/manycreate/')
        request.user = self.user
        request = self._attach_session(request)

        request.session['updated_form_data'] = {'authors': ['CREATE:One', 'CREATE:Two', 'CREATE:Three']}
        request.session['workflow_updated_fields'] = ['authors']
        request.session.save()

        form = F(request=request)
        form.cleaned_data = {'authors': []}
        form.fields = {'authors': None}

        cleaned = form.clean()
        qs = list(cleaned['authors'])
        self.assertEqual(len(qs), 3)
        names = [p.get_full_name() for p in qs]
        self.assertTrue(any('One' in n for n in names))
        self.assertTrue(any('Two' in n for n in names))
        self.assertTrue(any('Three' in n for n in names))

    def test_simultaneous_fields_with_interdependent_updates(self):
        """When multiple fields are updated in session, all should be processed and removed from session."""
        class F(disambiguation_mixins.PersonDisambiguationFormMixin, DummyParent):
            pass

        request = self.factory.get('/simul/')
        request.user = self.user
        request = self._attach_session(request)

        request.session['updated_form_data'] = {
            'authors': ['CREATE:Sim Author'],
            'supervisors': ['CREATE:Sim Supervisor', 'CREATE:Sim Supervisor2']
        }
        request.session['workflow_updated_fields'] = ['authors', 'supervisors']
        request.session.save()

        form = F(request=request)
        form.cleaned_data = {'authors': [], 'supervisors': []}
        form.fields = {'authors': None, 'supervisors': None}

        cleaned = form.clean()

        self.assertIn('authors', cleaned)
        self.assertIn('supervisors', cleaned)
        self.assertEqual(len(list(cleaned['authors'])), 1)
        self.assertEqual(len(list(cleaned['supervisors'])), 2)

        # Session entries should be cleared
        self.assertNotIn('updated_form_data', request.session)
        self.assertNotIn('workflow_updated_fields', request.session)
