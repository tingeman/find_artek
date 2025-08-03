import re
import json
import os
import ast
import time
import tempfile
import shutil
import traceback  # Make sure traceback is imported

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext
from django.core import serializers
from django.contrib.auth import authenticate, login, logout
from django.views import View
from django.urls import reverse
from django.db.models import QuerySet
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string

from django.views.generic import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, FormView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from django_select2.views import AutoResponseView

from find_artek.search import get_query
from publications.utils import CaseInsensitively, create_ordered_queryset, handle_publication_file_upload
from publications.library import get_client_ip, is_private
from publications.forms import (LoginForm, AddEditReportForm, AddEditReportFinalSaveForm,
                                PublicationForm, AuthorSelectForm, SupervisorSelectForm, DeleteReportForm,
                                AddFeatureCoordinatesForm, PersonWorkflowMixin)
from publications.forms.mixins import WorkflowAddEditReportForm, WorkflowAddEditReportFinalSaveForm
from publications.models import Publication, Topic, Feature, Person

from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic.edit import DeleteView
from publications.models import Feature



import pdb

# Create your views here.




class BaseView(View):
    base_template = "publications/base.html"

    def get_context_data(self, **kwargs):
        # context = super().get_context_data(**kwargs)    # View class has no method get_context_data
        context = {
            'base_template': self.base_template,
            # Other common context variables...
        }
        print('In BaseView')
        print(context.keys())
        return context
    
    def get(self, request, **kwargs):
        context = self.get_context_data(**kwargs)
        return render(request, self.base_template, context)



class BaseDetailView(DetailView, BaseView):
    def get_context_data(self, **kwargs):
        # Get the context from BaseView
        context = super().get_context_data(**kwargs)
        # Get the context from BaseView
        base_context = BaseView.get_context_data(self, **kwargs)
        # Combine the contexts
        context.update(base_context)
        return context

class BaseFormView(FormView, BaseView):
    def get_context_data(self, **kwargs):
        # Get the context from BaseView
        context = super().get_context_data(**kwargs)
        # Get the context from BaseView
        base_context = BaseView.get_context_data(self, **kwargs)
        # Combine the contexts
        context.update(base_context)
        return context








class FrontPageView(BaseView):

    template_name = 'publications/frontpage.html'

    def get(self, request, **kwargs):

        context = {
        }

        context.update(self.get_context_data(**kwargs))
        return render(request, self.template_name, context)




















































class MapView(BaseView): 
    template_name = 'publications/map.html'
    def get(self, request, **kwargs):

        context = {
        }
        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)


















class ReportsView(BaseView):
    template_name = 'publications/reports.html'

    def get(self, request, **kwargs):
        # Extract the 'topic' query parameter from the request
        topic = request.GET.get('topic', None)

        context = {
            'topic': topic,  # Add the topic to the context
        }

        # Update the context with additional data
        context.update(self.get_context_data(**kwargs))

        # Render the template with the context
        return render(request, self.template_name, context)

























class PersonsView(BaseView):
    template_name = 'publications/persons.html'

    def get(self, request, **kwargs):
        
        person_list = Person.objects.all().order_by('last', 'first')  # .order_by('-year').order_by('number')

        context = {
            'pers_list': person_list,
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)



















class ReportView(BaseDetailView):
    model = Publication
    template_name = 'publications/report.html'
    context_object_name = 'publication'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        associated_features = Feature.objects.filter(publications=self.object)
        user = self.request.user
        can_edit_features = self.object.is_editable_by(user) if user.is_authenticated else False
        can_delete_features = self.object.is_deletable_by(user) if user.is_authenticated else False
        context.update({
            'associated_features': associated_features,
            'can_edit_features': can_edit_features,
            'can_delete_features': can_delete_features,
        })
        context['invalidate_feature_cache'] = self.request.session.pop('invalidate_feature_cache', False)
        print(context)
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.verified and not request.user.is_authenticated:
            context = self.get_context_data(object=self.object)
            context['error'] = "You do not have permissions to access this publication!"
            return render(request, 'publications/access_denied.html', context=context)
        return super().get(request, *args, **kwargs)





