# === Standard library imports ===
import os
import shutil

# === Django imports ===
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction

from django.shortcuts import get_object_or_404, render, redirect
from django.utils.decorators import method_decorator
from django.views import View

# Add imports for filtering helpers
from django.db.models import Q, CharField
from django.db.models.functions import Cast

# === Project-specific imports ===
from publications.forms import ChangeReportNumberForm

from publications.forms.publication import (
    DisambiguationWorkflowAddEditReportForm, 
    DisambiguationWorkflowAddEditReportFinalSaveForm
)

from publications.models import (
    Publication, Topic, Feature, Person, PubType, Authorship, Supervisorship,
    Keyword, FileObject
)

from publications.utils_models import (
    handle_publication_file_upload, generate_next_report_number, rename_publication_files
)

from publications.views.base_views import BaseView, BaseDetailView, BaseFormView 

from publications.mixins.disambiguation import PersonDisambiguationViewReaderMixin, PersonDisambiguationViewProcessorMixin



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
class ReportFormView(PersonDisambiguationViewReaderMixin, BaseFormView):
    """Unified view for both adding and editing reports"""
    model = Publication
    template_name = 'publications/add_edit_report.html'
    select_persons_url = 'select-persons'
    
    def get_form_class(self):
        klass = DisambiguationWorkflowAddEditReportForm
        print(f"DEBUG ReportFormView.get_form_class: returning {klass.__name__}")
        return klass
    
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
        print(f"DEBUG ReportFormView.get_form_kwargs: session keys={list(self.request.session.keys())}")
        # Add request object for workflow forms
        kwargs['request'] = self.request
        # For edit mode, always pass the instance
        if self.is_edit_mode():
            kwargs['instance'] = self.get_object()
        print(f"DEBUG ReportFormView.get_form_kwargs: kwargs keys={list(kwargs.keys())}")
        return kwargs

    def get_form(self):
        """Get form for regular Add/Edit operations"""
        form = super().get_form()
        print(f"DEBUG ReportFormView.get_form: form class={form.__class__.__name__}, mixins={form.__class__.__mro__}")
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
        print(f"DEBUG ReportFormView.form_valid: called with form class={form.__class__.__name__}, mixins={form.__class__.__mro__}")
        print(f"DEBUG ReportFormView.form_valid: session keys={list(self.request.session.keys())}")
        print(f"DEBUG ReportFormView.form_valid: cleaned_data={form.cleaned_data}")
        # FIRST: Always store form data in session
        session_data = self._convert_form_to_session_data(form)
        # Handle file uploads
        if 'pdffile' in self.request.FILES:
            uploaded_file = self.request.FILES['pdffile']
            print(f"🔍 DEBUG: Found file upload: {uploaded_file.name} (size: {uploaded_file.size} bytes)")
            file_obj = handle_publication_file_upload(uploaded_file, user=self.request.user)
            session_data['uploaded_file_id'] = str(file_obj.id)
                
        # TODO: Could/should we make a mixin for handling session storage of form data?

        # Store in session BEFORE any redirects
        self.request.session['form_data'] = session_data
        if self.is_edit_mode():
            self.request.session['publication_id'] = self.kwargs['pk']
        
        print(f"🔍 DEBUG: Session data stored: {session_data}")

        # Check if disambiguation workflow is needed
        if hasattr(form, '_workflow_redirect') and form._workflow_redirect:
            print("🔍 DEBUG: Form has workflow redirect, returning redirect")
            return form._workflow_redirect
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
class ReportReviewView(PersonDisambiguationViewReaderMixin, BaseView):
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
            print(f"🔍 DEBUG: ReportReviewView.dispatch - No form_data, redirecting to form")
            if self.is_edit_mode():
                return redirect('publications:edit_report', pk=kwargs['pk'])
            else:
                return redirect('publications:add_report')
        
        print(f"🔍 DEBUG: ReportReviewView.dispatch - Continuing to {request.method} method")
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
    
        print(f"🔍 DEBUG: ReportReviewView.get_context_data - Session form_data: {self.request.session['form_data']}")
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
            except (PubType.DoesNotExist, ValueError) as e:
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
            if isinstance(item_id, str) and item_id.startswith('CREATE:'):
                # Just display the name part with a "New:" prefix to indicate it will be created later
                item_name = item_id[7:]  # Remove the CREATE: prefix
                items.append(f"{item_name} [new]")
                continue
                
            try:
                item = this_model.objects.get(pk=int(item_id))
                items.append(str(item))
            except (this_model.DoesNotExist, ValueError) as e:
                print(f"Error processing {label} from {this_model.__name__} PK {item_id}: {e}")
                items.append(str(item_id))
        return items

    def _convert_person_ids_to_strings(self, person_ids):
        """Convert person IDs to person objects"""
        items = []
        for person_id in person_ids:
            if isinstance(person_id, str) and person_id.startswith('CREATE:'):
                # Just display the name part with a "New:" prefix to indicate it will be created later
                person_name = person_id[7:]  # Remove the CREATE: prefix
                items.append(f"{person_name} [new]")
                continue

            try:
                person = Person.objects.get(pk=int(person_id))
                items.append(str(person))
            except (Person.DoesNotExist, ValueError) as e:
                print(f"Error processing author PK {person_id}: {e}")
                items.append(str(person_id))
        return items

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
        print(f"           Session keys: {list(request.session.keys())}")
        print(f"           Has form_data: {'form_data' in request.session}")

        print(f"           form_data: {request.session.get('form_data', {})}")
        print(f"           person_disambiguation.resolved_form_data: {request.session.get('person_disambiguation', {}).get('resolved_form_data', {})}")
        print(f"           person_disambiguation.resolved_field_values: {request.session.get('person_disambiguation', {}).get('resolved_field_values', {})}")

        print(f"           Template name: {self.template_name}")

        context = self.get_context_data(**kwargs)
        print(f"           Context keys: {list(context.keys())}")

        # if context['changed_fields'] is empty, then redirect to report view
        if not context['changed_fields']:
            print(f"🔍 DEBUG: ReportReviewView.get - No changed fields, redirecting to report view")
            if self.is_edit_mode():
                return redirect('publications:report', pk=kwargs['pk'])
            # else:
            #     return redirect('publications:add_report')

        response = render(request, self.template_name, context)
        print(f"🔍 DEBUG: ReportReviewView.get - Response type: {type(response)}")
        print(f"🔍 DEBUG: ReportReviewView.get - Response status: {response.status_code}")
        print(f"🔍 DEBUG: ReportReviewView.get - About to return response")

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
        print(f"           POST data: {request.POST}")
        if self.is_edit_mode():
            return redirect('publications:edit_report_finalize', pk=kwargs['pk'])
        else:
            return redirect('publications:add_report_finalize')



