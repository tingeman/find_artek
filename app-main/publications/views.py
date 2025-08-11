# === Standard library imports ===
import os
import ast
import datetime
import json
import pdb
import re
import shutil
import tempfile
import time
import traceback

# === Django imports ===
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction, IntegrityError
from django.db.models import QuerySet
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView, DetailView, CreateView, UpdateView, FormView, DeleteView

# Add imports for filtering helpers
from django.db.models import Q, CharField
from django.db.models.functions import Cast



# === Django GIS imports ===
from django.contrib.gis.geos import Point, MultiPoint

# === Third-party imports ===
from django_select2.views import AutoResponseView

# === Project-specific imports ===
from .register_from_file import xlsx_pubs
from find_artek.search import get_query
from publications.forms import (
    LoginForm, AddEditReportForm, AddEditReportFinalSaveForm,
    PublicationForm, AuthorSelectForm, SupervisorSelectForm, DeleteReportForm,
    AddFeatureByCoordinatesForm, AddFeatureByMap, PersonWorkflowMixin, 
    UploadAppendixForm, ChangeReportNumberForm
)
from publications.forms.publication import ImportPublicationFileForm
from publications.forms.mixins import WorkflowAddEditReportForm, WorkflowAddEditReportFinalSaveForm
from publications.library import get_client_ip, is_private
from publications.models import (
    Publication, Topic, Feature, Person, PubType, Authorship, Supervisorship,
    Keyword, FileObject
)
from publications.utils_basic import CaseInsensitively
from publications.utils_models import (
    handle_publication_file_upload, create_ordered_queryset, generate_next_report_number, 
    handle_session_appendix_uploads, rename_publication_files
)
from publications.workflows.person import disambiguate_person_step, complete_person_workflow
from publications.workflows.person import disambiguate_person_step, complete_person_workflow

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
        can_edit_publication = self.object.is_editable_by(user) if user.is_authenticated else False
        can_delete_publication = self.object.is_deletable_by(user) if user.is_authenticated else False
        can_verify_publication = self.object.is_verifiable_by(user) if user.is_authenticated else False
        context.update({
            'associated_features': associated_features,
            'can_edit_publication': can_edit_publication,
            'can_delete_publication': can_delete_publication,
            'can_verify_publication': can_verify_publication,
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
class ReportFormView(BaseFormView):
    """Unified view for both adding and editing reports"""
    model = Publication
    template_name = 'publications/add_edit_report.html'
    select_persons_url = 'select-persons'
    
    def get_form_class(self):
        return WorkflowAddEditReportForm
    
    def is_edit_mode(self):
        return 'pk' in self.kwargs
    
    def get_object(self):
        if self.is_edit_mode():
            # If cache exists, return it
            if hasattr(self, '_object_cache'):
                return self._object_cache

            # To avoid unnecessary database queries, cache the object
            self._object_cache = get_object_or_404(Publication, pk=self.kwargs['pk'])
            return self._object_cache

        return None
    
    def get_initial(self):
        if self.is_edit_mode():
            return self._get_edit_initial()
        return {}
    
    def _get_edit_initial(self):
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
            'publication_topics': publication.publication_topics.all(),
            'publication_keywords': publication.publication_keywords.all(),
        }

        initial_data['authors'] = [auth.person.pk for auth in publication.authorship_set.all().order_by('author_id')]
        print(f"ReportFormView initial data for authors: {initial_data['authors']}")
    
        initial_data['supervisors'] = [sup.person.pk for sup in publication.supervisorship_set.all().order_by('supervisor_id')]
        print(f"ReportFormView initial data for supervisors: {initial_data['supervisors']}")

        return initial_data

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
        """Get form for regular Add/Edit operations"""
        form = super().get_form()
            
        # Configure widget choices based on initial data
        if self.is_edit_mode():
            publication = self.get_object()
            if publication:
                # Get current authors and supervisors from database
                current_authors = publication.authorship_set.all().order_by('author_id')
                current_supervisors = publication.supervisorship_set.all().order_by('supervisor_id')
                
                # Set widget choices
                author_choices = [(str(auth.person.pk), str(auth.person)) for auth in current_authors]
                supervisor_choices = [(str(sup.person.pk), str(sup.person)) for sup in current_supervisors]
                
                form.fields['authors'].widget.choices = author_choices
                form.fields['supervisors'].widget.choices = supervisor_choices

                print(f"🔍 DEBUG: AddEditReportView:get_form - Edit mode: Setting widget choices for {len(author_choices)} authors, {len(supervisor_choices)} supervisors")
        else:
            # Add mode - empty choices
            form.fields['authors'].widget.choices = []
            form.fields['supervisors'].widget.choices = []
            print(f"🔍 DEBUG: AddEditReportView:get_form - Add mode: Setting widget choices empty for authors, supervisors")

        return form

    def form_valid(self, form):
        """Unified form processing for both Add and Edit with workflow support"""
        print(f"🔍 DEBUG: ReportFormView.form_valid called")
        print(f"🔍 DEBUG: Form cleaned_data keys: {list(form.cleaned_data.keys())}")
        print(f"🔍 DEBUG: Form contains data:")
        for key, value in form.cleaned_data.items():
            print(f"🔍 DEBUG:     '{key}': {value} (type: {type(value).__name__})")
        
        # Debug the form data types
        for key, value in form.cleaned_data.items():
            print(f"🔍 DEBUG: Form field '{key}': {value} (type: {type(value).__name__})")
        
        # FIRST: Always store form data in session
        session_data = self._convert_form_to_session_data(form)
        
        # Handle file uploads
        if 'pdffile' in self.request.FILES:
            uploaded_file = self.request.FILES['pdffile']
            print(f"🔍 DEBUG: Found file upload: {uploaded_file.name} (size: {uploaded_file.size} bytes)")
            file_obj = handle_publication_file_upload(uploaded_file, user=self.request.user)
            session_data['uploaded_file_id'] = str(file_obj.id)
                
        # Store in session BEFORE any redirects
        self.request.session['form_data'] = session_data
        if self.is_edit_mode():
            self.request.session['publication_id'] = self.kwargs['pk']
        
        print(f"🔍 DEBUG: Session data stored: {session_data}")

        # THEN: Check if workflow forms need to redirect to disambiguation
        if hasattr(form, 'has_workflow_redirect') and form.has_workflow_redirect():
            print("🔍 DEBUG: Form has workflow redirect, calling form.get_workflow_redirect()")
            return form.get_workflow_redirect()
        else:
            print("🔍 DEBUG: No workflow redirect, proceeding with normal flow")

        # Continue with normal flow - redirect to review
        if self.is_edit_mode():
            return redirect('publications:edit_report_review', pk=self.kwargs['pk'])
        else:
            return redirect('publications:add_report_review')
    
    def _convert_form_to_session_data(self, form):
        """Convert form data to session-compatible format"""
        session_data = {}
        for key, value in self.request.POST.lists():
            # Skip empty file field to avoid misinterpreting as an uploaded file
            if key == 'pdffile' and (not value or value == [''] or all(v == '' for v in value)):
                print(f"🔍 DEBUG: Skipping empty pdffile field: {value}")
                continue
            session_data[key] = value
        return session_data



@method_decorator(login_required, name='dispatch')
class ReportReviewView(BaseView):
    """Handles review of form data before final save"""
    template_name = 'publications/add_edit_report_review.html'
    
    def is_edit_mode(self):
        return 'pk' in self.kwargs
    
    def get_object(self):
        if self.is_edit_mode():
            return get_object_or_404(Publication, pk=self.kwargs['pk'])
        return None
    
    def dispatch(self, request, *args, **kwargs):
        print(f"🔍 DEBUG: ReportReviewView.dispatch - Method: {request.method}")
        print(f"🔍 DEBUG: ReportReviewView.dispatch - Has form_data: {'form_data' in request.session}")
        
        if 'form_data' not in request.session:
            print(f"🔍 DEBUG: No form_data, redirecting to form")
            if self.is_edit_mode():
                return redirect('publications:edit_report', pk=kwargs['pk'])
            else:
                return redirect('publications:add_report')
        
        print(f"🔍 DEBUG: Continuing to {request.method} method")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Pass add/edit state on to the template
        context['action'] = 'edit' if self.is_edit_mode() else 'add'

        # Get the publication object if in edit mode
        if self.is_edit_mode():
            context['publication'] = self.get_object()
            if not context['publication'].is_editable_by(self.request.user):
                context['error'] = "You do not have permissions to edit this publication!"
                return context
        else:
            context['publication'] = None

        # Get review data from session
        if 'form_data' not in self.request.session:
            context['error'] = "No form data found in session. Please fill out the form first."
            return context
    
        print(f"🔍 DEBUG: Session form_data: {self.request.session['form_data']}")
        review_data, changed_fields = self._get_review_data()
        context['review_data'] = review_data
                 
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
        session_data = self.request.session.get('form_data', {})
        review_data = {}
        
        # Debug output to understand the format of session data
        print(f"🔍 DEBUG:ReportReviewView:_get_review_data:  Review session data keys: {list(session_data.keys())}")
        print(f"🔍 DEBUG:ReportReviewView:_get_review_data:  Full session data for debugging:")
        for key, value in session_data.items():
            print(f"🔍 DEBUG:     '{key}': {value} (type: {type(value).__name__})")

        # Convert basic fields
        for field in ['title', 'year', 'number', 'abstract', 'comment']:
            value = session_data.get(field, [])
            review_data[field] = value[0] if isinstance(value, list) and value else value
        
        # Convert type
        type_pk = session_data.get('type', [])
        print(f"🔍 DEBUG: Processing type field. Raw value: {type_pk} (type: {type(type_pk).__name__})")
        if isinstance(type_pk, list) and type_pk:
            try:
                pub_type = PubType.objects.get(pk=int(type_pk[0]))
                print(f"🔍 DEBUG: Found PubType object: {pub_type} (ID: {pub_type.id}, type: {pub_type.type})")
                # Pass the actual object rather than just the string
                review_data['type'] = pub_type
            except (PubType.DoesNotExist, ValueError):
                print(f"🔍 DEBUG: Error finding PubType: {e}")
                review_data['type'] = type_pk[0]
        else:
            print(f"🔍 DEBUG: type is not a list, using type value directly: {type_pk}")
            review_data['type'] = type_pk
        
        # Convert authors/supervisors
        review_data['authors'] = self._convert_model_ids_to_strings(Person, 'authors', session_data.get('authors', []))
        review_data['supervisors'] = self._convert_model_ids_to_strings(Person, 'supervisors', session_data.get('supervisors', []))

        # Convert topics and keywords
        review_data['publication_topics'] = self._convert_model_ids_to_strings(Topic, 'topics', session_data.get('publication_topics', []))
        review_data['publication_keywords'] = self._convert_model_ids_to_strings(Keyword, 'keywords', session_data.get('publication_keywords', []))

        # Extract file IDs if they exist
        review_data['uploaded_file_id'] = session_data.get('uploaded_file_id', None)
        review_data['existing_file'] = self.get_object().file if self.is_edit_mode() else None
        if review_data['existing_file']:
            review_data['existing_file_id'] = review_data['existing_file'].pk
        else:
            review_data['existing_file_id'] = None
        # Fix: Normalize delete_pdf to boolean
        raw_delete_pdf = session_data.get('delete_pdf', False)
        print(f"🔍 DEBUG: Raw delete_pdf value: {raw_delete_pdf} (type: {type(raw_delete_pdf).__name__})")
        if isinstance(raw_delete_pdf, list):
            # If it's a list, take the first element
            raw_delete_pdf = raw_delete_pdf[0] if raw_delete_pdf else False
        review_data['delete_pdf'] = raw_delete_pdf in [True, 'true', 'True', 'on', '1']


        # Add file IDs to review data if they exist
        if review_data['uploaded_file_id']:
            print(f"🔍 DEBUG: uploaded_file_id: {review_data['uploaded_file_id']} (type: {type(review_data['uploaded_file_id']).__name__ if review_data['uploaded_file_id'] else 'None'})")
            review_data['uploaded_file'] = FileObject.objects.filter(pk=review_data['uploaded_file_id']).first()
        if review_data['existing_file_id']:
            print(f"🔍 DEBUG: existing_file_id: {review_data['existing_file_id']} (type: {type(review_data['existing_file_id']).__name__ if review_data['existing_file_id'] else 'None'})")
            review_data['existing_file'] = FileObject.objects.filter(pk=review_data['existing_file_id']).first()

        changed_fields = self._get_changed_fields(review_data=review_data)

        return review_data, changed_fields
        
    def _convert_model_ids_to_strings(self, this_model, label, ids):
        """Convert model IDs to string representations"""
        items = []
        for item_id in ids:
            try:
                item = this_model.objects.get(pk=int(item_id))
                items.append(str(item))
            except (this_model.DoesNotExist, ValueError) as e:
                print(f"Error processing {label} from {this_model.__name__} PK {item_id}: {e}")
                items.append(str(item_id))
        return items

    def _convert_person_ids_to_strings(self, person_ids):
        """Convert person IDs to person objects"""
        persons = []
        for person_id in person_ids:
            try:
                person = Person.objects.get(pk=int(person_id))
                persons.append(str(person))
            except (Person.DoesNotExist, ValueError):
                print(f"Error processing author PK {person_id}: {e}")
                persons.append(str(person_id))
        return persons
    
    def _get_changed_fields(self, review_data={}):
        """Determine which fields changed (for edit mode)"""
        if not self.is_edit_mode():
            return {}

        print(f"🔍 DEBUG: ReportReviewView._get_changed_fields called (in edit mode)")

        changed_fields = {}

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
            has_new_file = 'uploaded_file_id' in review_data and review_data['uploaded_file_id'] is not None
            has_delete_request = 'delete_pdf' in review_data and review_data['delete_pdf'] == True
            
            # If we have a file upload or delete request, mark as changed
            if has_new_file or has_delete_request:
                changed_fields['file'] = True
                print(f"🔍 DEBUG: File marked as changed - has_new_file: {has_new_file}, has_delete_request: {has_delete_request}")

        print(f"🔍 DEBUG: ReportReviewView._get_changed_fields - Review data keys: {list(review_data.keys())}")
        print(f"🔍 DEBUG: ReportReviewView._get_changed_fields - Review data:")
        for key, value in review_data.items():
            print(f"🔍 DEBUG:     '{key}': {value} (type: {type(value).__name__})")

        print(f"🔍 DEBUG: ReportReviewView._get_changed_fields - Changed fields identified: {changed_fields}")

        return changed_fields
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests - show the review page"""
        print(f"🔍 DEBUG: ReportReviewView.get called")
        print(f"🔍 DEBUG: Session keys: {list(request.session.keys())}")
        print(f"🔍 DEBUG: Has form_data: {'form_data' in request.session}")

        print(f"🔍 DEBUG: form_data: {request.session.get('form_data', {})}")
        print(f"🔍 DEBUG: updated_form_data: {request.session.get('updated_form_data', {})}")

        print(f"🔍 DEBUG: Template name: {self.template_name}")

        context = self.get_context_data(**kwargs)
        print(f"🔍 DEBUG: Context keys: {list(context.keys())}")

        # if context['changed_fields'] is empty, then redirect to report view
        if not context['changed_fields']:
            print(f"🔍 DEBUG: No changed fields, redirecting to report view")
            if self.is_edit_mode():
                return redirect('publications:report', pk=kwargs['pk'])
            # else:
            #     return redirect('publications:add_report')

        response = render(request, self.template_name, context)
        print(f"🔍 DEBUG: Response type: {type(response)}")
        print(f"🔍 DEBUG: Response status: {response.status_code}")
        print(f"🔍 DEBUG: About to return response")

        #return render(request, self.template_name, context)
        return response

        # if not 'form_data' in request.session:
        #     print(f"🔍 DEBUG: No form_data in session, redirecting to form")
        #     if self.is_edit_mode():
        #         return redirect('publications:edit_report', pk=kwargs['pk'])
        #     else:
        #         return redirect('publications:add_report')

        # print(f"🔍 DEBUG: Form data exists, proceeding to render review page")


    def post(self, request, *args, **kwargs):
        """Handle form submission from review page"""
        print(f"🔍 DEBUG: ReportReviewView.post called - THIS SHOULD NOT HAPPEN ON GET!")
        print(f"🔍 DEBUG: POST data: {request.POST}")
        if self.is_edit_mode():
            return redirect('publications:edit_finalize', pk=kwargs['pk'])
        else:
            return redirect('publications:add_finalize')



@method_decorator(login_required, name='dispatch')
class ReportFinalizeView(BaseView):
    """Handles final save of publication"""
    
    def get_form_class(self):
        return WorkflowAddEditReportForm

    def is_edit_mode(self):
        return 'pk' in self.kwargs
    
    def get_object(self):
        if self.is_edit_mode():
            return get_object_or_404(Publication, pk=self.kwargs['pk'])
        return None
    
    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form"""
        kwargs = super().get_form_kwargs()
        
        # Add request object for workflow forms
        kwargs['request'] = self.request
        
        # For edit mode, always pass the instance
        if self.is_edit_mode():
            kwargs['instance'] = self.get_object()
            
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        if 'form_data' not in request.session:
            if self.is_edit_mode():
                return redirect('publications:edit_report', pk=kwargs['pk'])
            else:
                return redirect('publications:add_report')
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Save the publication with session data"""

        # 1. Get session data
        session_data = self.request.session.get('form_data', {})
        print(f"🔍 DEBUG: ReportFinalizeView:post - Session data found: {bool(session_data)}")
        print(f"🔍 DEBUG: ReportFinalizeView:post - Session data keys: {list(session_data.keys())}")

        if not session_data:
            # No session data, redirect back
            if self.is_edit_mode():
                print(f"🔍 DEBUG: No session data, redirecting to edit_report")
                return redirect('publications:edit_report', pk=kwargs['pk'])
            else:
                print(f"🔍 DEBUG: No session data, redirecting to add_report")
                return redirect('publications:add_report')

        # 2. Convert session data to form input format
        form_input = self._session_data_to_form_input(session_data)

        print(f"🔍 DEBUG: ReportFinalizeView:post - Form input prepared from session data:")
        for key, value in form_input.items():
            print(f"🔍 DEBUG:     '{key}': {value} (type: {type(value).__name__})")

        print(f"🔍 DEBUG: ReportFinalizeView:post - Form input prepared:")
        for key, value in form_input.items():
            print(f"🔍 DEBUG:     '{key}': {value} (type: {type(value).__name__})")

        # 2. Prepare form kwargs
        form_kwargs = {'request': request}
        if self.is_edit_mode():
            form_kwargs['instance'] = self.get_object()

        # 3. Create form instance with session data
        form_class = self.get_form_class()
        form = form_class(form_input, **form_kwargs)

        print(f"🔍 DEBUG: ReportFinalizeView:post - Form instance created")

        # 4. Validate and save
        if form.is_valid():
            print(f"🔍 DEBUG: Form is valid, proceeding to save publication")

            try:
                with transaction.atomic():
                    publication = form.save(commit=False)
                    publication.modified_by = request.user
                    if not publication.pk:
                        publication.created_by = request.user
                    
                    if not self.is_edit_mode() and 'year' in form_input and form_input['year']:
                        publication.number = generate_next_report_number(form_input['year'])
                       
                    publication.save()
                    self._handle_relationships(publication)
                    self._handle_files(publication)
                    publication.save()
                    del request.session['form_data']            
                return redirect('publications:report', pk=publication.pk)
            except Exception as e:
                messages.error(request, f'Error saving publication: {e}')
                print(f"🔍 DEBUG: Error saving publication: {e}")
                if self.is_edit_mode():
                    return redirect('publications:edit_report_review', pk=kwargs['pk'])
                else:
                    return redirect('publications:add_report_review')
        else:
            # If invalid, redirect back to review
            print(f"🔍 DEBUG: Form is invalid: {form.errors}")

            # print all form values
            print(f"🔍 DEBUG: Form cleaned_data:")
            for key, value in form.cleaned_data.items():
                print(f"🔍 DEBUG:     '{key}': {value} (type: {type(value).__name__})")

            messages.error(request, 'Form data is invalid. Please check your input.')
            if self.is_edit_mode():
                return redirect('publications:edit_report_review', pk=kwargs['pk'])
            else:
                return redirect('publications:add_report_review')
    
    def _session_data_to_form_input(self, session_data):
        """Convert session data to form input format"""
        form_input = {}
        for key, value in session_data.items():
            if key in ['authors', 'supervisors', 'publication_topics', 'publication_keywords']:
                form_input[key] = value
            elif key == 'delete_pdf':
                # Normalize delete_pdf to boolean
                form_input[key] = value in [True, 'true', 'True', 'on', '1']
            elif isinstance(value, list):
                # If the value is a list, take the first item if it exists
                if value:
                    # take the first item if it exists
                    # there should never be more than one item here
                    form_input[key] = value[0]
                    if len(value) > 1:
                        print(f"🔍 DEBUG: Warning: Multiple values found for {key} in session data, using first value only: {value[0]}")
                else:
                    form_input[key] = None
            else:
                form_input[key] = value
        return form_input


    def _handle_relationships(self, publication):
        """Handle authors, supervisors, topics, keywords"""
        session_data = self.request.session['form_data']
        
        print(f"🔍 DEBUG: ReportFinalizeView:_handle_relationships called for publication {publication.pk}" )
        print(f"🔍 DEBUG: Session data keys: {list(session_data.keys())}")
        print(f"🔍 DEBUG: Session data:")
        for key, value in session_data.items():
            print(f"🔍 DEBUG:     '{key}': {value} (type: {type(value).__name__})")

        # Authors
        publication.authorship_set.all().delete()
        for i, author_pk in enumerate(session_data.get('authors', [])):
            person = Person.objects.get(pk=int(author_pk))
            Authorship.objects.create(
                publication=publication,
                person=person,
                author_id=i
            )
        
        # Supervisors  
        publication.supervisorship_set.all().delete()
        for i, supervisor_pk in enumerate(session_data.get('supervisors', [])):
            person = Person.objects.get(pk=int(supervisor_pk))
            Supervisorship.objects.create(
                publication=publication,
                person=person,
                supervisor_id=i
            )
        
        # Topics
        publication.publication_topics.clear()
        for topic_pk in session_data.get('publication_topics', []):
            try:
                topic = Topic.objects.get(pk=int(topic_pk))
                publication.publication_topics.add(topic)
            except Topic.DoesNotExist:
                print(f"🔍 DEBUG: Topic with PK {topic_pk} does not exist, skipping")

        # Keywords
        publication.publication_keywords.clear()
        for keyword_pk in session_data.get('publication_keywords', []):
            try:
                keyword = Keyword.objects.get(pk=int(keyword_pk))
                publication.publication_keywords.add(keyword)
            except Keyword.DoesNotExist:
                print(f"🔍 DEBUG: Keyword with PK {keyword_pk} does not exist, skipping")

    def _handle_files(self, publication):
        """Handle file operations"""
        session_data = self.request.session['form_data']
        
        if 'uploaded_file_id' in session_data:
            print(f"🔍 DEBUG: ReportFinalizeView:_handle_files called with uploaded_file_id")

            uploaded_file_obj = FileObject.objects.get(pk=session_data['uploaded_file_id'])
           
            original_file_obj_backup = self._temporarily_rename_existing_file(publication)

            try:
                final_file_obj = self._move_temp_file_to_final(uploaded_file_obj, publication)
                publication.file = final_file_obj
                publication.save()
            except:
                print(f"🔍 DEBUG: Error moving file to final location, restoring existing file")  
                self._restore_existing_file(publication, original_file_obj_backup)              
                # reraise exception
                raise

            if original_file_obj_backup:
                print(f"🔍 DEBUG: Deleting temporary file object: {original_file_obj_backup.pk}")
                try:
                    original_file_obj_backup.delete()  # Clean up the temporary file object
                    print(f"🔍 DEBUG: File moved successfully to publication {publication.pk}: {final_file_obj.pk}")
                except Exception as e:
                    print(f"🔍 DEBUG: Error deleting temporary file object: {e}")
                    pass
        elif 'delete_pdf' in session_data and session_data['delete_pdf']:
            print(f"🔍 DEBUG: Deleting existing file for publication {publication.pk}")
            if publication.file:
                # Store the file reference before deletion
                file_to_delete = publication.file
                
                # First update the publication to remove the file reference
                publication.file = None
                publication.save(update_fields=['file'])
                
                # Delte the file on disk
                if file_to_delete.file and os.path.exists(file_to_delete.file.path):
                    print(f"🔍 DEBUG: Deleting file from disk: {file_to_delete.file.path}")
                    os.remove(file_to_delete.file.path)

                # Then delete the actual file object
                file_to_delete.delete()

    def _temporarily_rename_existing_file(self, publication):
        """Will physically rename existing file on disk, forcing overwrite of any existing file 
        with the same name"""
        if publication.file:
            print(f"🔍 DEBUG: Temporarily renaming existing file for publication {publication.pk}")
            original_file_path = publication.file.file.path
            print(f"🔍 DEBUG: Original file path: {original_file_path}")
            # Create a temporary name to avoid conflicts
            temp_file_path = original_file_path + '.old'
            print(f"🔍 DEBUG: Temporary file path: {temp_file_path}")
            # Rename the file
            try:
                os.rename(original_file_path, temp_file_path)
                print(f"🔍 DEBUG: Existing file renamed to temporary path: {temp_file_path}")
                # Update the publication file reference
                publication.file.file.name = temp_file_path
            except OSError as e:
                print(f"🔍 DEBUG: Error renaming file: {e}")
                publication.file.file = None  # Clear the file reference
            publication.file.save() 
            return publication.file
        else:
            return None

    def _restore_existing_file(self, publication, temp_file_object):
        """Restore the existing file to its original name (needed if transactions fail)"""

        print(f"🔍 DEBUG: Restoring existing file for publication {publication.pk}")
        if temp_file_object.file:
            temp_file_path = temp_file_object.file.path
            original_file_path = temp_file_path.replace('.old', '')
            if os.path.exists(temp_file_path):
                print(f"🔍 DEBUG: Restoring file from {temp_file_path} to {original_file_path}")
                # Rename back to original
                os.rename(temp_file_path, original_file_path)
                # Update the publication file reference
                publication.file.file.name = original_file_path
                publication.file.save()
        
    def _move_temp_file_to_final(self, temp_file_obj, publication):
        """Move a temporary file to its final location"""
                
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
        
        base_path, ext = os.path.splitext(original_final_path)
        while os.path.exists(full_final_path):
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



class VerifyReportView(BaseView):
    """
    View for verifying a report. Sets the 'verified' flag on a Publication if the user has permission.
    """
    template_name = 'publications/access_denied.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        pub_id = self.kwargs.get('pub_id')
        if pub_id:
            return get_object_or_404(Publication, pk=pub_id)
        return None

    def get(self, request, *args, **kwargs):
        publication = self.get_object()
        if not publication:
            return redirect('publications:reports')

        if not publication.is_verifiable_by(request.user):
            error = "You do not have permissions to verify this report!"
            context = {'pub': publication, 'error': error}
            return render(request, self.template_name, context)

        publication.verified = True
        publication.save()
        messages.success(request, f"Report ({publication.id}) '{publication.number}' was verified.")
        return redirect('publications:report', pk=publication.pk)


class UnverifyReportView(BaseView):
    """
    View for unverifying a report. Sets the 'verified' flag to False if the user has permission.
    """
    template_name = 'publications/access_denied.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        pub_id = self.kwargs.get('pub_id')
        if pub_id:
            return get_object_or_404(Publication, pk=pub_id)
        return None

    def get(self, request, *args, **kwargs):
        publication = self.get_object()
        if not publication:
            return redirect('publications:reports')

        if not publication.is_verifiable_by(request.user):
            error = "You do not have permissions to unverify this report!"
            context = {'pub': publication, 'error': error}
            return render(request, self.template_name, context)

        publication.verified = False
        publication.save()
        messages.success(request, f"Report ({publication.id}) '{publication.number}' was unverified.")
        return redirect('publications:report', pk=publication.pk)


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
                    messages.error(request, f'Error uploading {uploaded_file.name}: {e}')
            
            # Update session
            request.session[session_key] = session_files
            request.session.modified = True
            
            messages.success(request, f'Successfully uploaded {len(files)} file(s)')
        
        return redirect('publications:upload_appendix', pk=publication.id)
    
    def handle_file_removal(self, request, publication):
        """Remove a file from session storage"""
        
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
            
            messages.success(request, f'Removed {file_to_remove["filename"]}')
        
        return redirect('publications:upload_appendix', pk=publication.id)
    
    def handle_submit(self, request, publication):
        """Commit all session files to the publication"""
        
        try:
            created_files = handle_session_appendix_uploads(request, publication)
            
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
            messages.error(request, f'Error processing files: {e}')
            return redirect('publications:upload_appendix', pk=publication.id)
    
    def handle_cancel(self, request, publication):
        """Cancel upload and clean up session files"""
        
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
        print("🔍 DEBUG: ChangeReportNumberView.form_valid called")
        publication = self.get_object()
        old_number = publication.number
        new_number = form.cleaned_data['new_number']
        print(f"🔍 DEBUG: old_number={old_number}, new_number={new_number}")
        print(f"🔍 DEBUG: form.cleaned_data={form.cleaned_data}")
        try:
            with transaction.atomic():
                print("🔍 DEBUG: Starting file renaming...")
                rename_results = rename_publication_files(publication, old_number, new_number)
                print(f"🔍 DEBUG: rename_results={rename_results}")
                if not rename_results['success']:
                    print("🔍 DEBUG: File renaming failed, errors:", rename_results['errors'])
                    for error in rename_results['errors']:
                        messages.error(self.request, f"File renaming error: {error}")
                    return self.form_invalid(form)
                print("🔍 DEBUG: Updating publication number in database...")
                publication.number = new_number
                publication.modified_by = self.request.user
                publication.save(update_fields=['number', 'modified_by'])
                print("🔍 DEBUG: Publication updated and saved.")
                messages.success(
                    self.request, 
                    f"Report number changed from {old_number} to {new_number}"
                )
                if rename_results['renamed_files']:
                    print(f"🔍 DEBUG: Renamed files: {rename_results['renamed_files']}")
                    print(f"🔍 DEBUG: Renamed directories: {rename_results['directories_renamed']}")
                    messages.info(
                        self.request,
                        f"Renamed {len(rename_results['renamed_files'])} files and {len(rename_results['directories_renamed'])} directories"
                    )
                print("🔍 DEBUG: Redirecting to publication report view...")
                return redirect('publications:report', pk=publication.pk)
        except Exception as e:
            print(f"🔍 DEBUG: Exception in form_valid: {type(e).__name__}: {str(e)}")
            messages.error(
                self.request, 
                f"Error changing report number: {str(e)}"
            )
            return self.form_invalid(form)


@method_decorator(login_required, name='dispatch')
class AddFeatureCoordinatesView(BaseFormView):
    """View for adding a point feature with known coordinates"""
    template_name = 'publications/add_feature_coordinates.html'
    form_class = AddFeatureByCoordinatesForm
    
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


class AddFeatureByMapView(LoginRequiredMixin, FormView):
    """View for adding a feature by clicking on a map"""
    template_name = 'publications/add_feature_by_map.html'
    form_class = AddFeatureByMap
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to get the publication"""
        self.publication = self.get_publication()
        return super().dispatch(request, *args, **kwargs)
    
    def get_publication(self):
        """Get the publication object"""
        report_pk = self.kwargs.get('report_pk')
        return get_object_or_404(Publication, pk=report_pk)
    
    def get_context_data(self, **kwargs):
        """Add publication to context"""
        context = super().get_context_data(**kwargs)
        context['publication'] = self.publication
        # Add any MapBox or other API keys if needed
        if hasattr(settings, 'MAPBOX_ACCESS_TOKEN'):
            context['mapbox_access_token'] = settings.MAPBOX_ACCESS_TOKEN
        return context
    
    def post(self, request, *args, **kwargs):
        """Process the form submission"""
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Create and save the feature with geometry from the map"""
        try:
            # Create feature object but don't save yet
            feature = form.save(commit=False)
            feature.created_by = self.request.user

            # Process geometry from the correct hidden field
            geojson_data = self.request.POST.get('geojson_data', '')
            if geojson_data:
                try:
                    # Parse the GeoJSON data
                    geojson = json.loads(geojson_data)

                    # Create a MultiPoint geometry from the coordinates
                    coordinates = []
                    if geojson.get('type') == 'FeatureCollection':
                        for f in geojson.get('features', []):
                            if f.get('geometry', {}).get('type') == 'Point':
                                coords = f['geometry']['coordinates']
                                coordinates.append(coords)

                    if coordinates:
                        print(f"DEBUG: Raw coordinates list: {coordinates}")
                        points = []
                        for idx, pair in enumerate(coordinates):
                            print(f"DEBUG: Coordinate pair {idx}: {pair} (type: {type(pair)})")
                            try:
                                lon, lat = pair
                                pt = Point(lon, lat)
                                print(f"DEBUG: Created Point: {pt} (type: {type(pt)})")
                                points.append(pt)
                            except Exception as e:
                                print(f"DEBUG: Error creating Point from {pair}: {e}")
                        print(f"DEBUG: Points list for MultiPoint: {points}")
                        print(f"DEBUG: Types in points list: {[type(p) for p in points]}")
                        geom = MultiPoint(points, srid=4326)
                        feature.points = geom
                        print(f"Created MultiPoint with {len(points)} points")
                    else:
                        raise ValueError("No valid coordinates found in map data")
                except Exception as e:
                    print(f"Error parsing GeoJSON: {str(e)}")
                    raise

            # Save the feature
            feature.save()
            print(f"Feature saved with ID: {feature.pk}")
            publication = self.get_publication()
            feature.publications.add(publication) 
            print(f"Feature added to publication {publication.pk}")
            

            messages.success(
                self.request,
                'Feature added successfully!'
            )

            return redirect('publications:report', pk=publication.pk)

        except Exception as e:
            print(f"ERROR: Exception while creating feature: {e}")
            print(traceback.format_exc())
            messages.error(
                self.request, 
                f'An error occurred while creating the feature: {str(e)}. '
                'Please try again or contact support.'
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Handle invalid form data"""
        print(f"AddFeatureByMapView.form_invalid called. Errors: {form.errors}")
        messages.error(
            self.request, 
            'There was a problem with your feature data. '
            'Please correct the errors below and try again.'
        )
        return super().form_invalid(form)


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
                messages.success(request, f'Publication "{pub_title}" has been successfully deleted.')
                return redirect('publications:reports')
                
            except Exception as e:
                messages.error(request, f'Error deleting publication: {str(e)}')
                return redirect('publications:report', pk=publication.pk)
        
        # Invalid action - show the form again
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def _delete_publication_files(self, publication):
        """Delete all files associated with the publication"""
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



@method_decorator(login_required, name='dispatch')
class AddReportsFromFileUploadView(BaseFormView):
    template_name = "publications/add_reports_from_file_upload.html"
    form_class = ImportPublicationFileForm

    def form_valid(self, form):
        uploaded_file = form.cleaned_data["file"]
        upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        # Call the parsing function
        filemessages = xlsx_pubs(file_path, user=self.request.user)
        for level, msg in filemessages:
            messages.add_message(self.request, level, msg)

        # Redirect back to the same page to show messages
        return redirect("publications:add_reports_from_file_upload")

    def form_invalid(self, form):
        print("🔍 DEBUG: ChangeReportNumberView.form_invalid called")
        print(f"🔍 DEBUG: form.errors={form.errors}")
        print(f"🔍 DEBUG: form.cleaned_data={getattr(form, 'cleaned_data', None)}")
        messages.error(self.request, "Please correct the errors below.")
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)



class BulkDeletePublicationsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'publications/bulk_delete_publications.html'

    def test_func(self):
        # Require permission to delete publications
        return self.request.user.has_perm('publications.delete_publication')

    def get_queryset(self, request):
        qs = Publication.objects.all().prefetch_related('authors')

        # Filters
        year_q = request.GET.get('year', '').strip()
        number_q = request.GET.get('number', '').strip()
        title_q = request.GET.get('title', '').strip()
        author_q = request.GET.get('author', '').strip()

        if year_q:
            # Allow partial match on year by casting to CharField
            qs = qs.annotate(year_str=Cast('year', CharField())).filter(year_str__icontains=year_q)
        if number_q:
            qs = qs.filter(number__icontains=number_q)
        if title_q:
            qs = qs.filter(title__icontains=title_q)
        if author_q:
            qs = qs.filter(
                Q(authors__first__icontains=author_q) |
                Q(authors__middle__icontains=author_q) |
                Q(authors__prelast__icontains=author_q) |
                Q(authors__last__icontains=author_q)
            )
        return qs.order_by('-year', '-number', 'title').distinct()

    def get(self, request):
        publications = self.get_queryset(request)
        context = {
            'publications': publications,
            'filters': {
                'year': request.GET.get('year', ''),
                'number': request.GET.get('number', ''),
                'title': request.GET.get('title', ''),
                'author': request.GET.get('author', ''),
            },
            'confirm': False,
            'selected_ids': [],
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        if 'cancel' in request.POST:
            messages.info(request, 'Bulk delete cancelled.')
            return redirect('publications:bulk_delete_publications')

        selected_ids = request.POST.getlist('selected_publications')
        if not selected_ids:
            messages.warning(request, 'No publications selected.')
            return redirect('publications:bulk_delete_publications')

        # If confirm flag is present, perform deletion
        if request.POST.get('confirm') == 'yes':
            qs = Publication.objects.filter(pk__in=selected_ids)
            count = qs.count()
            qs.delete()
            messages.success(request, f'Deleted {count} publication(s).')
            return redirect('publications:bulk_delete_publications')

        # Otherwise, render confirmation
        publications = Publication.objects.filter(pk__in=selected_ids).prefetch_related('authors')
        context = {
            'confirm': True,
            'publications_to_delete': publications,
            'count': publications.count(),
            'selected_ids': selected_ids,
        }
        return render(request, self.template_name, context)