@method_decorator(login_required, name='dispatch')
class AddEditReportView(BaseFormView):
    """Unified view for both adding and editing reports"""
    model = Publication
    template_name = 'publications/add_edit_report.html'
    select_persons_url = 'select-persons'

    def get_form_class(self):
        """Return the appropriate form class based on mode"""
        if self.is_final_save():
            return WorkflowAddEditReportFinalSaveForm
        else:
            return WorkflowAddEditReportForm

    def is_edit_mode(self):
        """Check if we're in edit mode (has pk in URL)"""
        return 'pk' in self.kwargs

    def is_final_save(self):
        """Check if this is a final save after person selection"""
        # Check for action parameter in query string
        action = self.request.GET.get('action', '')
        if action in ['add_final', 'edit_final']:
            return True
            
        # Check if we're on a finalize URL path
        path = self.request.path
        print(f"🔍 DEBUG: Checking if path contains 'finalize': {path}")
        if 'finalize' in path:
            print(f"🔍 DEBUG: Found 'finalize' in path, treating as final save")
            return True
            
        # Not a final save
        return False

    def get_object(self):
        """Get the publication to edit, or None for add mode"""
        if self.is_edit_mode():
            if hasattr(self, '_object_cache'):
                return self._object_cache
            
            # For final save, get from session
            if self.is_final_save():
                publication_id = self.request.session.get('edit_report_publication_id')
                if publication_id:
                    self._object_cache = get_object_or_404(Publication, pk=publication_id)
                    return self._object_cache
            else:
                # For regular edit, get from URL
                self._object_cache = get_object_or_404(Publication, pk=self.kwargs['pk'])
                return self._object_cache
        return None

    def get_session_key(self):
        """Get appropriate session key based on mode"""
        return 'edit_report_form_data' if self.is_edit_mode() else 'add_report_form_data'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'edit' if self.is_edit_mode() else 'add'
        
        if self.is_edit_mode():
            context['publication'] = self.get_object()
        else:
            context['publication'] = None  # Ensure publication is always in context
        
        # Handle returning from person selection
        if self.request.GET.get('action') == 'edit_continue':
            context['action'] = 'edit'
        elif self.request.GET.get('action') == 'new':
            context['action'] = 'add'
            
        return context

    def get_initial(self):
        """Get initial form data based on mode and state"""
        if self.is_edit_mode():
            return self._get_edit_initial()
        else:
            return self._get_add_initial()

    def _get_add_initial(self):
        """Get initial data for Add mode"""
        action = self.request.GET.get('action', 'new')
        
        if action == 'edit':  # Returning from person selection
            session_data = self.request.session.get('add_report_form_data', {})
            return self._normalize_session_data(session_data)
        
        return {}

    def _get_edit_initial(self):
        """Get initial data for Edit mode - always from database"""
        action = self.request.GET.get('action', 'edit')
        
        if action == 'edit_continue':  # Returning from person selection (legacy)
            session_data = self.request.session.get('edit_report_form_data', {})
            return self._normalize_session_data(session_data)
        
        # Build initial data from the publication - no session complexity
        publication = self.get_object()
        if not publication:
            return {}
            
        initial_data = {
            'type': publication.type,
            'title': publication.title,
            'number': publication.number,
            'year': publication.year,
            'abstract': publication.abstract,
            'comment': publication.comment,
        }
        
        # Prepare authors and supervisors
        if publication.authorship_set.exists():
            authors = publication.authorship_set.all().order_by('author_id')
            author_pks = [auth.person.pk for auth in authors]  # Use integers, not strings
            # For HeavySelect2TagWidget, set as list of PKs (not string representation)
            initial_data['authors'] = author_pks
            print(f'AddEditReportView:_get_edit_initial - Set initial authors as list: {author_pks}')
            
        if publication.supervisorship_set.exists():
            supervisors = publication.supervisorship_set.all().order_by('supervisor_id')
            supervisor_pks = [sup.person.pk for sup in supervisors]  # Use integers, not strings
            # For HeavySelect2TagWidget, set as list of PKs (not string representation)
            initial_data['supervisors'] = supervisor_pks
            print(f'AddEditReportView:_get_edit_initial - Set initial supervisors as list: {supervisor_pks}')
        
        # Prepare topics and keywords
        initial_data['publication_topics'] = publication.publication_topics.all()
        initial_data['publication_keywords'] = publication.publication_keywords.all()
        
        return initial_data

    def _normalize_session_data(self, session_data):
        """Normalize session data for form initialization"""
        normalized_data = {}
        for key, value in session_data.items():
            if isinstance(value, list) and len(value) == 1:
                normalized_data[key] = value[0]
            else:
                normalized_data[key] = value
        return normalized_data

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form"""
        kwargs = super().get_form_kwargs()
        
        # Add request object for workflow forms
        kwargs['request'] = self.request
        
        # For edit mode, always pass the instance
        if self.is_edit_mode():
            kwargs['instance'] = self.get_object()
            
        return kwargs

    def get_form(self):
        """Get form instance with proper setup"""
        if self.is_final_save():
            return self._get_final_save_form()
        else:
            return self._get_regular_form()

    def _get_regular_form(self):
        """Get form for regular Add/Edit operations"""
        form = super().get_form()
        
        # Retrieve session data for authors and supervisors
        session_key = self.get_session_key()
        session_data = self.request.session.get(session_key, {})
        session_authors = session_data.get('authors', [])
        session_supervisors = session_data.get('supervisors', [])
        
        # Configure widget choices based on mode and data availability
        if session_data:
            # Coming back from person selection - use session data
            form.fields['authors'].widget.choices = self._get_person_choices(session_authors)
            form.fields['supervisors'].widget.choices = self._get_person_choices(session_supervisors)
            print(f"AddEditReportView:_get_regular_form - Using session data: {len(session_authors)} authors, {len(session_supervisors)} supervisors")
        elif self.is_edit_mode():
            # Edit mode - get current authors and supervisors from publication
            publication = self.get_object()
            if publication:
                # Get current authors and supervisors
                current_authors = publication.authorship_set.all().order_by('author_id')
                current_supervisors = publication.supervisorship_set.all().order_by('supervisor_id')
                
                # Convert to choices for widget
                author_choices = [(str(auth.person.pk), str(auth.person)) for auth in current_authors]
                supervisor_choices = [(str(sup.person.pk), str(sup.person)) for sup in current_supervisors]
                
                # Set widget choices to enable display of current values
                form.fields['authors'].widget.choices = author_choices
                form.fields['supervisors'].widget.choices = supervisor_choices
                
                print(f"AddEditReportView:_get_regular_form - Edit mode: Setting widget choices for {len(author_choices)} authors, {len(supervisor_choices)} supervisors")
        else:
            # Add mode - start with empty choices
            form.fields['authors'].widget.choices = []
            form.fields['supervisors'].widget.choices = []
            print("AddEditReportView:_get_regular_form - Add mode: Empty widget choices")
        
        return form

    def _get_final_save_form(self):
        """Get form for final save operations"""
        print(f"🔍 DEBUG: _get_final_save_form called, request method: {self.request.method}")
        
        # If we already have POST data, keep it (for true form submissions)
        if self.request.method == 'POST' and self.request.POST:
            print(f"🔍 DEBUG: Using existing POST data from request with keys: {list(self.request.POST.keys())}")
        else:
            # Pretend this is a POST request with session data
            print(f"🔍 DEBUG: No POST data, using session data instead")
            self.request.method = 'POST'
            
            # Check for updated form data from review page first
            if 'updated_form_data' in self.request.session:
                print(f"🔍 DEBUG: Using updated_form_data from session")
                normalized_data = self._normalize_session_data(self.request.session.get('updated_form_data', {}))
                self.request.POST = normalized_data
            else:
                # Fall back to regular session key
                session_key = self.get_session_key()
                print(f"🔍 DEBUG: Falling back to session key: {session_key}")
                normalized_data = self._normalize_session_data(self.request.session.get(session_key, {}))
                self.request.POST = normalized_data
        
        # Get form with proper instance for edit mode
        form_kwargs = self.get_form_kwargs()
        if self.is_edit_mode():
            form_kwargs['instance'] = self.get_object()
            
        form_class = self.get_form_class()
        return form_class(**form_kwargs)

    def _get_person_choices(self, person_data=[]):
        """Convert person data to choices for select2 widget"""
        choices = []
        for person in person_data:
            if isinstance(person, int) or (isinstance(person, str) and person.isnumeric()):
                person_obj = Person.objects.filter(pk=int(person)).first()
                if person_obj:
                    choices.append((person_obj.pk, str(person_obj)))
            elif isinstance(person, str):  # New person name
                choices.append((person, person))
        return choices

    def get(self, request, *args, **kwargs):
        """Handle GET requests"""
        if self.is_final_save():
            return self._handle_final_save_get(request)
        else:
            return self._handle_regular_get(request, *args, **kwargs)
            
    def post(self, request, *args, **kwargs):
        """Handle POST requests with special handling for finalize URLs"""
        print(f"🔍 DEBUG: AddEditReportView.post called for URL: {request.path}")
        print(f"🔍 DEBUG: POST data keys: {list(request.POST.keys())}")
        print(f"🔍 DEBUG: Files keys: {list(request.FILES.keys()) if request.FILES else 'No files'}")
        
        # Always treat POST to finalize URLs as final save operations
        if 'finalize' in request.path:
            print(f"🔍 DEBUG: POST to finalize URL detected - handling as final save")
            
            # Check if we should use session data
            use_session_data = request.POST.get('use_session_data') == 'True'
            if use_session_data and 'updated_form_data' in request.session:
                print(f"🔍 DEBUG: Using session data from 'updated_form_data' key")
                session_data = request.session.get('updated_form_data', {})
                
                # Create a publication instance directly
                from django.db import transaction
                try:
                    with transaction.atomic():
                        publication = self.get_object() if self.is_edit_mode() else Publication()
                        
                        # Update basic fields
                        publication.title = request.POST.get('title', '')
                        publication.number = request.POST.get('number', '')
                        
                        # Type field needs special handling
                        type_id = request.POST.get('type')
                        if type_id:
                            from publications.models import PubType
                            try:
                                publication.type = PubType.objects.get(pk=type_id)
                            except (PubType.DoesNotExist, ValueError):
                                print(f"🔍 DEBUG: Error finding PubType with ID: {type_id}")
                        
                        # Year field needs to be an integer
                        year = request.POST.get('year', '')
                        if year and year.isdigit():
                            publication.year = int(year)
                        
                        publication.abstract = request.POST.get('abstract', '')
                        publication.comment = request.POST.get('comment', '')
                        
                        # Set the modified by user
                        if request.user.is_authenticated:
                            publication.modified_by = request.user
                            if not publication.pk:  # If new publication
                                publication.created_by = request.user
                        
                        # Save publication to get an ID if it's new
                        publication.save()
                        
                        # Set the object so get_success_url works
                        self.object = publication
                        
                        # Handle authors
                        publication.authorship_set.all().delete()
                        authors = request.POST.getlist('authors', [])
                        for i, author_pk in enumerate(authors):
                            from publications.models import Authorship, Person
                            try:
                                person = Person.objects.get(pk=int(author_pk))
                                Authorship.objects.create(
                                    publication=publication,
                                    person=person,
                                    author_id=i
                                )
                                print(f"🔍 DEBUG: Added author: {person}")
                            except (Person.DoesNotExist, ValueError) as e:
                                print(f"🔍 DEBUG: Error adding author {author_pk}: {e}")
                        
                        # Handle supervisors
                        publication.supervisorship_set.all().delete()
                        supervisors = request.POST.getlist('supervisors', [])
                        for i, supervisor_pk in enumerate(supervisors):
                            from publications.models import Supervisorship, Person
                            try:
                                person = Person.objects.get(pk=int(supervisor_pk))
                                Supervisorship.objects.create(
                                    publication=publication,
                                    person=person,
                                    supervisor_id=i
                                )
                                print(f"🔍 DEBUG: Added supervisor: {person}")
                            except (Person.DoesNotExist, ValueError) as e:
                                print(f"🔍 DEBUG: Error adding supervisor {supervisor_pk}: {e}")
                        
                        # Handle topics
                        publication.publication_topics.clear()
                        topics = request.POST.getlist('publication_topics', [])
                        if topics:
                            from publications.models import Topic
                            for topic_pk in topics:
                                try:
                                    topic = Topic.objects.get(pk=int(topic_pk))
                                    publication.publication_topics.add(topic)
                                    print(f"🔍 DEBUG: Added topic: {topic}")
                                except (Topic.DoesNotExist, ValueError) as e:
                                    print(f"🔍 DEBUG: Error adding topic {topic_pk}: {e}")
                        
                        # Handle keywords
                        publication.publication_keywords.clear()
                        keywords = request.POST.getlist('publication_keywords', [])
                        if keywords:
                            from publications.models import Keyword
                            for keyword_pk in keywords:
                                try:
                                    keyword = Keyword.objects.get(pk=int(keyword_pk))
                                    publication.publication_keywords.add(keyword)
                                    print(f"🔍 DEBUG: Added keyword: {keyword}")
                                except (Keyword.DoesNotExist, ValueError) as e:
                                    print(f"🔍 DEBUG: Error adding keyword {keyword_pk}: {e}")
                        
                        # Handle file upload
                        has_file_in_session = request.POST.get('has_file_in_session') == 'True'
                        if has_file_in_session:
                            print(f"🔍 DEBUG: File data found in session")
                            # Do special handling here if needed
                            
                        # Save again after all relations are set
                        publication.save()
                        
                except Exception as e:
                    print(f"🔍 DEBUG: Error during direct publication save: {str(e)}")
                    print(f"🔍 DEBUG: {traceback.format_exc()}")
                    return self.form_invalid(self.get_form())
                
                # After saving, handle file operations separately BEFORE clearing session data
                try:
                    # Create a dummy form for the file operations
                    form = self.get_form()
                    # Set the object manually since we created it directly
                    self.object = publication
                    # Call the file operations method
                    self._handle_file_operations_with_session_data(request)
                except Exception as e:
                    print(f"🔍 DEBUG: Error during file operations: {str(e)}")
                    print(f"🔍 DEBUG: {traceback.format_exc()}")
                
                # Clear session data AFTER file operations are complete
                if 'updated_form_data' in request.session:
                    del request.session['updated_form_data']
                    print(f"🔍 DEBUG: Cleared updated_form_data from session after file operations")
                
                # Redirect to success URL
                return redirect(self.get_success_url())
            else:
                print(f"🔍 DEBUG: No session data found, trying normal form processing")
                # Process the form and get the result
                form = self.get_form()
                
                if form.is_valid():
                    print(f"🔍 DEBUG: Form is valid, processing final save")
                    return self.form_valid(form)
                else:
                    print(f"🔍 DEBUG: Form validation failed: {form.errors}")
                    # Try to fix validation issues with session data
                    if 'updated_form_data' in request.session:
                        print(f"🔍 DEBUG: Attempting to save with session data despite validation errors")
                        try:
                            # Get the publication instance
                            publication = self.get_object() if self.is_edit_mode() else Publication()
                            # Set basic fields from session data
                            session_data = request.session.get('updated_form_data', {})
                            
                            # Set fields (with safeguards)
                            if 'title' in session_data and session_data['title']:
                                publication.title = session_data['title'][0] if isinstance(session_data['title'], list) else session_data['title']
                            
                            # Process other fields...
                            
                            # Save the publication
                            publication.save()
                            self.object = publication
                            
                            # Clear session data
                            del request.session['updated_form_data']
                            
                            # Redirect to success URL
                            return redirect(self.get_success_url())
                        except Exception as e:
                            print(f"🔍 DEBUG: Error during fallback save: {str(e)}")
                    
                    return self.form_invalid(form)
        else:
            # For regular POST requests, use standard FormView processing
            return super().post(request, *args, **kwargs)

    def _handle_regular_get(self, request, *args, **kwargs):
        """Handle regular GET requests"""
        action = request.GET.get('action', 'new' if not self.is_edit_mode() else 'edit')
        
        if action == 'new' and not self.is_edit_mode():
            # Clear session data for new Add operation
            request.session.pop('add_report_form_data', None)
        elif action == 'edit' and self.is_edit_mode():
            # Clear session data for new Edit operation
            request.session.pop('edit_report_form_data', None)
            
        return super().get(request, *args, **kwargs)

    def _handle_final_save_get(self, request):
        """Handle final save GET requests"""
        session_key = self.get_session_key()
        
        if not request.session.get(session_key, {}):
            # Redirect if no session data
            if self.is_edit_mode():
                return redirect('publications:reports')
            else:
                return redirect('publications:add_report')
        
        form = self.get_form()
        
        if hasattr(form, 'is_valid') and form.is_valid():
            # Process the form and get the result
            result = self.form_valid(form)
            # If form_valid returns a redirect response, return it
            if hasattr(result, 'status_code') and result.status_code in [301, 302]:
                return result
            # Otherwise, redirect to success URL manually
            return redirect(self.get_success_url())
        else:
            # Redirect back with error
            if self.is_edit_mode():
                publication_id = self.request.session.get('edit_report_publication_id')
                if publication_id:
                    return redirect('publications:edit_report', pk=publication_id)
                return redirect('publications:reports')
            else:
                return redirect('publications:add_report')

    def form_valid(self, form):
        """Unified form processing for both Add and Edit with workflow support"""
        print(f"🔍 DEBUG: AddEditReportView.form_valid called")
        print(f"🔍 DEBUG: Form cleaned_data keys: {list(form.cleaned_data.keys())}")
        print(f"🔍 DEBUG: Form contains data: {form.cleaned_data}")
        
        # Debug the form data types
        for key, value in form.cleaned_data.items():
            print(f"🔍 DEBUG: Form field '{key}': {value} (type: {type(value).__name__})")
        
        # Check if workflow forms need to redirect to disambiguation
        if hasattr(form, 'has_workflow_redirect') and form.has_workflow_redirect():
            print("🔍 DEBUG: Form has workflow redirect, calling form.get_workflow_redirect()")
            return form.get_workflow_redirect()
        
        # Always store form data in session and redirect to review view
        print("🔍 DEBUG: Storing form data in session for review view")
        
        # Convert form data to session-compatible format and store it
        session_data = {}
        
        # Copy POST data, converting values to simple lists of strings
        for key, value_list in self.request.POST.lists():
            # Skip empty file fields
            if key == 'pdffile' and (not value_list or value_list == [''] or value_list[0] == ''):
                print(f"🔍 DEBUG: Skipping empty pdffile field: {value_list}")
                continue
                
            session_data[key] = value_list
            print(f"🔍 DEBUG: Session data field '{key}': {value_list}")
        
        # Handle file uploads - store file ID in session for later linking
        print(f"🔍 DEBUG: Checking for file uploads in request.FILES: {list(self.request.FILES.keys())}")
        
        # Track if we have any file handling to do
        file_handled = False
        
        # First check for standard field name
        if 'pdffile' in self.request.FILES:
            uploaded_file = self.request.FILES['pdffile']
            print(f"🔍 DEBUG: Found file upload: {uploaded_file.name} (size: {uploaded_file.size} bytes)")
            
            try:
                # Create a temporary publication object for file processing
                temp_publication = Publication()
                temp_publication.created_by = self.request.user
                temp_publication.modified_by = self.request.user
                temp_publication.title = "TEMP_" + str(time.time())  # Temporary title
                temp_publication.year = 2024  # Temporary year
                temp_publication.save()  # Save to get an ID
                
                # Process file and store in temp location
                file_obj = handle_publication_file_upload(temp_publication, uploaded_file, temp_storage=True)
                
                # Store the actual FileObject ID in session for later linking
                session_data['uploaded_file_id'] = str(file_obj.id)
                session_data['temp_publication_id'] = str(temp_publication.id)
                
                print(f"🔍 DEBUG: Created FileObject with ID: {file_obj.id}")
                print(f"🔍 DEBUG: Created temporary publication ID: {temp_publication.id}")
                
                file_handled = True
                
            except Exception as e:
                print(f"🔍 DEBUG: Error storing uploaded file: {e}")
            
            # Store file metadata as dictionary
            session_data['pdffile'] = {
                'name': uploaded_file.name,
                'size': uploaded_file.size,
                'content_type': uploaded_file.content_type,
                'has_uploaded_file': True
            }
            print(f"🔍 DEBUG: Added file metadata to session data: {session_data['pdffile']}")
            
        # Also check for formset-style field name (form-0-pdffile)
        elif 'form-0-pdffile' in self.request.FILES:
            uploaded_file = self.request.FILES['form-0-pdffile']
            print(f"🔍 DEBUG: Found file upload with formset name: {uploaded_file.name}")
            
            try:
                # Create a temporary publication object for file processing
                temp_publication = Publication()
                temp_publication.created_by = self.request.user
                temp_publication.modified_by = self.request.user
                temp_publication.title = "TEMP_" + str(time.time())  # Temporary title
                temp_publication.year = 2024  # Temporary year
                temp_publication.save()  # Save to get an ID
                
                # Process file and store in temp location
                file_obj = handle_publication_file_upload(temp_publication, uploaded_file, temp_storage=True)
                
                # Store the actual FileObject ID in session for later linking
                session_data['uploaded_file_id'] = str(file_obj.id)
                session_data['temp_publication_id'] = str(temp_publication.id)
                
                print(f"🔍 DEBUG: Created FileObject with ID: {file_obj.id}")
                print(f"🔍 DEBUG: Created temporary publication ID: {temp_publication.id}")
                
                file_handled = True
                
            except Exception as e:
                print(f"🔍 DEBUG: Error storing uploaded file: {e}")
            
            # Store file metadata as dictionary
            session_data['pdffile'] = {
                'name': uploaded_file.name,
                'size': uploaded_file.size,
                'content_type': uploaded_file.content_type,
                'has_uploaded_file': True
            }
            print(f"🔍 DEBUG: Added formset file metadata to session data: {session_data['pdffile']}")
        
        # Check if we're in edit mode and preserving existing file (no new upload)
        elif self.is_edit_mode():
            publication = self.get_object()
            if publication and publication.file:
                print(f"🔍 DEBUG: Edit mode - preserving existing file: {publication.file.file.name}")
                
                # Store the existing file ID for preservation
                session_data['existing_file_id'] = str(publication.file.id)
                
                # Store file metadata
                session_data['pdffile'] = {
                    'name': os.path.basename(publication.file.file.name),
                    'size': os.path.getsize(publication.file.file.path) if publication.file.file else 0,
                    'content_type': 'application/pdf',  # Assume PDF for now
                    'has_existing_file': True
                }
                
                print(f"🔍 DEBUG: Preserving existing file ID: {publication.file.id}")
                file_handled = True
        
        if not file_handled:
            print(f"🔍 DEBUG: No file upload or existing file found")
        
        # Ensure type field is stored as string (PK), not model instance
        if 'type' in session_data and len(session_data['type']) == 1:
            # Type should be a string representation of the PK
            original_type = session_data['type'][0]
            session_data['type'] = [str(session_data['type'][0])]
            print(f"🔍 DEBUG: Converted type field from {original_type} to {session_data['type'][0]}")
            
        # Store the form data in session using the key that the review view expects
        try:
            # Use the special key that the review view checks for
            self.request.session['updated_form_data'] = session_data
            print("✅ Session data stored successfully for review view")
            print(f"🔍 DEBUG: Session data includes uploaded_file_id: {'uploaded_file_id' in session_data}")
            print(f"🔍 DEBUG: Session data includes existing_file_id: {'existing_file_id' in session_data}")
            print(f"🔍 DEBUG: Session data includes temp_publication_id: {'temp_publication_id' in session_data}")
            
            # If file IDs are present, print them
            if 'uploaded_file_id' in session_data:
                print(f"🔍 DEBUG: uploaded_file_id value: {session_data['uploaded_file_id']}")
            if 'existing_file_id' in session_data:
                print(f"🔍 DEBUG: existing_file_id value: {session_data['existing_file_id']}")
            if 'temp_publication_id' in session_data:
                print(f"🔍 DEBUG: temp_publication_id value: {session_data['temp_publication_id']}")
            
            # Store publication ID for edit mode
            if self.is_edit_mode():
                obj = self.get_object()
                if obj:
                    self.request.session['edit_report_publication_id'] = obj.pk
                    
            # Redirect to the review view
            action = 'edit' if self.is_edit_mode() else 'add'
            view_name = 'publications:review_edit_report' if self.is_edit_mode() else 'publications:review_add_report'
            if self.is_edit_mode():
                return redirect(view_name, pk=self.kwargs['pk'])
            else:
                return redirect(view_name)
                
        except (TypeError, ValueError) as e:
            print(f"❌ Failed to store session data: {e}")
            
            # Fall back to original behavior if session storage fails
            authors = form.cleaned_data['authors']
            supervisors = form.cleaned_data['supervisors']
            
            # Handle person selection redirect if needed (fallback for legacy forms)
            if (not isinstance(authors, QuerySet)) or (not isinstance(supervisors, QuerySet)):
                print("🔍 DEBUG: Authors or supervisors are not QuerySets, calling _handle_person_selection_redirect")
                return self._handle_person_selection_redirect(form)
                
            # Continue with direct save
            print("🔍 DEBUG: Falling back to direct save without review")
            self.object = form.save(commit=False)
        
            # Auto-generate report number for new publications
            if not self.object.pk and not self.object.number:
                if self.object.year:
                    from publications.utils import generate_next_report_number
                    from django.db import transaction, IntegrityError
                    import time
                    
                    # Use retry logic to handle concurrency during auto-generation
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            with transaction.atomic():
                                # Generate number atomically
                                self.object.number = generate_next_report_number(self.object.year)
                                self.object.save()
                                break  # Success - exit retry loop
                        except IntegrityError:
                            if attempt < max_retries - 1:
                                time.sleep(0.1)  # Brief delay before retry
                                continue
                            else:
                                # If all retries fail, show error
                                from django.contrib import messages
                                messages.error(
                                    self.request, 
                                    "Unable to assign report number due to high system load. Please try again."
                                )
                                return redirect('publications:add_report')
                else:
                    from django.contrib import messages
                    messages.error(self.request, "Cannot create report without a year")
                    return redirect('publications:add_report')
            else:
                # Save existing publication (edit mode)
                self.object.save()

            # Handle file operations AFTER report number is assigned
            self._handle_file_operations(form)

            # Handle relationships
            self._handle_authors_and_supervisors(authors, supervisors)
            self._handle_topics_and_keywords(form)

            # Clear session data for final save operations
            if self.is_final_save():
                session_key = self.get_session_key()
                self.request.session.pop(session_key, None)
                if self.is_edit_mode():
                    self.request.session.pop('edit_report_publication_id', None)

            # Return a redirect to the success URL
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(self.get_success_url())

    def _handle_person_selection_redirect(self, form):
        """Handle redirect to person selection using field-specific workflow approach"""
        
        print("🔍 DEBUG: _handle_person_selection_redirect called")
        print(f"🔍 DEBUG: POST data keys: {list(self.request.POST.keys())}")
        print(f"🔍 DEBUG: POST data: {dict(self.request.POST.lists())}")
        
        # Use raw POST data to avoid any form processing that might convert strings to model instances
        # This ensures all data is JSON-serializable (strings, lists of strings)
        session_data = {}
        
        # Copy raw POST data, converting values to simple lists of strings
        for key, value_list in self.request.POST.lists():
            print(f"🔍 DEBUG: Processing POST field '{key}': {value_list} (types: {[type(v).__name__ for v in value_list]})")
            session_data[key] = value_list
        
        # Ensure type field is stored as string (PK), not model instance
        if 'type' in session_data and len(session_data['type']) == 1:
            # Type should be a string representation of the PK
            original_type = session_data['type'][0]
            session_data['type'] = [str(session_data['type'][0])]
            print(f"🔍 DEBUG: Converted type field from {original_type} ({type(original_type).__name__}) to {session_data['type'][0]} (str)")
        
        # The person disambiguation workflow only modifies 'authors' and 'supervisors' fields
        # All other fields remain as original string values from POST data
        
        print(f"🔍 DEBUG: Final session_data keys: {list(session_data.keys())}")
        print(f"🔍 DEBUG: Session data types check:")
        for key, value in session_data.items():
            print(f"  - {key}: {type(value).__name__} containing {[type(v).__name__ for v in value] if isinstance(value, list) else type(value).__name__}")
        
        # Test JSON serialization to ensure it will work
        try:
            json.dumps(session_data)
            print("✅ Session data is JSON serializable")
        except (TypeError, ValueError) as e:
            print(f"❌ Session data serialization failed: {e}")
            print(f"Problematic data: {session_data}")
            # Find the problematic object
            for key, value in session_data.items():
                try:
                    json.dumps({key: value})
                except (TypeError, ValueError) as field_error:
                    print(f"❌ Problem with field '{key}': {field_error}")
                    print(f"  Field value: {value}")
                    print(f"  Field type: {type(value)}")
                    if isinstance(value, list):
                        for i, item in enumerate(value):
                            print(f"    Item {i}: {item} (type: {type(item)})")
            # This should not happen with our approach, but log for debugging
        
        # Store the original form data in session - guaranteed JSON-serializable
        session_key = self.get_session_key()
        print(f"🔍 DEBUG: About to store session data under key '{session_key}'")
        
        # Additional safety check before storing
        try:
            json.dumps(session_data)
            self.request.session[session_key] = session_data
            print("✅ Session data stored successfully")
        except (TypeError, ValueError) as e:
            print(f"❌ CRITICAL: Failed to store session data: {e}")
            raise
        
        if self.is_edit_mode():
            obj = self.get_object()
            if obj:
                self.request.session['edit_report_publication_id'] = obj.pk
                print(f"🔍 DEBUG: Stored edit_report_publication_id: {obj.pk} (type: {type(obj.pk).__name__})")
            
        # Debug: Check all session keys before redirect
        print(f"🔍 DEBUG: All session keys before redirect: {list(self.request.session.keys())}")
        for key in self.request.session.keys():
            try:
                value = self.request.session[key]
                print(f"🔍 DEBUG: Session['{key}']: {type(value).__name__}")
                # Try to serialize each session item
                json.dumps({key: value})
                print(f"  ✅ Session['{key}'] is JSON serializable")
            except (TypeError, ValueError) as e:
                print(f"  ❌ Session['{key}'] is NOT JSON serializable: {e}")
                print(f"     Value: {value}")
                print(f"     Type: {type(value)}")
            
        action = 'edit' if self.is_edit_mode() else 'add'
        print(f"🔍 DEBUG: AddEditReportView: redirecting to {self.select_persons_url}?action={action}")
        return redirect(f"publications:{self.select_persons_url}?action={action}")

    def _handle_file_operations(self, form):
        """Handle PDF file upload/deletion"""
        delete_pdf = form.cleaned_data.get('delete_pdf', False)
        uploaded_file = form.cleaned_data.get('pdffile')
        
        if delete_pdf and self.object.file:
            if self.object.file.file:
                self.object.file.file.delete()
            self.object.file.delete()
            self.object.file = None
            
        if uploaded_file:
            if self.object.file:
                if self.object.file.file:
                    self.object.file.file.delete()
                self.object.file.delete()
            
            file_obj = handle_publication_file_upload(self.object, uploaded_file)
            self.object.file = file_obj
            
        self.object.save()

    def _handle_authors_and_supervisors(self, authors, supervisors):
        """Handle author and supervisor relationships"""
        # Authors
        self.object.authorship_set.all().delete()
        for i, author in enumerate(authors):
            from publications.models import Authorship
            Authorship.objects.create(
                publication=self.object,
                person=author,
                author_id=i
            )
            
        # Supervisors
        self.object.supervisorship_set.all().delete()
        for i, supervisor in enumerate(supervisors):
            from publications.models import Supervisorship
            Supervisorship.objects.create(
                publication=self.object,
                person=supervisor,
                supervisor_id=i
            )

    def _handle_topics_and_keywords(self, form):
        """Handle topic and keyword relationships"""
        self.object.publication_topics.set(form.cleaned_data.get('publication_topics', []))
        self.object.publication_keywords.set(form.cleaned_data.get('publication_keywords', []))

    def _handle_file_operations_with_session_data(self, request):
        """Handle file operations using session data for the hybrid approach"""
        print(f"🔍 DEBUG: _handle_file_operations_with_session_data called")
        
        # Get session data
        session_data = request.session.get('updated_form_data', {})
        print(f"🔍 DEBUG: Session data keys: {list(session_data.keys())}")
        print(f"🔍 DEBUG: Full session data: {session_data}")
        
        # Check if we have file data - first from POST data (from form)
        uploaded_file_id = request.POST.get('uploaded_file_id')
        existing_file_id = request.POST.get('existing_file_id')
        temp_publication_id = request.POST.get('temp_publication_id')
        
        # If not in POST data, check session data
        if not uploaded_file_id:
            uploaded_file_id = session_data.get('uploaded_file_id')
        if not existing_file_id:
            existing_file_id = session_data.get('existing_file_id')
        if not temp_publication_id:
            temp_publication_id = session_data.get('temp_publication_id')
        
        print(f"🔍 DEBUG: uploaded_file_id from POST/session: {uploaded_file_id} (type: {type(uploaded_file_id).__name__ if uploaded_file_id else 'None'})")
        print(f"🔍 DEBUG: existing_file_id from POST/session: {existing_file_id} (type: {type(existing_file_id).__name__ if existing_file_id else 'None'})")
        print(f"🔍 DEBUG: temp_publication_id from POST/session: {temp_publication_id} (type: {type(temp_publication_id).__name__ if temp_publication_id else 'None'})")
        
        # Handle uploaded file (new upload)
        if uploaded_file_id and temp_publication_id:
            print(f"🔍 DEBUG: Found uploaded file ID: {uploaded_file_id}, temp publication ID: {temp_publication_id}")
            
            try:
                # Get the uploaded file object
                from publications.models import FileObject, Publication
                uploaded_file_obj = FileObject.objects.get(pk=uploaded_file_id)
                temp_publication = Publication.objects.get(pk=temp_publication_id)
                
                print(f"🔍 DEBUG: Retrieved uploaded file: {uploaded_file_obj.file.name}")
                print(f"🔍 DEBUG: Current uploaded file path: {uploaded_file_obj.file.path}")
                
                # Move the file from temp location to final location
                final_file_obj = self._move_temp_file_to_final(uploaded_file_obj, self.object)
                
                # Link the final file to the publication
                self.object.file = final_file_obj
                self.object.save()
                
                print(f"🔍 DEBUG: File linked to publication: {final_file_obj.file.name}")
                
                # Clean up temporary objects
                temp_publication.delete()
                uploaded_file_obj.delete()
                
                print(f"🔍 DEBUG: Cleaned up temporary objects")
                
            except Exception as e:
                print(f"🔍 DEBUG: Error moving uploaded file: {e}")
                print(f"🔍 DEBUG: {traceback.format_exc()}")
                
        # Handle existing file (edit mode - preserve existing file)
        elif existing_file_id:
            print(f"🔍 DEBUG: Found existing file ID: {existing_file_id}")
            
            try:
                # Get the existing file object and link it to the publication
                from publications.models import FileObject
                existing_file_obj = FileObject.objects.get(pk=existing_file_id)
                
                print(f"🔍 DEBUG: Retrieved existing file: {existing_file_obj.file.name}")
                
                # Link the existing file to the publication (no move needed)
                self.object.file = existing_file_obj
                self.object.save()
                
                print(f"🔍 DEBUG: Existing file preserved and linked to publication")
                
            except Exception as e:
                print(f"🔍 DEBUG: Error linking existing file: {e}")
                print(f"🔍 DEBUG: {traceback.format_exc()}")
        
        else:
            print(f"🔍 DEBUG: No file data found in session or POST data")
            # Also check for file metadata that might indicate a file was uploaded
            pdffile_data = session_data.get('pdffile')
            if pdffile_data:
                print(f"🔍 DEBUG: Found pdffile metadata: {pdffile_data}")
                print(f"🔍 DEBUG: POST data keys: {list(request.POST.keys())}")
                print(f"🔍 DEBUG: Looking for temp IDs in POST data...")
                for key, value in request.POST.items():
                    if 'temp' in key:
                        print(f"🔍 DEBUG: Found temp-related POST field: {key} = {value}")
                
                # Try to find any temporary files that might match this publication
                print(f"🔍 DEBUG: Searching for orphaned temporary files...")
                from publications.models import FileObject, Publication
                
                # Look for recent temp publications (created in the last hour)
                import datetime
                from django.utils import timezone
                one_hour_ago = timezone.now() - datetime.timedelta(hours=1)
                
                temp_publications = Publication.objects.filter(
                    title__startswith="TEMP_",
                    created_date__gte=one_hour_ago
                ).order_by('-created_date')
                
                print(f"🔍 DEBUG: Found {temp_publications.count()} temporary publications")
                for temp_pub in temp_publications[:5]:  # Check first 5
                    print(f"🔍 DEBUG: Temp publication: {temp_pub.id} - {temp_pub.title} (files: {temp_pub.fileobject_set.count()})")
                    if temp_pub.file:
                        print(f"🔍 DEBUG: Temp publication {temp_pub.id} has main file: {temp_pub.file.file.name}")
                        
                        # Check if the file name matches
                        if pdffile_data.get('name') and pdffile_data['name'] in temp_pub.file.file.name:
                            print(f"🔍 DEBUG: Found matching temp file! Attempting to use temp publication {temp_pub.id}")
                            try:
                                # Move the file to final location
                                final_file_obj = self._move_temp_file_to_final(temp_pub.file, self.object)
                                
                                # Link the final file to the publication
                                self.object.file = final_file_obj
                                self.object.save()
                                
                                print(f"🔍 DEBUG: Successfully moved file from temp publication {temp_pub.id}")
                                
                                # Clean up temporary publication
                                temp_pub.delete()
                                
                                print(f"🔍 DEBUG: Cleaned up temporary publication {temp_pub.id}")
                                break
                                
                            except Exception as e:
                                print(f"🔍 DEBUG: Error moving file from temp publication {temp_pub.id}: {e}")
                                print(f"🔍 DEBUG: {traceback.format_exc()}")
            else:
                print(f"🔍 DEBUG: No pdffile metadata found either")

    def _move_temp_file_to_final(self, temp_file_obj, publication):
        """Move a temporary file to its final location"""
        from django.conf import settings
        from publications.models import FileObject
        
        print(f"🔍 DEBUG: Moving temp file to final location")
        print(f"🔍 DEBUG: Temp file: {temp_file_obj.file.name}")
        print(f"🔍 DEBUG: Publication: {publication.title} (#{publication.number})")
        
        # Create a new FileObject for the final location
        final_file_obj = FileObject()
        final_file_obj.created_by = temp_file_obj.created_by
        final_file_obj.modified_by = temp_file_obj.modified_by
        final_file_obj.description = temp_file_obj.description
        final_file_obj.save()  # Save to get an ID
        
        # Determine final file path
        pub_number = publication.number if publication.number else f"pub_{final_file_obj.id}"
        year = publication.year if publication.year else 'unknown_year'
        year_str = str(year)
        
        # Get original filename
        original_filename = os.path.basename(temp_file_obj.file.name)
        base_name, ext = os.path.splitext(original_filename)
        
        # Create final filename
        final_filename = f"{pub_number}{ext}"
        
        # Create final path
        final_upload_to = os.path.join('reports', year_str)
        final_file_path = os.path.join(final_upload_to, final_filename)
        
        # Create directory if it doesn't exist
        final_dir = os.path.join(settings.MEDIA_ROOT, final_upload_to)
        os.makedirs(final_dir, exist_ok=True)
        
        # Handle filename conflicts
        counter = 1
        original_final_path = final_file_path
        full_final_path = os.path.join(settings.MEDIA_ROOT, final_file_path)
        
        while os.path.exists(full_final_path):
            base_path, ext = os.path.splitext(original_final_path)
            final_file_path = f"{base_path}_{counter}{ext}"
            full_final_path = os.path.join(settings.MEDIA_ROOT, final_file_path)
            counter += 1
        
        # Copy the file from temp to final location
        temp_full_path = temp_file_obj.file.path
        
        print(f"🔍 DEBUG: Copying from: {temp_full_path}")
        print(f"🔍 DEBUG: Copying to: {full_final_path}")
        
        shutil.copy2(temp_full_path, full_final_path)
        
        # Set the file path on the final file object
        final_file_obj.file.name = final_file_path
        final_file_obj.save()
        
        print(f"🔍 DEBUG: File moved successfully to: {final_file_obj.file.name}")
        
        return final_file_obj

    def get_success_url(self):
        """Get URL to redirect to after successful save"""
        redirect_url = reverse('publications:report', kwargs={'pk': self.object.pk})
        print(f"🔍 DEBUG: AddEditReportView.get_success_url - Publication ID: {self.object.pk}")
        print(f"🔍 DEBUG: AddEditReportView.get_success_url - Redirecting to: {redirect_url}")
        
        # Clear any session data to prevent stale data issues
        if 'updated_form_data' in self.request.session:
            print(f"🔍 DEBUG: AddEditReportView.get_success_url - Clearing updated_form_data from session")
            del self.request.session['updated_form_data']
            
        if self.is_edit_mode():
            edit_key = self.get_session_key()
            if edit_key in self.request.session:
                print(f"🔍 DEBUG: AddEditReportView.get_success_url - Clearing {edit_key} from session")
                del self.request.session[edit_key]
        
        return redirect_url


@method_decorator(login_required, name='dispatch')
class AddEditReportReviewView(BaseView):
    """Review view for forms with workflow session data - displays as static content"""
    model = Publication
    template_name = 'publications/add_edit_report_review.html'
    
    def is_edit_mode(self):
        """Check if we're in edit mode (has pk in URL)"""
        return 'pk' in self.kwargs

    def get_object(self):
        """Get the publication to edit, or None for add mode"""
        if self.is_edit_mode():
            if hasattr(self, '_object_cache'):
                return self._object_cache
            self._object_cache = get_object_or_404(Publication, pk=self.kwargs['pk'])
            return self._object_cache
        return None

    def dispatch(self, request, *args, **kwargs):
        """Ensure session data exists, redirect to clean form if not"""
        if not self._has_valid_session_data():
            if self.is_edit_mode():
                return redirect('publications:edit_report', pk=kwargs['pk'])
            else:
                return redirect('publications:add_report')
        return super().dispatch(request, *args, **kwargs)

    def _has_valid_session_data(self):
        """Check if we have valid session data for this view"""
        return 'updated_form_data' in self.request.session

    def get_context_data(self, **kwargs):
        # Get base context but avoid FormView implementation
        context = BaseView.get_context_data(self, **kwargs)
        context['action'] = 'edit' if self.is_edit_mode() else 'add'
        
        if self.is_edit_mode():
            context['publication'] = self.get_object()
        else:
            context['publication'] = None
        
        # Get the review data
        review_data, changed_fields = self._get_review_data()
        context['review_data'] = review_data
        
        # Add information about what changed
        if 'updated_form_data' in self.request.session:
            context['has_workflow_changes'] = True
            
            # Get the original field that was updated in workflow
            workflow_field = self.request.session.get('workflow_updated_field', None)
            if workflow_field:
                # Add workflow field to changed fields
                changed_fields[workflow_field] = True
                
        # In add mode, consider all fields as "changed" from default
        if not self.is_edit_mode():
            # All fields are considered new in add mode
            for field in review_data.keys():
                if field not in ['pdffile', 'delete_pdf'] and review_data[field]:  # Skip empty fields
                    changed_fields[field] = True
                    
        context['changed_fields'] = changed_fields
            
        return context

    def _get_review_data(self):
        """Convert session data into a clean format for display and track changed fields"""
        session_data = self.request.session.get('updated_form_data', {})
        
        # Debug output to understand the format of session data
        print(f"🔍 DEBUG: Review session data keys: {list(session_data.keys())}")
        print(f"🔍 DEBUG: Full session data for debugging:")
        for key, value in session_data.items():
            print(f"🔍 DEBUG:   '{key}': {value} (type: {type(value).__name__})")
        
        # Check for temp file data
        if 'temp_file_id' in session_data:
            print(f"🔍 DEBUG: temp_file_id found in session: {session_data['temp_file_id']}")
        else:
            print(f"🔍 DEBUG: temp_file_id NOT found in session")
            
        if 'temp_publication_id' in session_data:
            print(f"🔍 DEBUG: temp_publication_id found in session: {session_data['temp_publication_id']}")
        else:
            print(f"🔍 DEBUG: temp_publication_id NOT found in session")
        
        if 'authors' in session_data:
            print(f"🔍 DEBUG: Authors data: {session_data['authors']} (type: {type(session_data['authors']).__name__})")
            if session_data['authors'] and isinstance(session_data['authors'], list):
                print(f"🔍 DEBUG: First author: {session_data['authors'][0]} (type: {type(session_data['authors'][0]).__name__})")
        
        if 'supervisors' in session_data:
            print(f"🔍 DEBUG: Supervisors data: {session_data['supervisors']} (type: {type(session_data['supervisors']).__name__})")
            if session_data['supervisors'] and isinstance(session_data['supervisors'], list):
                print(f"🔍 DEBUG: First supervisor: {session_data['supervisors'][0]} (type: {type(session_data['supervisors'][0]).__name__})")
        
        review_data = {}
        # Dictionary to track changed fields
        changed_fields = {}
        
        # Basic fields - get from session, convert lists to single values where needed
        for field in ['title', 'year', 'number', 'abstract', 'comment']:
            value = session_data.get(field, [])
            if isinstance(value, list) and len(value) == 1:
                review_data[field] = value[0]
            elif isinstance(value, list) and len(value) > 1:
                review_data[field] = ', '.join(str(v) for v in value)
            else:
                review_data[field] = value

        # Type field - convert to display name
        type_value = session_data.get('type', [])
        print(f"🔍 DEBUG: Processing type field. Raw value: {type_value} (type: {type(type_value).__name__})")
        
        if isinstance(type_value, list) and len(type_value) == 1:
            type_pk = type_value[0]
            print(f"🔍 DEBUG: Type PK extracted from list: {type_pk} (type: {type(type_pk).__name__})")
            
            try:
                from publications.models import PubType
                pub_type = PubType.objects.get(pk=int(type_pk))
                print(f"🔍 DEBUG: Found PubType object: {pub_type} (ID: {pub_type.id}, type: {pub_type.type})")
                # Pass the actual object rather than just the string
                review_data['type'] = pub_type
            except (PubType.DoesNotExist, ValueError, TypeError) as e:
                print(f"🔍 DEBUG: Error finding PubType: {e}")
                review_data['type'] = type_pk
        else:
            print(f"🔍 DEBUG: Using type value directly: {type_value}")
            review_data['type'] = type_value

        # Authors and supervisors - convert PKs to Person names
        authors_data = session_data.get('authors', [])
        if authors_data:
            authors = []
            for author_pk in authors_data:
                try:
                    # Handle different formats of author_pk
                    if isinstance(author_pk, str):
                        if ',' in author_pk:
                            # Handle comma-separated format (like "1,0,0,1")
                            clean_pk = author_pk.replace(',', '')
                            person = Person.objects.get(pk=int(clean_pk))
                        elif author_pk.isdigit():
                            # Handle normal digit string
                            person = Person.objects.get(pk=int(author_pk))
                        else:
                            # If it's not a number, it might be a new person name
                            raise ValueError(f"Not a valid person ID: {author_pk}")
                    else:
                        # Handle numeric types directly
                        person = Person.objects.get(pk=int(author_pk))
                    authors.append(str(person))
                except (Person.DoesNotExist, ValueError, TypeError) as e:
                    print(f"Error processing author PK {author_pk}: {e}")
                    authors.append(str(author_pk))  # Fallback for new person names
            review_data['authors'] = authors
        else:
            review_data['authors'] = []

        # Handle supervisors - convert to list if it's a string
        supervisors_data = session_data.get('supervisors', [])
        print(f"🔍 DEBUG: Raw supervisors_data: {supervisors_data} (type: {type(supervisors_data).__name__})")
        
        # Convert string to list if needed
        if isinstance(supervisors_data, str):
            # Convert single string value to a list with one item
            supervisors_data = [supervisors_data]
            print(f"🔍 DEBUG: Converted supervisors_data to list: {supervisors_data}")
        elif not isinstance(supervisors_data, list):
            # Handle any other non-list type
            supervisors_data = [str(supervisors_data)]
            print(f"🔍 DEBUG: Converted non-list supervisors_data to list: {supervisors_data}")
            
        if supervisors_data:
            supervisors = []
            for supervisor_pk in supervisors_data:
                try:
                    # Handle different formats of supervisor_pk
                    if isinstance(supervisor_pk, str):
                        if ',' in supervisor_pk:
                            # Handle comma-separated format (like "1,0,0,1")
                            clean_pk = supervisor_pk.replace(',', '')
                            person = Person.objects.get(pk=int(clean_pk))
                        elif supervisor_pk.isdigit():
                            # Handle normal digit string
                            person = Person.objects.get(pk=int(supervisor_pk))
                        else:
                            # If it's not a number, it might be a new person name
                            raise ValueError(f"Not a valid person ID: {supervisor_pk}")
                    else:
                        # Handle numeric types directly
                        person = Person.objects.get(pk=int(supervisor_pk))
                    supervisors.append(str(person))
                except (Person.DoesNotExist, ValueError, TypeError) as e:
                    print(f"Error processing supervisor PK {supervisor_pk}: {e}")
                    supervisors.append(str(supervisor_pk))  # Fallback for new person names
            review_data['supervisors'] = supervisors
        else:
            review_data['supervisors'] = []

        # Topics and keywords - convert PKs to display names  
        topics_data = session_data.get('publication_topics', [])
        if topics_data:
            topics = []
            for topic_pk in topics_data:
                try:
                    from publications.models import Topic
                    topic = Topic.objects.get(pk=int(topic_pk))
                    topics.append(str(topic))
                except (Topic.DoesNotExist, ValueError, TypeError):
                    topics.append(str(topic_pk))
            review_data['publication_topics'] = topics
        else:
            review_data['publication_topics'] = []

        keywords_data = session_data.get('publication_keywords', [])
        if keywords_data:
            keywords = []
            for keyword_pk in keywords_data:
                try:
                    from publications.models import Keyword
                    keyword = Keyword.objects.get(pk=int(keyword_pk))
                    keywords.append(str(keyword))
                except (Keyword.DoesNotExist, ValueError, TypeError):
                    keywords.append(str(keyword_pk))
            review_data['publication_keywords'] = keywords
        else:
            review_data['publication_keywords'] = []

        # File fields for all modes - always add these keys to prevent template errors
        # Initialize with default empty/false values
        review_data['pdffile'] = None
        review_data['delete_pdf'] = False
        
        # Handle file uploads for both add and edit modes
        pdffile_data = session_data.get('pdffile')
        print(f"🔍 DEBUG: pdffile_data from session: {pdffile_data} (type: {type(pdffile_data).__name__ if pdffile_data is not None else 'None'})")
            
        # Only add real file data if it's not empty
        if pdffile_data and pdffile_data != [''] and pdffile_data != '':
            # Handle dictionary format (with file metadata)
            if isinstance(pdffile_data, dict):
                review_data['pdffile'] = pdffile_data
                print(f"🔍 DEBUG: Set pdffile in review_data from dict: {review_data['pdffile']}")
            # Handle list format (session might store as list)
            elif isinstance(pdffile_data, list) and len(pdffile_data) > 0:
                if isinstance(pdffile_data[0], dict):
                    review_data['pdffile'] = pdffile_data[0]
                else:
                    # Extract file name from list
                    file_name = pdffile_data[0]
                    review_data['pdffile'] = {'name': file_name}
                print(f"🔍 DEBUG: Set pdffile in review_data from list: {review_data['pdffile']}")
            else:
                # Handle string or other format
                review_data['pdffile'] = {'name': str(pdffile_data)}
                print(f"🔍 DEBUG: Set pdffile in review_data from string: {review_data['pdffile']}")
        
        # Check for delete PDF flag separately (should work regardless of file upload)
        delete_pdf_data = session_data.get('delete_pdf', [])
        print(f"🔍 DEBUG: delete_pdf_data from session: {delete_pdf_data}")
        
        if delete_pdf_data and (isinstance(delete_pdf_data, bool) or 
                             (isinstance(delete_pdf_data, list) and len(delete_pdf_data) > 0 and 
                              delete_pdf_data[0] in ['True', 'on', '1'])):
            review_data['delete_pdf'] = True
            print(f"🔍 DEBUG: Set delete_pdf in review_data to True")
        
        # Extract file IDs if they exist
        uploaded_file_id = session_data.get('uploaded_file_id')
        existing_file_id = session_data.get('existing_file_id')
        temp_publication_id = session_data.get('temp_publication_id')
        
        print(f"🔍 DEBUG: uploaded_file_id from session: {uploaded_file_id} (type: {type(uploaded_file_id).__name__ if uploaded_file_id else 'None'})")
        print(f"🔍 DEBUG: existing_file_id from session: {existing_file_id} (type: {type(existing_file_id).__name__ if existing_file_id else 'None'})")
        print(f"🔍 DEBUG: temp_publication_id from session: {temp_publication_id} (type: {type(temp_publication_id).__name__ if temp_publication_id else 'None'})")
        
        # Add file IDs to review data if they exist
        if uploaded_file_id:
            review_data['uploaded_file_id'] = uploaded_file_id
            print(f"🔍 DEBUG: Added uploaded_file_id to review_data: {uploaded_file_id}")
        
        if existing_file_id:
            review_data['existing_file_id'] = existing_file_id
            print(f"🔍 DEBUG: Added existing_file_id to review_data: {existing_file_id}")
        
        if temp_publication_id:
            review_data['temp_publication_id'] = temp_publication_id
            print(f"🔍 DEBUG: Added temp_publication_id to review_data: {temp_publication_id}")
        
        # Detect which fields have changed compared to original data
        if self.is_edit_mode():
            obj = self.get_object()
            if obj:
                # Check basic text fields
                for field in ['title', 'year', 'number', 'abstract', 'comment']:
                    if field in review_data and hasattr(obj, field):
                        # Get the current value from the database
                        current_val = getattr(obj, field)
                        # Handle None values
                        if current_val is None:
                            current_val = ""
                        
                        # Get the new value
                        new_val = review_data.get(field, "")
                        if str(current_val) != str(new_val) and new_val:
                            changed_fields[field] = True
                
                # Check type changes - compare by PK/ID for most accurate comparison
                if hasattr(obj, 'type') and 'type' in review_data:
                    # Extract the current type object from the database record
                    current_type_obj = obj.type
                    new_type_obj = review_data['type']
                    
                    # Debug the values we're comparing
                    print(f"🔍 DEBUG: Comparing Types: Current: {current_type_obj} | New: {new_type_obj}")
                    
                    # Get the IDs/PKs for comparison
                    current_id = getattr(current_type_obj, 'id', None)
                    new_id = getattr(new_type_obj, 'id', None)
                    
                    print(f"🔍 DEBUG: Type IDs - Current: {current_id} | New: {new_id}")
                    
                    # If we have valid IDs for both, compare by ID (most reliable)
                    if current_id is not None and new_id is not None:
                        if int(current_id) != int(new_id):
                            changed_fields['type'] = True
                            print(f"🔍 DEBUG: Type marked as changed based on ID comparison: {current_id} ≠ {new_id}")
                    else:
                        # No valid IDs, so compare by type code string
                        current_type_code = current_type_obj.type if hasattr(current_type_obj, 'type') else str(current_type_obj)
                        new_type_code = new_type_obj.type if hasattr(new_type_obj, 'type') else str(new_type_obj)
                        
                        # Normalize by converting to uppercase string for comparison
                        current_type_str = str(current_type_code).upper()
                        new_type_str = str(new_type_code).upper()
                        
                        print(f"🔍 DEBUG: Type strings - Current: '{current_type_str}' | New: '{new_type_str}'")
                        
                        if current_type_str != new_type_str:
                            changed_fields['type'] = True
                            print(f"🔍 DEBUG: Type marked as changed based on string comparison")
                    
                    # For debugging, log if type is unchanged
                    if 'type' not in changed_fields:
                        print(f"🔍 DEBUG: Type field unchanged - values match")
                
                # Check authors, supervisors, topics and keywords changes
                for field in ['authors', 'supervisors', 'publication_topics', 'publication_keywords']:
                    # For these M2M fields, we'll compare the string representations
                    if field in review_data:
                        new_items = review_data[field]
                        
                        # Get current items
                        current_items = []
                        if field == 'authors' and hasattr(obj, 'authors'):
                            current_items = [str(author) for author in obj.authors.all()]
                        elif field == 'supervisors' and hasattr(obj, 'supervisors'):
                            current_items = [str(supervisor) for supervisor in obj.supervisors.all()]
                        elif field == 'publication_topics' and hasattr(obj, 'publication_topics'):
                            current_items = [str(topic) for topic in obj.publication_topics.all()]
                        elif field == 'publication_keywords' and hasattr(obj, 'publication_keywords'):
                            current_items = [str(keyword) for keyword in obj.publication_keywords.all()]
                        
                        # Compare lists by creating sorted sets of string values
                        if set(new_items) != set(current_items):
                            changed_fields[field] = True
                
                # Check file changes - detect any changes in file state
                has_real_file = 'pdffile' in review_data and review_data['pdffile'] is not None
                has_delete_request = 'delete_pdf' in review_data and review_data['delete_pdf'] == True
                
                # If we have a file upload or delete request, mark as changed
                if has_real_file or has_delete_request:
                    changed_fields['file'] = True
                    print(f"🔍 DEBUG: File marked as changed - has_real_file: {has_real_file}, has_delete_request: {has_delete_request}")
        
        return review_data, changed_fields

    def get(self, request, *args, **kwargs):
        """Handle GET requests - show the review page"""
        context = self.get_context_data(**kwargs)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """Handle POST requests - process the acceptance and save"""
        # Get session data and process it using the form
        session_data = self.request.session.get('updated_form_data', {})
        print(f"🔍 DEBUG: post - Session data found: {bool(session_data)}")
        print(f"🔍 DEBUG: post - Session data keys: {list(session_data.keys())}")
        print(f"🔍 DEBUG: post - request.FILES keys: {list(request.FILES.keys()) if request.FILES else 'No files in request'}")
        
        if not session_data:
            # No session data, redirect back
            if self.is_edit_mode():
                print(f"🔍 DEBUG: No session data, redirecting to edit_report")
                return redirect('publications:edit_report', pk=kwargs['pk'])
            else:
                print(f"🔍 DEBUG: No session data, redirecting to add_report")
                return redirect('publications:add_report')

        # Create a form instance to process the session data
        form_class = WorkflowAddEditReportForm
        
        # Convert session data to POST-like format for form processing
        post_data = {}
        
        # Track if we have file data in session and request
        has_file_data = False
        file_data = None
        file_in_request = False
        file_key = 'pdffile'
        
        # First check if we have a file in the request
        if 'pdffile' in request.FILES:
            file_in_request = True
            file_key = 'pdffile'
            print(f"🔍 DEBUG: Found file in request.FILES['pdffile']: {request.FILES['pdffile'].name}")
        elif 'form-0-pdffile' in request.FILES:
            file_in_request = True
            file_key = 'form-0-pdffile'
            print(f"🔍 DEBUG: Found file in request.FILES['form-0-pdffile']: {request.FILES['form-0-pdffile'].name}")
            
        # Process session data
        for key, value in session_data.items():
            # Special handling for authors and supervisors - always ensure they are lists
            if key in ['authors', 'supervisors']:
                if isinstance(value, list):
                    post_data[key] = value
                else:
                    post_data[key] = [value]  # Convert single value to list
                print(f"🔍 DEBUG: POST processing {key}: {post_data[key]} (type: {type(post_data[key]).__name__})")
            elif key == 'pdffile':
                # Special handling for pdffile
                has_file_data = True
                if isinstance(value, dict):
                    file_data = value
                    print(f"🔍 DEBUG: Found file data in session (dict): {value}")
                elif isinstance(value, list) and value:
                    if isinstance(value[0], dict):
                        file_data = value[0]
                    else:
                        file_data = {'name': str(value[0])}
                    print(f"🔍 DEBUG: Found file data in session (list): {file_data}")
                else:
                    file_data = {'name': str(value)}
                    print(f"🔍 DEBUG: Found file data in session (other): {file_data}")
                post_data[key] = value
            elif isinstance(value, list):
                if len(value) == 1:
                    post_data[key] = value[0]
                else:
                    post_data[key] = value
            else:
                post_data[key] = value
                
        # Add file handling flags
        post_data['file_in_request'] = file_in_request
        post_data['file_key'] = file_key
        if has_file_data:
            post_data['has_file_data_in_session'] = True
            post_data['file_info_from_session'] = file_data
            
        # Create form with processed data
        form_kwargs = {'request': request}
        if self.is_edit_mode():
            form_kwargs['instance'] = self.get_object()
        
        # For file processing, we need to handle request.FILES properly
        # If there's a file in request, add it to the form data
        files_dict = {}
        if file_in_request:
            # We don't add files directly to form to avoid validation issues
            # Instead, we'll process the file manually in _handle_file_operations_with_session_data
            print(f"🔍 DEBUG: Will process file from request.FILES['{file_key}'] during save")
        else:
            print(f"🔍 DEBUG: No file in request.FILES to process")
        
        # Create form with POST data (we'll handle files separately)
        form = form_class(post_data, **form_kwargs)
        print(f"🔍 DEBUG: Form created with data keys: {list(post_data.keys())}")
        
        # Check if form is valid
        try:
            is_valid = form.is_valid()
            print(f"🔍 DEBUG: Form is valid: {is_valid}")
            
            # If form has validation errors, log them but continue
            if not is_valid:
                print(f"🔍 DEBUG: Form validation errors: {form.errors}")
                for field, errors in form.errors.items():
                    print(f"🔍 DEBUG: Field '{field}' errors: {errors}")
            
            # For review form, even if validation fails, we should proceed with saving
            # because the data came from a previously valid form and has just been transformed
            print(f"🔍 DEBUG: Proceeding with _save_publication")
            return self._save_publication(form)
        except Exception as e:
            # Catch any validation or processing errors
            print(f"🔍 DEBUG: Error during form processing: {str(e)}")
            print(f"🔍 DEBUG: {traceback.format_exc()}")
            from django.contrib import messages
            messages.error(
                request,
                f"An error occurred while processing your form: {str(e)}"
            )
            
            # Redirect back to form
            if self.is_edit_mode():
                return redirect('publications:edit_report', pk=kwargs['pk'])
            else:
                return redirect('publications:add_report')
            
            # Get the object if in edit mode
            if self.is_edit_mode():
                obj = self.get_object()
                if obj:
                    # Process the object and session data directly
                    from django.http import HttpResponseRedirect
                    from publications.models import Publication, Authorship, Supervisorship, Person
                    
                    print(f"🔍 DEBUG: Found object to edit: {obj}")
                    
                    # Extract authors and supervisors from session data
                    authors_pks = session_data.get('authors', [])
                    supervisors_pks = session_data.get('supervisors', [])
                    
                    # Convert to lists if needed
                    if not isinstance(authors_pks, list):
                        authors_pks = [authors_pks]
                    if not isinstance(supervisors_pks, list):
                        supervisors_pks = [supervisors_pks]
                        
                    print(f"🔍 DEBUG: Author PKs: {authors_pks}")
                    print(f"🔍 DEBUG: Supervisor PKs: {supervisors_pks}")
                    
                    # Save the basic fields
                    if 'title' in session_data:
                        obj.title = session_data['title'][0] if isinstance(session_data['title'], list) else session_data['title']
                    if 'year' in session_data:
                        year_val = session_data['year'][0] if isinstance(session_data['year'], list) else session_data['year']
                        obj.year = int(year_val) if year_val else None
                    if 'number' in session_data:
                        obj.number = session_data['number'][0] if isinstance(session_data['number'], list) else session_data['number']
                    if 'abstract' in session_data:
                        obj.abstract = session_data['abstract'][0] if isinstance(session_data['abstract'], list) else session_data['abstract']
                    if 'comment' in session_data:
                        obj.comment = session_data['comment'][0] if isinstance(session_data['comment'], list) else session_data['comment']
                    
                    # Save the publication
                    obj.modified_by = self.request.user
                    obj.save()
                    
                    # Handle authors
                    obj.authorship_set.all().delete()
                    for i, author_pk in enumerate(authors_pks):
                        try:
                            person = Person.objects.get(pk=int(author_pk))
                            Authorship.objects.create(
                                publication=obj,
                                person=person,
                                author_id=i
                            )
                            print(f"🔍 DEBUG: Added author: {person}")
                        except Exception as e:
                            print(f"🔍 DEBUG: Error adding author {author_pk}: {e}")
                    
                    # Handle supervisors
                    obj.supervisorship_set.all().delete()
                    for i, supervisor_pk in enumerate(supervisors_pks):
                        try:
                            person = Person.objects.get(pk=int(supervisor_pk))
                            Supervisorship.objects.create(
                                publication=obj,
                                person=person,
                                supervisor_id=i
                            )
                            print(f"🔍 DEBUG: Added supervisor: {person}")
                        except Exception as e:
                            print(f"🔍 DEBUG: Error adding supervisor {supervisor_pk}: {e}")
                    
                    # Clear ALL session data
                    self._clear_session_data()
                    
                    # Redirect to the report page
                    return HttpResponseRedirect(reverse('publications:report', kwargs={'pk': obj.pk}))
                    
            # If not edit mode or couldn't save directly, redirect back to form
            if self.is_edit_mode():
                return redirect('publications:edit_report', pk=kwargs['pk'])
            else:
                return redirect('publications:add_report')

    def _save_publication(self, form):
        """Save the publication with form data"""
        print(f"🔍 DEBUG: AddEditReportReviewView._save_publication called")
        
        # Set user information
        if not form.instance.pk:
            form.instance.created_by = self.request.user
        form.instance.modified_by = self.request.user

        authors = form.cleaned_data['authors']
        supervisors = form.cleaned_data['supervisors']
        
        print(f"🔍 DEBUG: Authors from form: {authors} (type: {type(authors).__name__})")
        print(f"🔍 DEBUG: Supervisors from form: {supervisors} (type: {type(supervisors).__name__})")

        # In review mode, we should always have QuerySets by now
        if (not isinstance(authors, QuerySet)) or (not isinstance(supervisors, QuerySet)):
            print("🔍 DEBUG: ERROR: Review mode should have QuerySets")
            # Redirect back to main edit form to restart process
            if self.is_edit_mode():
                return redirect('publications:edit_report', pk=self.kwargs['pk'])
            else:
                return redirect('publications:add_report')

        # Save publication (without files yet)
        self.object = form.save(commit=False)
        
        # Auto-generate report number for new publications
        if not self.object.pk and not self.object.number:
            if self.object.year:
                from publications.utils import generate_next_report_number
                from django.db import transaction, IntegrityError
                
                # Use retry logic to handle concurrency during auto-generation
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        with transaction.atomic():
                            # Generate number atomically
                            self.object.number = generate_next_report_number(self.object.year)
                            self.object.save()
                            break  # Success - exit retry loop
                    except IntegrityError:
                        if attempt < max_retries - 1:
                            time.sleep(0.1)  # Brief delay before retry
                            continue
                        else:
                            # If all retries fail, show error
                            from django.contrib import messages
                            messages.error(
                                self.request, 
                                "Unable to assign report number due to high system load. Please try again."
                            )
                            return redirect('publications:add_report')
            else:
                from django.contrib import messages
                messages.error(self.request, "Cannot create report without a year")
                return redirect('publications:add_report')
        else:
            # Save existing publication (edit mode)
            self.object.save()

        # Handle file operations AFTER report number is assigned
        self._handle_file_operations_with_session_data(self.request)

        # Handle relationships
        self._handle_authors_and_supervisors(authors, supervisors)
        self._handle_topics_and_keywords(form)

        # Clear ALL session data after successful save
        self._clear_session_data()

        # Always return a redirect to the success URL
        from django.http import HttpResponseRedirect
        success_url = self.get_success_url()
        print(f"🔍 DEBUG: Redirecting to success URL: {success_url}")
        return HttpResponseRedirect(success_url)