@method_decorator(login_required, name='dispatch')
class ReportFinalizeView(PersonDisambiguationViewProcessorMixin, BaseView):
    """Handles final save of publication"""
    
    def get_form_class(self):
        return DisambiguationWorkflowAddEditReportFinalSaveForm

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
        
        try:
            response = super().post(request, *args, **kwargs)
        except Exception as e:
            print(f"🔍 DEBUG: Error occurred in ReportFinalizeView:post - {e}")
            pass

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
            if isinstance(author_pk, str) and author_pk.startswith('CREATE:'):
                # Skip CREATE: prefixed values - they should have been processed by now
                # If not, log an error:
                print(f"🔍 DEBUG: Found unprocessed CREATE: value in authors: {author_pk}")
                continue
            try:
                person = Person.objects.get(pk=int(author_pk))
                Authorship.objects.create(
                    publication=publication,
                    person=person,
                    author_id=i
                )
            except:
                print(f"🔍 DEBUG: Error creating authorship for person PK {author_pk}, skipping")
        
        # Supervisors  
        publication.supervisorship_set.all().delete()
        for i, supervisor_pk in enumerate(session_data.get('supervisors', [])):
            if isinstance(supervisor_pk, str) and supervisor_pk.startswith('CREATE:'):
                # Skip CREATE: prefixed values - they should have been processed by now
                # If not, log an error:
                print(f"🔍 DEBUG: Found unprocessed CREATE: value in supervisors: {supervisor_pk}")
                continue
            try:
                person = Person.objects.get(pk=int(supervisor_pk))
                Supervisorship.objects.create(
                    publication=publication,
                    person=person,
                    supervisor_id=i
                )
            except:
                print(f"🔍 DEBUG: Error creating supervisorship for person PK {supervisor_pk}, skipping")

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