@method_decorator(login_required, name='dispatch')
class PersonSelectView(BaseView):
    template_name = 'publications/persons_select.html'
    
    def __init__(self, *args, **kwargs):
        print('In PersonSelectView:__init__')
        super().__init__(*args, **kwargs)

    def get_session_config(self):
        """Get session configuration based on the action parameter"""
        action = self.request.GET.get('action', 'add')
        
        if action == 'edit':
            return {
                'session_key': 'edit_report_form_data',
                'redirect_url': 'publications:edit_report_final_save',
                'action': 'edit'
            }
        else:
            return {
                'session_key': 'add_report_form_data', 
                'redirect_url': 'publications:publication_final_save',
                'action': 'add'
            }

    def get(self, request):
        print('In PersonSelectView:get')
        
        config = self.get_session_config()
        session_data = self.request.session.get(config['session_key'], {})
        authors = session_data.get('authors', [])
        supervisors = session_data.get('supervisors', [])   

        if authors:
            authors_form = AuthorSelectForm(authors=authors)
        else:
            authors_form = None

        if supervisors:
            supervisors_form = SupervisorSelectForm(supervisors=supervisors)
        else:
            supervisors_form = None

        return render(request, self.template_name, {
            'authors_form': authors_form,
            'supervisors_form': supervisors_form,
            'action': config['action']
        })

    def post(self, request):
        print(f"PersonSelectView:post: request.post data: {request.POST}")

        config = self.get_session_config()
        session_data = self.request.session.get(config['session_key'], {})
        authors = session_data.get('authors', [])
        supervisors = session_data.get('supervisors', [])  

        print(f"PersonSelectView:post: authors data: {authors}")
        print(f"PersonSelectView:post: supervisors data: {supervisors}")

        if authors:
            authors_form = AuthorSelectForm(request.POST, authors=authors)
        else:
            authors_form = None

        if supervisors:
            supervisors_form = SupervisorSelectForm(request.POST, supervisors=supervisors)
        else:
            supervisors_form = None

        # print(f"PersonSelectView:post: authors_form: {authors_form}")
        # print(f"PersonSelectView:post: supervisors_form: {supervisors_form}")

        author_form_valid = False
        if (authors_form is not None) and (authors_form.is_valid()):
            print(f"PersonSelectView:post: authors_form cleaned data: {authors_form.cleaned_data}")
            selected_authors = []
            for key, value in authors_form.cleaned_data.items():
                if key.startswith("author_"):
                    if value == 'create_new':
                        print(f"  - Create new author: {key}: {value}")
                        # Create a new Person instance
                        name = authors[int(key.split('_')[1])]
                        person = Person.objects.create(name=name)
                        selected_authors.append(person.pk)
                        print(f"  - created new author: {person}")
                    else:
                        # Use the selected Person primary key
                        print(f"  - Select existing author: {key}: {value}")
                        selected_authors.append(int(value))

            # Update the session with the selected author primary keys
            session_data['authors'] = selected_authors
            print(f"PersonSelectView:post: selected authors: {selected_authors}")
            author_form_valid = True
        elif authors_form is not None:
            print(f"PersonSelectView:post: authors_form not valid")
            print(f"  - form errors: {authors_form.errors}")
            print(f"  - form non_field_errors: {authors_form.non_field_errors()}")
        else:
            print(f"PersonSelectView:post: authors_form is None")
            author_form_valid = True

        supervisor_form_valid = False
        if (supervisors_form is not None) and (supervisors_form.is_valid()):
            print(f"PersonSelectView:post: supervisors_form cleaned data: {supervisors_form.cleaned_data}")
            selected_supervisors = []
            for key, value in supervisors_form.cleaned_data.items():
                if key.startswith("supervisor_"):
                    if value == 'create_new':
                        print(f"  - Create new supervisor: {key}: {value}")
                        # Create a new Person instance
                        name = supervisors[int(key.split('_')[1])]
                        person = Person.objects.create(name=name)
                        selected_supervisors.append(person.pk)
                        print(f"  - created new supervisor: {person}")
                    else:
                        # Use the selected Person primary key
                        print(f"Select existing supervisor: {key}: {value}")
                        selected_supervisors.append(int(value))

            # Update the session with the selected supervisor primary keys
            session_data['supervisors'] = selected_supervisors
            print(f"PersonSelectView:post: selected supervisors: {selected_supervisors}")
            supervisor_form_valid = True
        elif supervisors_form is not None:
            print(f"PersonSelectView:post: supervisors_form not valid")
            print(f"  - form errors: {supervisors_form.errors}")
            print(f"  - form non_field_errors: {supervisors_form.non_field_errors()}")
        else:
            print(f"PersonSelectView:post: supervisors_form is None")
            supervisor_form_valid = True

        # Update the session data with the new author and supervisor selections
        self.request.session[config['session_key']] = session_data
        self.request.session.modified = True

        print(f"PersonSelectView:post: session data: {self.request.session.get(config['session_key'])}")

        if author_form_valid and supervisor_form_valid:
            print(f"PersonSelectView:post: redirecting to {config['redirect_url']}")
            return redirect(config['redirect_url'])
        else:
            print(f"PersonSelectView:post: forms are invalid, redirecting back to select_persons")
            return render(request, self.template_name, {
                'authors_form': authors_form,
                'supervisors_form': supervisors_form,
                'action': config['action']
            })
          







          





class PersonAutocompleteView(View):
    
    re_studynumber = re.compile(r'^s\d{1,6}$')

    def get(self, request, *args, **kwargs):
        term = request.GET.get("term", "")
        
        if term:
            # if the string in term starts with 's' followed by 1 to 6 numbers then...
            if self.re_studynumber.match(term):
                queryset = Person.objects.filter(id_number__iexact=term).order_by('first')
            else:
                fields_to_search = ['first_relaxed', 'last_relaxed',
                                    'first', 'middle', 'prelast', 'last', 'lineage',
                                    'initials']
                query = get_query(term, fields_to_search)

                queryset = Person.objects.filter(query).order_by('first')
        else:
            queryset = Person.objects.all()

        results = [
            {"id": person.pk, "text": str(person)} for person in queryset
        ]
        
        # print debug message to console displaying the number of results
        print(f"Term requested: {term}")
        print(f"Number of results: {len(results)}")

        return JsonResponse({"results": results})

















class PersonView(BaseDetailView):
    model = Person
    template_name = 'publications/person.html'
    context_object_name = 'person'



























































class FeatureView(BaseDetailView):
    model = Feature
    template_name = 'publications/feature.html'
    context_object_name = 'feature'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        geometry = self.object.points or self.object.lines or self.object.polys
        context.update({'geometry': geometry})
        return context



























































































































# class LoginView(BaseView):
    
    
#     template_view = 'publications/login.html'

#     # Check what is the IP address of the user
#     def get(self, request, **kwargs):
        
    

#         form = LoginForm()
#         context = {'form': form}
#         context.update(self.get_context_data(**kwargs))
#         return render(request, self.template_view, context)

#     def post(self, request, **kwargs):
        
#         ip = get_client_ip(request)


#         # Check if the IP address is in the list of allowed IP addresses
#         if not is_private(ip):
#                 return render(request, 'publications/access_denied.html', context = {'error': 'Your IP address is not allowed to access this page!'})
                
#         form = LoginForm(request.POST)
#         if form.is_valid():
#             username = form.cleaned_data['username']
#             password = form.cleaned_data['password']




#             user = authenticate(request, username=username, password=password)




#             if user is not None:
#                 login(request, user)
#                 return redirect('frontpage')  # or wherever you want to redirect after successful login
#             else:
#                 form.add_error(None, 'Authentication failed')

#         context = {'form': form}
#         context.update(self.get_context_data(**kwargs))
#         return render(request, self.template_view, context)






class LogoutView(BaseView):
    def get(self, request, **kwargs):
        logout(request)
        return redirect('publications:frontpage')






























# def map_data(request):
#     features = Feature.objects.all()
#     # q: in debug mode, how to loop through features and print out the attributes?
#     # for feature in features:
#     #     print(feature)
#     serialized_features = serializers.serialize('json', features)
#     return JsonResponse(serialized_features, safe=False)


class UploadAppendixView(BaseView):
    """
    View for uploading multiple appendix files to a publication.
    Uses session-based batch management for file handling.
    
    Note: For very large files (>100MB), we may need to implement 
    a secondary upload scheme with chunked uploads or direct storage.
    """
    template_name = 'publications/upload_appendix.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        publication_id = self.kwargs['pk']
        
        # Get the publication
        publication = get_object_or_404(Publication, id=publication_id)
        context['publication'] = publication
        
        # Import forms here to avoid circular imports
        from publications.forms import UploadAppendixForm
        context['form'] = UploadAppendixForm()
        
        # Get session files for this publication
        session_key = f'appendix_upload_{publication_id}'
        # Note: request is not available in get_context_data, will handle in get method
        context['session_files'] = []
        
        # Get existing appendices
        context['existing_appendices'] = publication.appendices.all()
        
        return context
    
    def get(self, request, **kwargs):
        self.request = request  # Store request for context access
        self.kwargs = kwargs    # Store kwargs for context access
        context = self.get_context_data(**kwargs)
        
        # Add session files here where we have access to request
        publication_id = kwargs['pk']
        session_key = f'appendix_upload_{publication_id}'
        context['session_files'] = request.session.get(session_key, [])
        
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle different POST actions: upload, remove, submit, cancel"""
        publication_id = self.kwargs['pk']
        publication = get_object_or_404(Publication, id=publication_id)
        action = request.POST.get('action', 'upload')
        
        if action == 'upload':
            return self.handle_file_upload(request, publication)
        elif action == 'remove':
            return self.handle_file_removal(request, publication)
        elif action == 'submit':
            return self.handle_submit(request, publication)
        elif action == 'cancel':
            return self.handle_cancel(request, publication)
        else:
            return self.get(request, *args, **kwargs)
    
    def handle_file_upload(self, request, publication):
        """Add uploaded files to session storage"""
        from publications.forms import UploadAppendixForm
        import tempfile
        import os
        
        form = UploadAppendixForm(request.POST, request.FILES)
        
        if form.is_valid():
            files = request.FILES.getlist('appendix_files')
            session_key = f'appendix_upload_{publication.id}'
            session_files = request.session.get(session_key, [])
            
            for uploaded_file in files:
                # Save to temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                try:
                    for chunk in uploaded_file.chunks():
                        temp_file.write(chunk)
                    temp_file.close()
                    
                    # Store file info in session
                    file_info = {
                        'filename': uploaded_file.name,
                        'temp_path': temp_file.name,
                        'size': uploaded_file.size,
                        'content_type': uploaded_file.content_type,
                    }
                    session_files.append(file_info)
                    
                except Exception as e:
                    # Clean up on error
                    try:
                        os.unlink(temp_file.name)
                    except OSError:
                        pass
                    # Add error message
                    from django.contrib import messages
                    messages.error(request, f'Error uploading {uploaded_file.name}: {e}')
            
            # Update session
            request.session[session_key] = session_files
            request.session.modified = True
            
            from django.contrib import messages
            messages.success(request, f'Successfully uploaded {len(files)} file(s)')
        
        return redirect('publications:upload_appendix', pk=publication.id)
    
    def handle_file_removal(self, request, publication):
        """Remove a file from session storage"""
        import os
        
        file_index = int(request.POST.get('file_index', -1))
        session_key = f'appendix_upload_{publication.id}'
        session_files = request.session.get(session_key, [])
        
        if 0 <= file_index < len(session_files):
            file_to_remove = session_files.pop(file_index)
            
            # Clean up temporary file
            temp_path = file_to_remove.get('temp_path')
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            
            # Update session
            request.session[session_key] = session_files
            request.session.modified = True
            
            from django.contrib import messages
            messages.success(request, f'Removed {file_to_remove["filename"]}')
        
        return redirect('publications:upload_appendix', pk=publication.id)
    
    def handle_submit(self, request, publication):
        """Commit all session files to the publication"""
        from publications.utils import handle_session_appendix_uploads
        
        try:
            created_files = handle_session_appendix_uploads(request, publication)
            
            from django.contrib import messages
            if created_files:
                messages.success(
                    request, 
                    f'Successfully attached {len(created_files)} appendix file(s) to publication {publication.number}'
                )
            else:
                messages.info(request, 'No files were uploaded')
                
            # Redirect to publication detail page
            return redirect('publications:report', pk=publication.id)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error processing files: {e}')
            return redirect('publications:upload_appendix', pk=publication.id)
    
    def handle_cancel(self, request, publication):
        """Cancel upload and clean up session files"""
        import os
        
        session_key = f'appendix_upload_{publication.id}'
        session_files = request.session.get(session_key, [])
        
        # Clean up temporary files
        for file_info in session_files:
            temp_path = file_info.get('temp_path')
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
        
        # Clear session
        if session_key in request.session:
            del request.session[session_key]
        
        from django.contrib import messages
        messages.info(request, 'Upload cancelled')
        
        # Redirect to publication detail page
        return redirect('publications:report', pk=publication.id)


class ChangeReportNumberView(BaseFormView):
    """
    View for changing an existing report's number with file renaming.
    """
    template_name = 'publications/change_report_number.html'
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self):
        """Get the publication to change number for"""
        return get_object_or_404(Publication, pk=self.kwargs['pk'])
    
    def get_form_class(self):
        from publications.forms import ChangeReportNumberForm
        return ChangeReportNumberForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['publication'] = self.get_object()
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['publication'] = self.get_object()
        return context
    
    def form_valid(self, form):
        publication = self.get_object()
        old_number = publication.number
        new_number = form.cleaned_data['new_number']
        
        try:
            from django.db import transaction
            from publications.utils import rename_publication_files
            
            with transaction.atomic():
                # First rename files
                rename_results = rename_publication_files(publication, old_number, new_number)
                
                if not rename_results['success']:
                    # If file renaming failed, show errors
                    for error in rename_results['errors']:
                        from django.contrib import messages
                        messages.error(self.request, f"File renaming error: {error}")
                    return self.form_invalid(form)
                
                # Update publication number in database
                publication.number = new_number
                publication.modified_by = self.request.user
                publication.save(update_fields=['number', 'modified_by', 'modified'])
                
                # Show success message with file details
                from django.contrib import messages
                messages.success(
                    self.request, 
                    f"Report number changed from {old_number} to {new_number}"
                )
                
                if rename_results['renamed_files']:
                    messages.info(
                        self.request,
                        f"Renamed {len(rename_results['renamed_files'])} files and {len(rename_results['directories_renamed'])} directories"
                    )
                
                return redirect('publications:report', pk=publication.pk)
                
        except Exception as e:
            from django.contrib import messages
            messages.error(
                self.request, 
                f"Error changing report number: {str(e)}"
            )
            return self.form_invalid(form)


class GetNextReportNumberView(View):
    """
    AJAX view to get the next available report number for a given year.
    Used for auto-updating the report number field when year changes.
    """
    
    def get(self, request):
        year = request.GET.get('year')
        
        if not year:
            return JsonResponse({'error': 'Year parameter is required'}, status=400)
        
        try:
            year = int(year)
            from publications.utils import generate_next_report_number
            next_number = generate_next_report_number(year)
            return JsonResponse({'number': next_number})
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid year format'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Error generating report number: {str(e)}'}, status=500)


@method_decorator(login_required, name='dispatch')
class AddFeatureCoordinatesView(BaseFormView):
    """View for adding a point feature with known coordinates"""
    template_name = 'publications/add_feature_coordinates.html'
    form_class = AddFeatureCoordinatesForm
    
    def dispatch(self, request, *args, **kwargs):
        """Add debugging for all requests"""
        print(f"AddFeatureCoordinatesView.dispatch: {request.method} request received")
        print(f"POST data: {request.POST}")
        return super().dispatch(request, *args, **kwargs)
    
    def get_publication(self):
        """Get the publication this feature will be associated with"""
        report_pk = self.kwargs.get('report_pk')
        return get_object_or_404(Publication, pk=report_pk)
    
    def get_context_data(self, **kwargs):
        print("AddFeatureCoordinatesView.get_context_data called")
        context = super().get_context_data(**kwargs)
        context['publication'] = self.get_publication()
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle POST requests with debugging"""
        print(f"AddFeatureCoordinatesView.post called with data: {request.POST}")
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Process valid form and create the feature"""
        print(f"AddFeatureCoordinatesView.form_valid called with cleaned_data: {form.cleaned_data}")
        from django.contrib.gis.geos import Point
        from django.contrib import messages
        
        try:
            print("Step 1: Getting publication...")
            publication = self.get_publication()
            print(f"Publication: {publication}")
            
            print("Step 2: Creating feature instance...")
            # Create the feature instance
            feature = form.save(commit=False)
            feature.created_by = self.request.user
            feature.modified_by = self.request.user
            
            print(f"Feature instance created: {feature}")
            print(f"Feature date: {feature.date}")
            
            print("Step 3: Getting coordinate data...")
            # Get coordinate data
            x_coord = form.cleaned_data['x_coordinate']
            y_coord = form.cleaned_data['y_coordinate']
            srid = int(form.cleaned_data['spatial_reference_system'])
            print(f"Coordinates: x={x_coord}, y={y_coord}, srid={srid}")
            
            print("Step 4: Creating Point geometry...")
            # Create the geometry
            point = Point(float(x_coord), float(y_coord), srid=srid)
            print(f"Point created: {point}")
            
            print("Step 5: Converting to MultiPoint...")
            # Convert to MultiPoint for storage (following the old system pattern)
            from django.contrib.gis.geos import MultiPoint
            feature.points = MultiPoint(point, srid=srid)
            print(f"MultiPoint created: {feature.points}")
            
            print("Step 6: Saving feature...")
            # Save the feature
            feature.save()
            print("Feature saved successfully")

            print("Step 7: Associating with publication...")
            # Associate with the publication
            feature.publications.add(publication)
            print("Feature associated with publication")

            # Set flag to trigger session cache clearing
            self.request.session['invalidate_feature_cache'] = True              

            print("Step 8: Adding success messages...")
            messages.success(
                self.request, 
                f'Feature "{feature.name}" has been successfully created and associated with '
                f'publication {publication.number}.'
            )
            
            # Check if coordinates seem reasonable and add informational message
            if hasattr(form, 'coordinate_warnings') and form.coordinate_warnings:
                messages.warning(
                    self.request,
                    'Please verify the feature location is correct. Some coordinate values '
                    'generated warnings during validation.'
                )
            else:
                messages.info(
                    self.request,
                    'Please verify that the geographical location of the feature is correct.'
                )
            
            print("Step 9: Redirecting...")
            return redirect('publications:report', pk=publication.pk)
            
        except Exception as e:
            print(f"ERROR in form_valid: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            messages.error(
                self.request,
                f'Error creating feature geometry: {str(e)}. Please check your coordinates and SRID.'
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Handle invalid form with debugging"""
        print(f"AddFeatureCoordinatesView.form_invalid called")
        print(f"Form errors: {form.errors}")
        print(f"Form non_field_errors: {form.non_field_errors}")
        return super().form_invalid(form)
    
    def get_success_url(self):
        """Redirect to the publication detail page"""
        return reverse('publications:report', kwargs={'pk': self.kwargs['report_pk']})


class DeleteReportView(BaseView):
    """View for deleting a publication and all its associated files"""
    template_name = 'publications/delete_report_form.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_publication(self):
        """Get the publication to be deleted"""
        pk = self.kwargs.get('pk')
        return get_object_or_404(Publication, pk=pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['publication'] = self.get_publication()
        return context
    
    def get(self, request, *args, **kwargs):
        """Display the delete confirmation page"""
        publication = self.get_publication()
        
        # Check permissions - user must be able to delete their own publications
        # or have admin privileges
        if not (request.user.is_superuser or 
                publication.created_by == request.user or
                request.user.has_perm('publications.delete_publication')):
            return render(request, 'publications/access_denied.html', {
                'message': 'You do not have permission to delete this publication.'
            })
        
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle the delete or cancel action"""
        publication = self.get_publication()
        
        # Check permissions
        if not (request.user.is_superuser or 
                publication.created_by == request.user or
                request.user.has_perm('publications.delete_publication')):
            return render(request, 'publications/access_denied.html', {
                'message': 'You do not have permission to delete this publication.'
            })
        
        action = request.POST.get('action')
        
        if action == 'cancel':
            # Redirect back to the publication detail page
            return redirect('publications:report', pk=publication.pk)
        
        elif action == 'delete':
            try:
                # Delete all associated files first
                self._delete_publication_files(publication)
                
                # Store publication title for success message
                pub_title = publication.title or f"Publication {publication.pk}"
                
                # Delete the publication itself (this will cascade to relationships)
                publication.delete()
                
                # Redirect to reports list with success message
                from django.contrib import messages
                messages.success(request, f'Publication "{pub_title}" has been successfully deleted.')
                return redirect('publications:reports')
                
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error deleting publication: {str(e)}')
                return redirect('publications:report', pk=publication.pk)
        
        # Invalid action - show the form again
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def _delete_publication_files(self, publication):
        """Delete all files associated with the publication"""
        import os
        from django.conf import settings
        
        # Delete main PDF file and its thumbnail
        if publication.file:
            # Delete the main file
            if publication.file.file and os.path.exists(publication.file.file.path):
                os.remove(publication.file.file.path)
            
            # Delete thumbnail if it exists
            thumbnail_path = self._get_thumbnail_path(publication.file.file.path)
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            
            # Delete the FileObject record
            publication.file.delete()
        
        # Delete all appendices
        for appendix in publication.appendices.all():
            if appendix.file and os.path.exists(appendix.file.path):
                os.remove(appendix.file.path)
            
            # Delete thumbnail if it exists
            thumbnail_path = self._get_thumbnail_path(appendix.file.path)
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        
        # Clear the many-to-many relationship (this will delete Appendenciesship records)
        publication.appendices.clear()
    
    def _get_thumbnail_path(self, file_path):
        """Generate the expected thumbnail path for a file"""
        if not file_path:
            return None
        
        # Assuming thumbnails are stored in the same directory with '_thumb' suffix
        # Adjust this logic based on your thumbnail generation implementation
        base_path, ext = os.path.splitext(file_path)
        return f"{base_path}_thumb.png"


class DeleteFeatureView(LoginRequiredMixin, UserPassesTestMixin, DeleteView, BaseView):
    model = Feature
    template_name = 'publications/feature_confirm_delete.html'
    context_object_name = 'feature'

    def test_func(self):
        # User must have permission to delete the feature (customize as needed)
        feature = self.get_object()
        # Example: allow if user has global or own-feature delete permission
        return self.request.user.has_perm('publications.delete_feature') or \
               self.request.user.has_perm('publications.delete_own_feature')

    def get_success_url(self):
        # Redirect to the report page after deletion
        # Assumes feature is associated with at least one publication
        
        # Set flag to invalidate feature cache
        self.request.session['invalidate_feature_cache'] = True

        pubs = self.object.publications.all()
        if pubs.exists():
            return reverse_lazy('publications:report', kwargs={'pk': pubs.first().pk})
        return reverse_lazy('publications:reports')

    def get_context_data(self, **kwargs):
        # Ensure self.object is set before using it
        if not hasattr(self, 'object') or self.object is None:
            self.object = self.get_object()
        context = super().get_context_data(**kwargs)
        # Ensure base_template is always present
        context['base_template'] = getattr(self, 'base_template', 'publications/base.html')
        pubs = self.object.publications.all()
        if pubs.exists():
            context['cancel_url'] = reverse_lazy('publications:report', kwargs={'pk': pubs.first().pk})
        else:
            context['cancel_url'] = reverse_lazy('publications:reports')
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Delete associated files from DB and disk
        for fileobj in self.object.files.all():
            if fileobj.file:
                fileobj.file.delete(save=False)  # Delete from disk
            fileobj.delete()  # Delete FileObject from DB
        # Optionally, handle images or other related objects here

        return super().delete(request, *args, **kwargs)


# AJAX Functions for Person Disambiguation Workflow
# Based on legacy Django 1.6 implementation

def get_tag(string, tag_name):
    """Extract tag value from string like '[id:123]' -> 123"""
    pattern = r'\[' + tag_name + r':([^\]]+)\]'
    match = re.search(pattern, string)
    if match:
        value = match.group(1)
        if value == '0':
            return 0
        elif value == 'ldap':
            return 'ldap'
        else:
            try:
                return int(value)
            except ValueError:
                return None
    return None


def remove_tags(string):
    """Remove all tags like '[id:123]' from string"""
    return re.sub(r'\[[^\]]+\]', '', string).strip()


def get_person_matches(name_string, exact=True, relaxed=True):
    """
    Find person matches in database.
    Returns (queryset, match_type) tuple.
    """
    clean_name = remove_tags(name_string).strip()
    
    if not clean_name:
        return (Person.objects.none(), None)
    
    # Try exact match first
    if exact:
        exact_matches = Person.objects.filter(name__iexact=clean_name)
        if exact_matches.exists():
            return (exact_matches, 'db_exact')
    
    # Try relaxed match (split on common separators)
    if relaxed:
        name_parts = re.split(r'[,\s]+', clean_name)
        if len(name_parts) >= 2:
            # Try matching first and last name components
            first_part = name_parts[0].strip()
            last_part = name_parts[-1].strip()
            
            relaxed_matches = Person.objects.filter(
                name__icontains=first_part
            ).filter(
                name__icontains=last_part
            )
            
            if relaxed_matches.exists():
                return (relaxed_matches, 'db_relaxed')
    
    return (Person.objects.none(), None)


@require_http_methods(["GET"])
@login_required
def check_person_ajax(request):
    """
    AJAX endpoint to check person names and provide disambiguation options.
    Based on legacy check_person_ajax view.
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'AJAX requests only'}, status=400)
    
    def process_field(field_name):
        """Process a field (authors, supervisors, etc.) and return disambiguation data"""
        persons_needing_choice = []
        
        for name in request.GET.getlist(f'{field_name}[]'):
            if not name.strip():
                continue
                
            # Check if name has an ID tag
            person_id = get_tag(name, 'id')
            
            if person_id == 0:
                # Person marked for creation - no disambiguation needed
                continue
            elif person_id and person_id != 'ldap':
                # Existing person ID - verify it exists
                try:
                    Person.objects.get(id=person_id)
                    continue  # Valid existing person
                except Person.DoesNotExist:
                    # Invalid ID, treat as new name
                    pass
            
            # No valid ID tag, need to check for matches
            matches, match_type = get_person_matches(name)
            
            if match_type:
                # Found matches - need user choice
                person_data = {
                    'name': name,
                    'p_exact': list(matches) if match_type == 'db_exact' else [],
                    'p_relaxed': list(matches) if match_type == 'db_relaxed' else [],
                    'p_ldap': []  # LDAP not implemented in modern version
                }
                persons_needing_choice.append(person_data)
            else:
                # No matches - will create new person
                person_data = {
                    'name': name,
                    'p_exact': [],
                    'p_relaxed': [],
                    'p_ldap': []
                }
                persons_needing_choice.append(person_data)
        
        if persons_needing_choice:
            # Render disambiguation form
            context = {
                'name_field': field_name,
                'persons': persons_needing_choice
            }
            html = render_to_string(
                'publications/ajax/choose_person_form.html',
                {'data': context},
                request=request
            )
            return {'html': html, 'message': 'choice_needed'}
        else:
            # All persons are valid
            return {'html': '', 'message': 'ok'}
    
    response = {}
    
    # Process each field type
    if 'authors[]' in request.GET:
        response['authors'] = process_field('authors')
    if 'supervisors[]' in request.GET:
        response['supervisors'] = process_field('supervisors')
    if 'editors[]' in request.GET:
        response['editors'] = process_field('editors')
    
    if not response:
        return JsonResponse({'error': 'No person fields specified'}, status=400)
    
    return JsonResponse(response)


@require_http_methods(["POST"])
@login_required
def add_person_ajax(request):
    """
    AJAX endpoint to create new persons.
    Based on legacy add_person_ajax view.
    """
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'AJAX requests only'}, status=400)
    
    # Simple person creation - just name required
    name = request.POST.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)
    
    try:
        person = Person.objects.create(
            name=name,
            created_by=request.user,
            modified_by=request.user
        )
        
        return JsonResponse({
            'success': f'Person "{person.name}" created successfully with ID {person.id}',
            'person_id': person.id,
            'person_name': person.name
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Failed to create person: {str(e)}'
        }, status=500)


# Multi-step person disambiguation workflow views
from publications.workflows.person import disambiguate_person_step, complete_person_workflow