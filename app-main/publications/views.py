# === Standard library imports ===
import os
import ast
import datetime
import functools
import json
import logging
import pdb
import re
import shutil
import tempfile
import time
import traceback

# === Django imports ===
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction, IntegrityError
from django.db.models import QuerySet
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
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
    PublicationForm, DeleteReportForm,
    AddFeatureByCoordinatesForm, AddFeatureByMap, PersonWorkflowMixin,
    UploadAppendixForm, ChangeReportNumberForm, FeatureFileUploadForm, FeatureImageUploadForm,
)
from publications.forms.publication import ImportPublicationFileForm
from publications.forms.mixins import WorkflowAddEditReportForm, WorkflowAddEditReportFinalSaveForm
from publications import person_privacy
from publications.person_links import is_marked, marked_links
from publications.library import get_client_ip, is_private
from publications.models import (
    Publication, Topic, Feature, Person, PubType, Authorship, Supervisorship,
    Keyword, FileObject, Appendenciesship, ImageObject, ImageObjectship
)
from publications.permissions import (
    ADD_FEATURE, ADD_PERSON, BULK_DELETE, DELETE, DELETE_FEATURE, EDIT, EDIT_FEATURE, MANAGE,
    MERGE_PERSON, VERIFY, VIEW,
    FeaturePermissionMixin, PermissionMixin, PublicationPermissionMixin,
    ReportFormPermissionMixin, permission_required, user_may,
)
from publications.utils_basic import CaseInsensitively
from publications.geometry import entered_point, single_point, source_origin
from publications.map_styles import selected_type_slugs
from publications import report_delete
from publications.visibility import visible_features, visible_publications
from publications.utils_models import (
    handle_publication_file_upload, create_ordered_queryset, generate_next_report_number,
    handle_session_appendix_uploads, rename_publication_files, get_or_create_keywords,
    FEATURE_FILE, FEATURE_IMAGE, FeatureUploadError, feature_media_dir, handle_feature_uploads,
    image_thumbnail_path, image_thumbnail_url,
)
from publications.workflows.person import (
    DirectoryPersonError, disambiguate_person_step, complete_person_workflow,
    person_from_form_value, person_review_label,
)

logger = logging.getLogger(__name__)

# Fields of an author/supervisor link (Personship) that flag it for a later merge of persons
MATCH_FIELDS = ('exact_match', 'relaxed_match', 'multiple_match', 'match_string')


# --- Add/edit report form: session data -------------------------------------------------
# ReportFormView keeps the submitted form in the session until ReportFinalizeView saves it.
# The data is bound to the form it was entered in ('add' or 'edit:<pk>'), so data entered for
# one report can never be reviewed or saved as another one (plan registration T7).
REPORT_FORM_DATA_KEY = 'form_data'
REPORT_FORM_TARGET_KEY = 'form_data_for'


def report_form_target(pk=None):
    """'add', or 'edit:<pk>' for the edit form of report ``pk``."""
    return 'add' if pk is None else f'edit:{int(pk)}'


def store_report_form_data(session, target, data):
    session[REPORT_FORM_DATA_KEY] = data
    session[REPORT_FORM_TARGET_KEY] = target


def get_report_form_data(session, target):
    """The form data in the session if it was entered in the form ``target``, else None."""
    if session.get(REPORT_FORM_TARGET_KEY) != target:
        return None
    return session.get(REPORT_FORM_DATA_KEY) or None


def clear_report_form_data(session):
    session.pop(REPORT_FORM_DATA_KEY, None)
    session.pop(REPORT_FORM_TARGET_KEY, None)


def _is_checked(value):
    """A checkbox value from the session data (a list from request.POST, or a plain value)."""
    values = value if isinstance(value, (list, tuple)) else [value]
    return any(v in (True, 'true', 'True', 'on', '1') for v in values)


# --- Add/edit report form: files after the commit ---------------------------------------
# ReportFinalizeView changes only database rows inside its transaction and registers these
# functions with transaction.on_commit, so a failed save leaves the files as they were.

def _remove_file(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.exception("Could not remove %s", path)


def _remove_temp_upload(temp_path):
    """Remove a temporary upload and its directory under MEDIA_ROOT/temp/ when empty."""
    _remove_file(temp_path)
    temp_root = os.path.join(settings.MEDIA_ROOT, 'temp')
    directory = os.path.dirname(temp_path)
    if os.path.abspath(os.path.dirname(directory)) == os.path.abspath(temp_root):
        try:
            os.rmdir(directory)
        except OSError:
            pass  # not empty (another upload in the same second) or already gone


def _place_uploaded_report_file(temp_path, final_path, old_path, thumbnail_path):
    """After the commit: put the uploaded PDF at its final path.

    A replaced PDF is kept on disk as ``<old name>.old`` (as before T7; it has no database
    row any more). The thumbnail of the report is removed so that the cron job makes a new
    one. On a file system error the old PDF is put back and the temporary upload is kept;
    the error is logged (the database already points to ``final_path``).
    """
    backup = None
    try:
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        if old_path and os.path.exists(old_path):
            backup = old_path + '.old'
            os.replace(old_path, backup)
        shutil.move(temp_path, final_path)
    except OSError:
        logger.exception("Could not move the uploaded report file %s to %s", temp_path, final_path)
        if backup and not os.path.exists(old_path):
            try:
                os.replace(backup, old_path)
            except OSError:
                logger.exception("Could not restore %s", old_path)
        return
    _remove_temp_upload(temp_path)
    _remove_file(thumbnail_path)


def _report_thumbnail_path(publication):
    """The thumbnail that the generate_thumbnails command makes for the report's PDF."""
    if not (publication.number and publication.year):
        return None
    return os.path.join(settings.MEDIA_ROOT, 'reports', str(publication.year), 'thumbs',
                        f'{publication.number}_thumb.jpg')


def _file_object_path(file_object):
    """Absolute path of a FileObject's file, or None (no file, or a name outside MEDIA_ROOT)."""
    if not file_object or not file_object.file:
        return None
    try:
        return file_object.file.path
    except Exception:  # SuspiciousFileOperation for legacy names outside MEDIA_ROOT
        logger.warning("FileObject %s has a file name outside MEDIA_ROOT", file_object.pk)
        return None


class BaseView(View):
    base_template = "publications/base.html"

    def get_context_data(self, **kwargs):
        # context = super().get_context_data(**kwargs)    # View class has no method get_context_data
        context = {
            'base_template': self.base_template,
            # Other common context variables...
        }
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
            # The type filter's checked types from ?types= (plan "features" T11).
            'selected_feature_types': selected_type_slugs(request.GET),
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
            # The list JS draws the duplicate markers the API sends to these users (FA-R66).
            'can_merge_person': user_may(request.user, MERGE_PERSON),
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



















class ReportView(PublicationPermissionMixin, BaseDetailView):
    """Report page. Shown to those who may see the report (permissions VIEW, the visibility
    rule of FA-R75); hidden reports send anonymous users to the login and are 404 for others."""
    permission = VIEW
    model = Publication
    template_name = 'publications/report.html'
    context_object_name = 'publication'

    def get_object(self, queryset=None):
        return self.publication   # loaded and checked by the mixin

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # The per-feature delete rule looks at the persons listed on the feature's reports.
        associated_features = visible_features(
            Feature.objects.filter(publications=self.object), user,
        ).prefetch_related(
            'publications__authors', 'publications__supervisors', 'publications__editors')
        can_edit_publication = self.object.is_editable_by(user) if user.is_authenticated else False
        can_delete_publication = self.object.is_deletable_by(user) if user.is_authenticated else False
        can_verify_publication = self.object.is_verifiable_by(user) if user.is_authenticated else False
        # Same rules as the views (permissions.py): report number changes are for editors,
        # features may be added by those who may edit the report, and deleted per feature.
        deletable_feature_ids = {
            feature.pk for feature in associated_features
            if user_may(user, DELETE_FEATURE, feature)
        }
        editable_feature_ids = {
            feature.pk for feature in associated_features
            if user_may(user, EDIT_FEATURE, feature)
        }
        # Authors and supervisors as link rows (with the duplicate markers, FA-R66), in the
        # order of the rows: the order publication.authors.all() lists them in on MariaDB.
        authorships = list(self.object.authorship_set.select_related('person').order_by('pk'))
        supervisorships = list(
            self.object.supervisorship_set.select_related('person').order_by('pk'))
        can_merge_person = user_may(user, MERGE_PERSON)
        context.update({
            'authorships': authorships,
            'supervisorships': supervisorships,
            'can_merge_person': can_merge_person,
            'has_person_markers': can_merge_person and any(
                is_marked(link) for link in authorships + supervisorships),
            'can_change_report_number': user_may(user, MANAGE),
            'associated_features': associated_features,
            'can_edit_publication': can_edit_publication,
            'can_delete_publication': can_delete_publication,
            'can_verify_publication': can_verify_publication,
            'can_add_feature': user_may(user, ADD_FEATURE, self.object),
            'deletable_feature_ids': deletable_feature_ids,
            'editable_feature_ids': editable_feature_ids,
        })
        return context


class ReportFormView(ReportFormPermissionMixin, BaseFormView):
    """Unified view for both adding and editing reports.

    Add needs add_publication, edit needs Publication.is_editable_by (permissions.py)."""
    model = Publication
    template_name = 'publications/add_edit_report.html'
    
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

    def get_context_data(self, **kwargs):
        """The template's title, report summary and JS (isEditMode) need the mode and the
        report, as on the review page (ReportReviewView)."""
        context = super().get_context_data(**kwargs)
        context['action'] = 'edit' if self.is_edit_mode() else 'add'
        context['publication'] = self.get_object()   # None in add mode
        return context

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
            'confidential': publication.confidential,
        }

        initial_data['authors'] = [auth.person.pk for auth in publication.authorship_set.all().order_by('author_id')]
        initial_data['supervisors'] = [sup.person.pk for sup in publication.supervisorship_set.all().order_by('supervisor_id')]

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
        """Unified form processing for both Add and Edit with workflow support.

        A form sent by file-upload.js (XMLHttpRequest, a PDF chosen) gets the next page's URL
        as JSON ({"success": true, "redirect": url}) instead of a redirect: the browser would
        follow a redirect inside the request, fetch the next page (the person step asks the DTU
        directory) and then load it a second time when the script goes there."""
        response = self._form_valid(form)
        if (isinstance(response, HttpResponseRedirect)
                and self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
            return JsonResponse({'success': True, 'redirect': response.url})
        return response

    def _form_valid(self, form):
        # FIRST: Always store form data in session
        session_data = self._convert_form_to_session_data(form)
        
        # Handle file uploads
        if 'pdffile' in self.request.FILES:
            uploaded_file = self.request.FILES['pdffile']
            file_obj = handle_publication_file_upload(uploaded_file, user=self.request.user)
            session_data['uploaded_file_id'] = str(file_obj.id)
                
        # Store in session BEFORE any redirects, bound to this form (add, or edit of this pk)
        store_report_form_data(self.request.session, report_form_target(self.kwargs.get('pk')),
                               session_data)

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
                continue
            # Set by form_valid from an upload in this request only, never from the POST
            # (it names the FileObject that finalize moves into the report).
            if key == 'uploaded_file_id':
                continue
            session_data[key] = value
        return session_data



class ReportReviewView(ReportFormPermissionMixin, BaseView):
    """Handles review of form data before final save.

    Same permission as the form (permissions.py), checked before anything else."""
    template_name = 'publications/add_edit_report_review.html'

    def is_edit_mode(self):
        return 'pk' in self.kwargs

    def get_object(self):
        if self.is_edit_mode():
            return get_object_or_404(Publication, pk=self.kwargs['pk'])
        return None

    def _form_redirect(self):
        """No form data in the session for this form: back to the form."""
        if self.is_edit_mode():
            return redirect('publications:edit_report', pk=self.kwargs['pk'])
        return redirect('publications:add_report')

    def _session_form_data(self):
        """The session form data if it was entered in this form (add, or edit of this pk)."""
        return get_report_form_data(self.request.session, report_form_target(self.kwargs.get('pk')))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Pass add/edit state on to the template
        context['action'] = 'edit' if self.is_edit_mode() else 'add'

        # Get the publication object if in edit mode (the permission was checked in dispatch)
        if self.is_edit_mode():
            context['publication'] = self.get_object()
        else:
            context['publication'] = None

        # Get review data from session
        if self._session_form_data() is None:
            context['error'] = "No form data found in session. Please fill out the form first."
            return context
    
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
        session_data = self._session_form_data() or {}
        review_data = {}


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
        # Unchecked checkbox: absent from the POST, so absent from the session data -> False
        review_data['confidential'] = _is_checked(session_data.get('confidential', False))


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
            # A new person or one from the DTU directory: made when the report is saved
            new_label = person_review_label(item_id) if this_model is Person else None
            if new_label is not None:
                items.append(new_label)
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
            
            if 'confidential' in review_data and review_data['confidential'] != obj.confidential:
                changed_fields['confidential'] = True

            # Check file changes - detect any changes in file state
            has_new_file = 'uploaded_file_id' in review_data and review_data['uploaded_file_id'] is not None
            has_delete_request = 'delete_pdf' in review_data and review_data['delete_pdf'] == True
            
            # If we have a file upload or delete request, mark as changed
            if has_new_file or has_delete_request:
                changed_fields['file'] = True
                print(f"🔍 DEBUG: File marked as changed - has_new_file: {has_new_file}, has_delete_request: {has_delete_request}")

        print(f"🔍 DEBUG: ReportReviewView._get_changed_fields - Changed fields identified: {changed_fields}")

        return changed_fields
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests - show the review page"""
        if self._session_form_data() is None:
            return self._form_redirect()

        context = self.get_context_data(**kwargs)

        # Nothing changed in edit mode: back to the report
        if not context['changed_fields'] and self.is_edit_mode():
            return redirect('publications:report', pk=kwargs['pk'])

        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        """A POST to the review page (the template posts to the finalize URL directly) is
        passed on to the finalize step with a 307, so it stays a POST with its CSRF token;
        the finalize step checks the permission again."""
        if self._session_form_data() is None:
            return self._form_redirect()
        if self.is_edit_mode():
            url = reverse('publications:edit_report_finalize', kwargs={'pk': kwargs['pk']})
        else:
            url = reverse('publications:add_report_finalize')
        return HttpResponseRedirect(url, status=307)



class ReportFinalizeView(ReportFormPermissionMixin, BaseView):
    """Handles final save of publication.

    Checks the same permission as the form again (permissions.py), so posting here directly
    without the right to add/edit fails with 403 and saves nothing."""
    
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

    def get(self, request, *args, **kwargs):
        """Nothing is saved by GET: back to the review step (which sends the user on to the
        form when there is no form data in the session)."""
        if self.is_edit_mode():
            return redirect('publications:edit_report_review', pk=kwargs['pk'])
        return redirect('publications:add_report_review')
    
    def _target(self):
        return report_form_target(self.kwargs.get('pk'))

    def _form_redirect(self):
        if self.is_edit_mode():
            return redirect('publications:edit_report', pk=self.kwargs['pk'])
        return redirect('publications:add_report')

    def _review_redirect(self):
        if self.is_edit_mode():
            return redirect('publications:edit_report_review', pk=self.kwargs['pk'])
        return redirect('publications:add_report_review')

    def post(self, request, *args, **kwargs):
        """Save the publication with the session data of this form.

        Only database rows are changed inside the transaction; the files are moved after the
        commit (transaction.on_commit), so a failed save leaves no report, no relations, no
        new keywords and no moved files behind, and the temporary upload stays for a retry.
        """
        # 1. Session data of this form only (add, or edit of this pk)
        session_data = get_report_form_data(request.session, self._target())
        if not session_data:
            if request.session.get(REPORT_FORM_DATA_KEY):
                # Data of another add/edit form: never saved onto this report.
                messages.error(request, 'The data in this session was entered for another report. '
                                        'Please fill in the form again.')
            return self._form_redirect()

        # 2. Rebuild and validate the form from the session data
        form_input = self._session_data_to_form_input(session_data)
        form_kwargs = {'request': request}
        if self.is_edit_mode():
            form_kwargs['instance'] = self.get_object()
        form = self.get_form_class()(form_input, **form_kwargs)
        if not form.is_valid():
            logger.debug("ReportFinalizeView: form invalid in fields %s", sorted(form.errors))
            messages.error(request, 'Form data is invalid. Please check your input.')
            return self._review_redirect()
        if form.has_workflow_redirect():
            # Typed person names that never went through the workflow: resolve them first.
            messages.info(request, 'Please choose who the typed names are before saving.')
            return form.get_workflow_redirect()

        # 3. The uploaded PDF, if any: a temporary upload of this user
        temp_upload = None
        if session_data.get('uploaded_file_id'):
            temp_upload = self._get_temp_upload(session_data['uploaded_file_id'])
            if temp_upload is None:
                messages.error(request, 'The uploaded PDF is no longer available. '
                                        'Please upload it again.')
                return self._form_redirect()

        # 4. Save the database rows; files are moved after the commit
        try:
            with transaction.atomic():
                publication = form.save(commit=False)
                publication.modified_by = request.user
                if not publication.pk:
                    publication.created_by = request.user

                if not self.is_edit_mode() and form_input.get('year'):
                    publication.number = generate_next_report_number(form_input['year'])

                publication.save()
                self._handle_relationships(publication, session_data, form.cleaned_data)
                self._handle_files(publication, session_data, temp_upload)
        except DirectoryPersonError as e:
            # A person chosen from the DTU directory can't be fetched (gone, directory down):
            # nothing saved. No traceback or name in the log: not a server error.
            logger.info("ReportFinalizeView: a person from the DTU directory could not be fetched")
            messages.error(request, f'The report was not saved: {e}')
            return self._review_redirect()
        except Exception as e:
            logger.exception("ReportFinalizeView: saving the report failed")
            messages.error(request, f'Error saving publication: {e}')
            return self._review_redirect()

        clear_report_form_data(request.session)
        return redirect('publications:report', pk=publication.pk)

    def _session_data_to_form_input(self, session_data):
        """Convert session data to form input format"""
        form_input = {}
        for key, value in session_data.items():
            if key in ['authors', 'supervisors', 'publication_topics', 'publication_keywords']:
                form_input[key] = value
            elif key in ('delete_pdf', 'confidential'):
                # Checkboxes: absent when unchecked (BooleanField cleans a missing key to False)
                form_input[key] = _is_checked(value)
            elif isinstance(value, list):
                # If the value is a list, take the first item if it exists
                if value:
                    # take the first item if it exists
                    # there should never be more than one item here
                    form_input[key] = value[0]
                    if len(value) > 1:
                        logger.debug("ReportFinalizeView: several values for %s in the session data, using the first", key)
                else:
                    form_input[key] = None
            else:
                form_input[key] = value
        return form_input

    def _get_temp_upload(self, file_object_id):
        """The temporary upload ``file_object_id`` if it is one (under temp/) of this user."""
        try:
            return FileObject.objects.get(pk=int(file_object_id), file__startswith='temp/',
                                          created_by=self.request.user)
        except (FileObject.DoesNotExist, TypeError, ValueError):
            return None

    def _handle_relationships(self, publication, session_data, cleaned_data):
        """Authors and supervisors (from the session data: pks, and the new persons chosen in
        the person workflow, created here), topics and keywords (from the cleaned form; typed
        keywords that don't exist yet are created here)."""
        created = {}  # new persons of this save by name (author and supervisor: one person)

        # The links are deleted and recreated. A person linked again in the same role keeps
        # the match flags of the old link; a new person gets the flags from its name.
        roles = [
            (publication.authorship_set, Authorship, 'author_id', session_data.get('authors', [])),
            (publication.supervisorship_set, Supervisorship, 'supervisor_id',
             session_data.get('supervisors', [])),
        ]
        for links, model, order_field, values in roles:
            kept = {link.person_id: {field: getattr(link, field) for field in MATCH_FIELDS}
                    for link in links.all()}
            links.all().delete()
            for i, value in enumerate(values):
                person, flags = person_from_form_value(value, self.request.user, created)
                if not flags:
                    flags = kept.get(person.pk, {})
                model.objects.create(publication=publication, person=person,
                                     **{order_field: i}, **flags)

        # Topics: list-only, unknown ones were refused by the form (TopicChoiceField)
        publication.publication_topics.set(cleaned_data.get('publication_topics') or [])

        # Keywords: existing ones and new names (KeywordTagField)
        publication.publication_keywords.set(
            get_or_create_keywords(cleaned_data.get('publication_keywords') or []))

    def _handle_files(self, publication, session_data, temp_upload):
        """Database part of the file changes; the files themselves change after the commit."""
        if temp_upload is not None:
            self._replace_file(publication, temp_upload)
        elif _is_checked(session_data.get('delete_pdf')):
            self._delete_file(publication)

    def _replace_file(self, publication, temp_upload):
        """The upload becomes the report's PDF at reports/<year>/<number>.pdf.

        A new FileObject points to the final name; the old FileObject (if any) and the
        temporary one are deleted. After the commit the old PDF is renamed to ``.old``, the
        upload is moved into place and the temporary file and its directory are removed
        (_place_uploaded_report_file)."""
        old = publication.file
        old_path = _file_object_path(old)
        final_name = self._final_file_name(publication, temp_upload, old)

        final = FileObject.objects.create(
            file=final_name,
            description=temp_upload.description,
            created_by=temp_upload.created_by,
            modified_by=self.request.user,
        )
        publication.file = final
        publication.save(update_fields=['file'])
        if old is not None:
            old.delete()  # nothing points to it any more (Publication.file is CASCADE)

        temp_path = _file_object_path(temp_upload)
        temp_upload.delete()

        transaction.on_commit(functools.partial(
            _place_uploaded_report_file, temp_path, os.path.join(settings.MEDIA_ROOT, final_name),
            old_path, _report_thumbnail_path(publication)))

    def _delete_file(self, publication):
        """Remove the report's PDF: the FileObject now, the file and thumbnail after the commit."""
        old = publication.file
        if old is None:
            return
        old_path = _file_object_path(old)
        publication.file = None
        publication.save(update_fields=['file'])
        old.delete()
        for path in (old_path, _report_thumbnail_path(publication)):
            transaction.on_commit(functools.partial(_remove_file, path))

    def _final_file_name(self, publication, temp_upload, old):
        """reports/<year>/<number><ext>, with _1, _2, ... when the name is taken. The old
        PDF's own name counts as free: it is moved aside after the commit."""
        ext = os.path.splitext(temp_upload.file.name)[1].lower() or '.pdf'
        number = str(publication.number or f'pub_{publication.pk}').replace('/', '_').replace('\\', '_')
        year = str(publication.year) if publication.year else 'unknown_year'
        base = f'reports/{year}/{number}'
        old_name = old.file.name if old is not None and old.file else None

        candidate, counter = f'{base}{ext}', 1
        while candidate != old_name and (
                os.path.exists(os.path.join(settings.MEDIA_ROOT, candidate))
                or FileObject.objects.filter(file=candidate).exists()):
            candidate = f'{base}_{counter}{ext}'
            counter += 1
        return candidate



class _SetVerifiedView(PublicationPermissionMixin, BaseView):
    """Sets Publication.verified; POST only (a GET is 405 and changes nothing), and only
    for users with verify_publication (permissions.py)."""
    permission = VERIFY
    publication_url_kwarg = 'pub_id'
    http_method_names = ['post']
    verified = None
    done = None

    def post(self, request, *args, **kwargs):
        publication = self.publication
        publication.verified = self.verified
        publication.save()
        messages.success(request, f"Report ({publication.id}) '{publication.number}' was {self.done}.")
        return redirect('publications:report', pk=publication.pk)


class VerifyReportView(_SetVerifiedView):
    """Verify a report (it becomes visible to anonymous users)."""
    verified = True
    done = 'verified'


class UnverifyReportView(_SetVerifiedView):
    """Unverify a report (it is hidden from anonymous users again)."""
    verified = False
    done = 'unverified'


class PersonAutocompleteView(View):
    """Person lookup for the select2 author/supervisor widgets of the report form.

    Logged-in users only (FA-R82): anonymous requests get a JSON 403 without person data,
    not a login redirect, because select2 calls this view with XHR.
    """

    re_studynumber = re.compile(r'^s\d{1,6}$')

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'results': [], 'error': 'Login required'}, status=403)

        term = request.GET.get("term", "")
        
        if term:
            # if the string in term starts with 's' followed by 1 to 6 numbers then...
            # Only for logged-in users: id_number is hidden from anonymous users
            # (person_privacy), so they must not look persons up by study number either.
            if (self.re_studynumber.match(term)
                    and person_privacy.can_view_id_number(request.user)):
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
        
        return JsonResponse({"results": results})

















class PersonView(BaseDetailView):
    """Person page. E-mail and ID are passed as ``person_email`` / ``person_id_number``,
    already filtered for the viewer (person_privacy, plan "registration" T13); the
    template must not output ``person.email`` or ``person.id_number`` itself."""
    model = Person
    template_name = 'publications/person.html'
    context_object_name = 'person'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person = self.object
        context['person_email'] = person_privacy.visible_email(self.request.user, person)
        context['person_id_number'] = person_privacy.visible_id_number(self.request.user, person)
        context['show_id_number'] = person_privacy.can_view_id_number(self.request.user)
        context['can_merge_person'] = user_may(self.request.user, MERGE_PERSON)
        if context['can_merge_person']:
            context.update(self.marker_context(person))
        return context

    def marker_context(self, person):
        """The person's marked links for the notice of the person page (FA-R66): all of them
        are counted (confirm clears them all), the reports listed are those the viewer may
        see."""
        links = marked_links(person)
        visible_ids = set(visible_publications(
            Publication.objects.filter(pk__in={link.publication_id for _, link in links}),
            self.request.user).values_list('pk', flat=True))
        shown = [(role, link) for role, link in links if link.publication_id in visible_ids]
        return {
            'marked_link_count': len(links),
            'marked_links': shown,
            'hidden_marked_link_count': len(links) - len(shown),
        }



























































class FeatureView(FeaturePermissionMixin, BaseDetailView):
    """Feature page. Same access as the report page (VIEW); lists only the feature's reports
    the user may see (``visible_reports``)."""
    permission = VIEW
    model = Feature
    template_name = 'publications/feature.html'
    context_object_name = 'feature'

    def get_object(self, queryset=None):
        return self.feature   # loaded and checked by the mixin

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        feature = self.object
        user = self.request.user
        # The WGS84 copy per kind (points, lines, polygons), as stored.
        geometries = [geom for geom in (feature.points, feature.lines, feature.polys)
                      if geom is not None and not geom.empty]
        # The report the page was opened from (``?report=``, a report of this feature the
        # user may see), passed on to the upload and delete links of files and images (T8).
        wanted = self.request.GET.get('report', '')
        request_report = None
        if wanted.isdigit():
            request_report = visible_publications(
                feature.publications.filter(pk=int(wanted)), user).first()
        context.update({
            'files': feature.files.all().order_by('pk'),
            # (image, thumbnail URL or None): thumbnails exist for images uploaded since T8.
            'images': [(image, image_thumbnail_url(image))
                       for image in feature.images.all().order_by('pk')],
            'report_query': f'?report={request_report.pk}' if request_report else '',
            'geometries': geometries,
            # Where the geometry came from (plan "features" T5, design note 8): 'map',
            # 'entered' or 'unknown' (registered before the source fields existed).
            'source_origin': source_origin(feature),
            'visible_reports': visible_publications(
                feature.publications.all(), user).order_by('number', 'pk'),
            # Same rules as the edit and delete views (permissions.py).
            'can_edit_feature': user_may(user, EDIT_FEATURE, feature),
            'can_delete_feature': user_may(user, DELETE_FEATURE, feature),
            # Coordinate edit only for one-point features (T6); others are edited on the map.
            'single_point': single_point(feature) is not None,
        })
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




































# def map_data(request):
#     features = Feature.objects.all()
#     # q: in debug mode, how to loop through features and print out the attributes?
#     # for feature in features:
#     #     print(feature)
#     serialized_features = serializers.serialize('json', features)
#     return JsonResponse(serialized_features, safe=False)


class UploadAppendixView(PublicationPermissionMixin, BaseView):
    """
    View for uploading multiple appendix files to a publication.
    Uses session-based batch management for file handling.
    Only users who may edit the publication can see or use the upload page (FA-R52,
    permissions.py).

    Each file may be up to settings.MAX_UPLOAD_SIZE_MB (UploadAppendixForm).
    """
    template_name = 'publications/upload_appendix.html'
    permission = EDIT

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
        else:
            # Refused files (too large, wrong type, empty): show why on the page we redirect to.
            for error in form.errors.get('appendix_files', []):
                messages.error(request, error)
        
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


# --- Deleting file and image records (appendix delete T9, feature delete T7) -------------
# The record (FileObject, ImageObject) is deleted inside the caller's transaction only when
# nothing uses it any more; its file is removed after the commit (transaction.on_commit),
# and only when no other record names the same file. A missing file is only logged.

def _remove_deleted_media_file(path, kind, pk):
    """After the commit: remove the file of a deleted record. A missing file is not an error."""
    if not os.path.exists(path):
        logger.warning("File of the deleted %s %s was already missing: %s", kind, pk, path)
        return
    _remove_file(path)


def _file_object_is_used(file_object, exclude_feature=None):
    """True if anything still points to ``file_object``: an appendix of any report, a
    report's PDF (Publication.file) or a feature (Feature.files; ``exclude_feature`` not
    counted)."""
    features = Feature.objects.filter(files=file_object)
    if exclude_feature is not None:
        features = features.exclude(pk=exclude_feature.pk)
    return (Appendenciesship.objects.filter(fileobject=file_object).exists()
            or Publication.objects.filter(file=file_object).exists()
            or features.exists())


def _image_object_is_used(image_object, exclude_feature=None):
    """True if a feature (other than ``exclude_feature``) still shows ``image_object``."""
    links = ImageObjectship.objects.filter(imageobject=image_object)
    if exclude_feature is not None:
        links = links.exclude(feature=exclude_feature)
    return links.exists()


def _media_field(record):
    return record.image if isinstance(record, ImageObject) else record.file


def _media_name_shared(record):
    """True if another FileObject or ImageObject names the same file as ``record``."""
    name = _media_field(record).name
    if not name:
        return False
    files = FileObject.objects.filter(file=name)
    images = ImageObject.objects.filter(image=name)
    if isinstance(record, ImageObject):
        images = images.exclude(pk=record.pk)
    else:
        files = files.exclude(pk=record.pk)
    return files.exists() or images.exists()


def _delete_media_record(record, kind):
    """Delete ``record`` (a FileObject or ImageObject nothing uses any more; the caller
    checks) inside the current transaction, and remove its file after the commit unless
    another record names the same file. ``kind`` names the record in the log. An image's
    thumbnail (features T8, utils_models.make_image_thumbnail) goes with its file."""
    pk = record.pk
    field = _media_field(record)
    path = None
    if field:
        try:
            path = field.path
        except Exception:  # SuspiciousFileOperation for legacy names outside MEDIA_ROOT
            logger.warning("%s %s has a file name outside MEDIA_ROOT", kind, pk)
    shared = _media_name_shared(record)
    thumbnail = image_thumbnail_path(record) if isinstance(record, ImageObject) else None
    record.delete()
    if path is None:
        logger.warning("Deleted %s %s had no file under MEDIA_ROOT", kind, pk)
    elif not shared:
        transaction.on_commit(functools.partial(_remove_deleted_media_file, path, kind, pk))
        if thumbnail:
            # Most images (all from before T8) have no thumbnail: no warning when missing.
            transaction.on_commit(functools.partial(_remove_file, thumbnail))


def _delete_feature(feature):
    """Delete ``feature`` with its files and images (plan "features" T7, design note 5).

    Call inside transaction.atomic(). Files and images that another feature, a report's PDF
    or an appendix still uses keep their record and file; the others are deleted, and their
    files are removed after the commit (_delete_media_record)."""
    files = list(feature.files.all())
    images = list(feature.images.all())
    feature.delete()   # also its rows in the M2M tables (files, ImageObjectship, reports)
    for file_object in files:
        if not _file_object_is_used(file_object):
            _delete_media_record(file_object, 'feature FileObject')
    for image_object in images:
        if not _image_object_is_used(image_object):
            _delete_media_record(image_object, 'feature ImageObject')


class DeleteAppendixView(PublicationPermissionMixin, BaseView):
    """Delete one appendix of a report (roadmap FA-R104, plan features T9).

    Same rule as the upload (``edit``: Publication.is_editable_by; permissions.py). GET shows
    the confirmation page, POST deletes. 404 if the file is not an appendix of this report.

    The link between the report and the file is always removed. The FileObject is deleted
    only when nothing else uses it (an appendix of another report, a report's PDF, a
    feature's files); its file on disk is removed after the commit, unless another FileObject
    names the same file. A file that is already missing is only logged.
    """
    template_name = 'publications/appendix_confirm_delete.html'
    permission = EDIT
    http_method_names = ['get', 'post']

    def get_appendix(self):
        file_pk = self.kwargs['file_pk']
        if not Appendenciesship.objects.filter(
                publication=self.publication, fileobject_id=file_pk).exists():
            raise Http404("No such appendix of this report.")
        return get_object_or_404(FileObject, pk=file_pk)

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        context.update({'publication': self.publication, 'appendix': self.get_appendix()})
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        publication = self.publication
        appendix = self.get_appendix()
        filename = appendix.filename() if appendix.file else f'file {appendix.pk}'
        with transaction.atomic():
            Appendenciesship.objects.filter(publication=publication, fileobject=appendix).delete()
            if not _file_object_is_used(appendix):
                _delete_media_record(appendix, 'appendix FileObject')
        messages.success(request, f'Appendix "{filename}" was deleted from report '
                                  f'{publication.number or publication.pk}.')
        return redirect('publications:report', pk=publication.pk)


class ChangeReportNumberView(PublicationPermissionMixin, BaseFormView):
    """
    View for changing an existing report's number with file renaming.

    For editors only (``manage``: change_publication; permissions.py).
    """
    template_name = 'publications/change_report_number.html'
    permission = MANAGE

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
        publication = self.get_object()
        old_number = publication.number
        new_number = form.cleaned_data['new_number']
        try:
            with transaction.atomic():
                rename_results = rename_publication_files(publication, old_number, new_number)
                if not rename_results['success']:
                    for error in rename_results['errors']:
                        messages.error(self.request, f"File renaming error: {error}")
                    return self.form_invalid(form)
                publication.number = new_number
                publication.modified_by = self.request.user
                publication.save(update_fields=['number', 'modified_by'])
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
            logger.exception("Changing the number of publication %s failed", publication.pk)
            messages.error(
                self.request,
                f"Error changing report number: {str(e)}"
            )
            return self.form_invalid(form)


class FeatureReturnReportMixin:
    """The report an edit of ``self.feature`` returns to (plan "features" T5, T6).

    ``report`` (query string on GET, hidden field on POST) names the report to return to; it
    counts only if it is a report of this feature the user may see. Otherwise the feature's
    first visible report, else the feature page."""

    def return_report(self):
        if not hasattr(self, '_return_report'):
            reports = visible_publications(
                self.feature.publications.all(), self.request.user).order_by('number', 'pk')
            wanted = self.request.POST.get('report') or self.request.GET.get('report')
            report = None
            if wanted and str(wanted).isdigit():
                report = reports.filter(pk=int(wanted)).first()
            self._return_report = report or reports.first()
        return self._return_report

    def return_url(self):
        report = self.return_report()
        if report is not None:
            return reverse('publications:report', kwargs={'pk': report.pk})
        return reverse('publications:feature', kwargs={'pk': self.feature.pk})


class FeatureCoordinatesFormMixin:
    """Add or edit a one-point feature by its coordinates (plan "features" T6).

    The form (``AddFeatureByCoordinatesForm``) builds and checks the point with
    publications.geometry. Hard errors re-render the form. Warnings (outside Greenland,
    values that look swapped, ...) lead to a confirm page that carries all values in hidden
    fields: "Save anyway" posts them again with ``confirm_warnings=1`` and saves; "Back to the
    form" (``back=1``) shows the form with the values. Nothing is saved before the
    confirmation. The subclass gives ``created`` and ``finish(feature)``."""
    template_name = 'publications/add_feature_coordinates.html'
    confirm_template_name = 'publications/feature_coordinates_confirm.html'
    form_class = AddFeatureByCoordinatesForm
    created = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'editing': not self.created,
            'srid_help_list': AddFeatureByCoordinatesForm.srid_help_list,
            'cancel_url': self.cancel_url(),
        })
        return context

    def form_valid(self, form):
        if self.request.POST.get('back'):
            return self.render_to_response(self.get_context_data(form=form))
        if form.coordinate_warnings and self.request.POST.get('confirm_warnings') != '1':
            return TemplateResponse(self.request, self.confirm_template_name,
                                    self.get_context_data(form=form))
        feature = form.save(commit=False)
        if self.created:
            feature.created_by = self.request.user
        feature.modified_by = self.request.user
        feature.save()
        form.save_m2m()
        return self.finish(feature, form)

    def warning_messages(self, form):
        for warning in form.coordinate_warnings:
            messages.warning(self.request, f'Saved with a warning: {warning}')


class AddFeatureCoordinatesView(PublicationPermissionMixin, FeatureCoordinatesFormMixin,
                                BaseFormView):
    """Add a point feature to a report by its coordinates.

    Needs ``add_feature`` on the report (add_feature and may edit it; permissions.py). The
    mixin sets ``self.publication``. Back to the report after saving or cancelling."""
    permission = ADD_FEATURE
    publication_url_kwarg = 'report_pk'
    created = True

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault('spatial_reference_system', '4326')
        return initial

    def cancel_url(self):
        return reverse('publications:report', kwargs={'pk': self.publication.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['publication'] = self.publication
        return context

    def finish(self, feature, form):
        feature.publications.add(self.publication)
        messages.success(self.request, f'Feature "{feature.name}" added to report '
                                       f'{self.publication.number}.')
        self.warning_messages(form)
        return redirect('publications:report', pk=self.publication.pk)


class EditFeatureCoordinatesView(FeaturePermissionMixin, FeatureReturnReportMixin,
                                 FeatureCoordinatesFormMixin, BaseFormView):
    """Edit a one-point feature by its coordinates (and its attributes).

    Needs ``edit_feature`` (Feature.is_editable_by; permissions.py). Only for features that
    hold exactly one point and no line or polygon (``geometry.single_point``); others are
    redirected to the map edit. The form starts with the coordinates as entered
    (``source_srid``/``source_geometry``), else EPSG:4326 from ``points``. Back to the report
    named by ``report`` (FeatureReturnReportMixin)."""
    permission = EDIT_FEATURE
    created = False

    def map_edit_redirect(self):
        url = reverse('publications:edit_feature_by_map', kwargs={'pk': self.feature.pk})
        report = self.return_report()
        if report is not None:
            url = f'{url}?report={report.pk}'
        return HttpResponseRedirect(url)

    def get(self, request, *args, **kwargs):
        if single_point(self.feature) is None:
            return self.map_edit_redirect()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if single_point(self.feature) is None:
            return self.map_edit_redirect()
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        srid, x, y = entered_point(self.feature)
        initial.update({'spatial_reference_system': str(srid), 'x_coordinate': x,
                        'y_coordinate': y})
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.feature
        return kwargs

    def cancel_url(self):
        return self.return_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'feature': self.feature, 'return_report': self.return_report()})
        return context

    def finish(self, feature, form):
        if form.geometry_changed:
            messages.success(self.request, f'Feature "{feature.name}" saved with the new '
                                           'coordinates.')
        else:
            messages.success(self.request, f'Feature "{feature.name}" saved (coordinates '
                                           'unchanged).')
        self.warning_messages(form)
        return HttpResponseRedirect(self.return_url())


class FeatureMapFormMixin:
    """Add or edit a feature by drawing on the map (plan "features" T5): the shared map
    component in edit mode (find-artek-map-edit.js) fills the form's ``geojson_data``;
    ``AddFeatureByMap`` checks it with publications.geometry and decides whether the geometry
    changed. Warnings of the geometry check (e.g. outside Greenland) become messages."""
    template_name = 'publications/add_feature_by_map.html'
    form_class = AddFeatureByMap

    def save_feature(self, form, created):
        feature = form.save(commit=False)
        if created:
            feature.created_by = self.request.user
        feature.modified_by = self.request.user
        feature.save()
        form.save_m2m()
        return feature

    def add_geometry_messages(self, form):
        for warning in form.geometry_warnings:
            messages.warning(self.request, warning)

    def form_invalid(self, form):
        messages.error(
            self.request,
            'There was a problem with your feature data. '
            'Please correct the errors below and try again.'
        )
        return super().form_invalid(form)


class AddFeatureByMapView(PublicationPermissionMixin, FeatureMapFormMixin, FormView):
    """Add a feature to a report by drawing it on the map.

    Needs ``add_feature`` on the report (add_feature and may edit it; permissions.py).
    The mixin sets ``self.publication``. Back to the report after saving or cancelling."""
    permission = ADD_FEATURE
    publication_url_kwarg = 'report_pk'

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault('pos_quality', 'Approximate')   # drawn on the map
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'publication': self.publication,
            'editing': False,
            'map_publication': self.publication,
            'cancel_url': reverse('publications:report', kwargs={'pk': self.publication.pk}),
        })
        return context

    def form_valid(self, form):
        feature = self.save_feature(form, created=True)
        feature.publications.add(self.publication)
        messages.success(self.request, f'Feature "{feature.name}" added to report '
                                       f'{self.publication.number}.')
        self.add_geometry_messages(form)
        return redirect('publications:report', pk=self.publication.pk)


class EditFeatureByMapView(FeaturePermissionMixin, FeatureReturnReportMixin,
                           FeatureMapFormMixin, FormView):
    """Edit a feature's attributes and geometry on the map.

    Needs ``edit_feature`` (Feature.is_editable_by; permissions.py). The report to return to
    comes from ``report`` (FeatureReturnReportMixin)."""
    permission = EDIT_FEATURE

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.feature
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.return_report()
        context.update({
            'feature': self.feature,
            'editing': True,
            'return_report': report,
            'map_publication': report,
            'cancel_url': self.return_url(),
        })
        return context

    def form_valid(self, form):
        feature = self.save_feature(form, created=False)
        messages.success(self.request, f'Feature "{feature.name}" saved.')
        self.add_geometry_messages(form)
        return HttpResponseRedirect(self.return_url())


class DeleteReportView(PublicationPermissionMixin, BaseView):
    """View for deleting a publication and all its associated files.

    Needs Publication.is_deletable_by (delete_publication, or delete_own_publication and
    own; permissions.py). This replaces the old rule "superuser, creator or
    delete_publication" (plan registration, permission matrix).

    A report that still has features cannot be deleted (owner 2026-11-23, plan "features"
    T13): deleting it would leave its features in the database, without a report, still on
    the map. GET then shows no delete button but the report's features and the two ways to
    remove them ("Delete all features", DeleteReportFeaturesView, or one by one from the
    report page); POST changes nothing and returns to the report with an error. Only this
    report's own features are listed, never the other reports they may belong to."""
    template_name = 'publications/delete_report_form.html'
    permission = DELETE
    
    def get_publication(self):
        """Get the publication to be deleted"""
        pk = self.kwargs.get('pk')
        return get_object_or_404(Publication, pk=pk)

    @staticmethod
    def report_features(publication):
        """The features linked to ``publication`` (all of them: the user may see this report,
        so they may see its features), sorted by name (report_delete.report_features)."""
        return report_delete.report_features(publication)

    @staticmethod
    def features_block_message(publication, count):
        number = report_delete.report_label(publication)
        return (f'Report {number} cannot be deleted: it still has {count} feature(s). '
                f'Delete its features first ("Delete all features" or one by one on the '
                f'report page), then delete the report.')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        publication = self.get_publication()
        features = list(self.report_features(publication))
        context.update({
            'publication': publication,
            'report_features': features,
            'can_delete_all_features': bool(features) and user_may(
                self.request.user, ADD_FEATURE, publication),
        })
        return context
    
    def get(self, request, *args, **kwargs):
        """Display the delete confirmation page"""
        context = self.get_context_data()
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle the delete or cancel action"""
        publication = self.get_publication()
        
        action = request.POST.get('action')
        
        if action == 'cancel':
            # Redirect back to the publication detail page
            return redirect('publications:report', pk=publication.pk)
        
        elif action == 'delete':
            count = self.report_features(publication).count()
            if count:
                # Blocked (T13): nothing is changed while the report has features.
                messages.error(request, self.features_block_message(publication, count))
                return redirect('publications:report', pk=publication.pk)
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


class DeleteFeatureView(FeaturePermissionMixin, FeatureReturnReportMixin, BaseView):
    """Delete one feature with its files and images (plan "features" T7).

    Needs ``delete_feature`` on the feature (delete_feature, or delete_own_feature and
    listed on a report the feature belongs to; permissions.py). GET shows the confirmation
    page (the feature, its files and images, the reports it is linked to) and changes
    nothing; POST deletes in one transaction (_delete_feature; files are removed after the
    commit). Returns to the report named by ``report`` (FeatureReturnReportMixin), else the
    feature's first visible report, else the report list.

    A feature linked to more than one report cannot be deleted (owner 2026-11-23, plan
    "features" T7a; long term roadmap FA-R109): GET explains it and offers no delete, POST
    changes nothing and returns with an error. "Delete all features" of a report
    (DeleteReportFeaturesView) only removes such a feature from that report.
    """
    template_name = 'publications/feature_confirm_delete.html'
    permission = DELETE_FEATURE
    http_method_names = ['get', 'post']

    def success_url(self):
        report = self.return_report()
        if report is not None:
            return reverse('publications:report', kwargs={'pk': report.pk})
        return reverse('publications:reports')

    def get(self, request, *args, **kwargs):
        feature = self.feature
        # Only reports the user may see; hidden (confidential/unvalidated) reports are not
        # named or counted (CLAUDE.md: confidential reports stay protected).
        visible = list(visible_publications(
            feature.publications.all(), request.user).order_by('number', 'pk'))
        context = self.get_context_data()
        context.update({
            'feature': feature,
            # (record, kept): kept when another feature, report PDF or appendix uses it.
            'files': [(f, _file_object_is_used(f, exclude_feature=feature))
                      for f in feature.files.all().order_by('pk')],
            'images': [(i, _image_object_is_used(i, exclude_feature=feature))
                       for i in feature.images.all().order_by('pk')],
            'reports': visible,
            'shared': self.is_shared(),
            'return_report': self.return_report(),
            'cancel_url': self.return_url(),
        })
        return render(request, self.template_name, context)

    def is_shared(self):
        """True if the feature is linked to more than one report (hidden ones count too)."""
        return self.feature.publications.count() > 1

    def post(self, request, *args, **kwargs):
        feature = self.feature
        name = feature.name or f'feature {feature.pk}'
        if self.is_shared():
            messages.error(request, f'Feature "{name}" belongs to more than one report and '
                                    'cannot be deleted. "Delete all features" on a report '
                                    'removes it from that report only.')
            return HttpResponseRedirect(self.return_url())
        success_url = self.success_url()   # before the links to the reports are gone
        with transaction.atomic():
            _delete_feature(feature)
        messages.success(request, f'Feature "{name}" was deleted.')
        return HttpResponseRedirect(success_url)


class FeatureMediaReturnMixin(FeatureReturnReportMixin):
    """Upload and delete of a feature's files and images (plan "features" T8) return to the
    feature page, which lists them, with ``?report=`` of the report the action started from
    (FeatureReturnReportMixin: a report of the feature the user may see, else the feature's
    first visible report), so the next upload uses the same report folder."""

    def feature_url(self):
        url = reverse('publications:feature', kwargs={'pk': self.feature.pk})
        report = self.return_report()
        return f'{url}?report={report.pk}' if report is not None else url


class UploadFeatureMediaView(FeaturePermissionMixin, FeatureMediaReturnMixin, BaseView):
    """Upload files or images to a feature (plan "features" T8, roadmap FA-R64).

    Needs ``edit_feature`` (Feature.is_editable_by; permissions.py). GET shows the page with
    one form for files and one for images; POST with ``kind`` = ``file`` or ``image`` stores
    the uploaded files (utils_models.handle_feature_uploads) under
    ``reports/<year>/<number>/features/<feature id>/`` (images in ``img/``) of the report named
    by ``report`` (query string / hidden field; else the feature's first visible report) and
    returns to the feature page. A feature without such a report gets no uploads (message).
    Same limit per file as appendices (settings.MAX_UPLOAD_SIZE_MB) and the submit guard.
    """
    template_name = 'publications/feature_upload.html'
    permission = EDIT_FEATURE
    http_method_names = ['get', 'post']

    def render_page(self, file_form=None, image_form=None, status=200):
        report = self.return_report()
        try:
            folder = feature_media_dir(self.feature, report)
            folder_error = None
        except FeatureUploadError as error:
            folder, folder_error = None, str(error)
        context = self.get_context_data()
        context.update({
            'feature': self.feature,
            'return_report': report,
            'folder': folder,
            'folder_error': folder_error,
            'file_form': file_form or FeatureFileUploadForm(),
            'image_form': image_form or FeatureImageUploadForm(),
            'cancel_url': self.feature_url(),
        })
        return render(self.request, self.template_name, context, status=status)

    def get(self, request, *args, **kwargs):
        return self.render_page()

    def post(self, request, *args, **kwargs):
        kind = request.POST.get('kind')
        if kind == FEATURE_IMAGE:
            form = FeatureImageUploadForm(request.POST, request.FILES)
            files_field, text_field, form_kwargs = 'feature_images', 'caption', {'image_form': form}
        elif kind == FEATURE_FILE:
            form = FeatureFileUploadForm(request.POST, request.FILES)
            files_field, text_field, form_kwargs = 'feature_files', 'description', {'file_form': form}
        else:
            messages.error(request, 'Choose files or images to upload.')
            return self.render_page(status=400)
        if not form.is_valid():
            return self.render_page(status=400, **form_kwargs)
        try:
            records = handle_feature_uploads(
                self.feature, self.return_report(), form.cleaned_data[files_field],
                request.user, kind, form.cleaned_data.get(text_field, ''))
        except FeatureUploadError as error:
            messages.error(request, str(error))
            return self.render_page(status=400, **form_kwargs)
        label = 'image' if kind == FEATURE_IMAGE else 'file'
        messages.success(request, f'{len(records)} {label}(s) added to feature '
                                  f'"{self.feature.name or self.feature.pk}".')
        return HttpResponseRedirect(self.feature_url())


class DeleteFeatureMediaView(FeaturePermissionMixin, FeatureMediaReturnMixin, BaseView):
    """Delete one file or image of a feature (plan "features" T8; ``kind`` set in urls.py).

    Needs ``edit_feature`` (as the upload). GET shows the confirmation page, POST deletes.
    404 if the record is not linked to this feature. The link to the feature is always
    removed; the record is deleted only when nothing else uses it (another feature, a
    report's PDF or appendix; _file_object_is_used / _image_object_is_used), and its file
    (and an image's thumbnail) is removed after the commit unless another record names the
    same file (_delete_media_record, as the feature delete T7 and the appendix delete T9).
    Returns to the feature page.
    """
    template_name = 'publications/feature_media_confirm_delete.html'
    permission = EDIT_FEATURE
    http_method_names = ['get', 'post']
    kind = FEATURE_FILE

    def get_record(self):
        record_pk = self.kwargs['record_pk']
        if self.kind == FEATURE_IMAGE:
            if not ImageObjectship.objects.filter(
                    feature=self.feature, imageobject_id=record_pk).exists():
                raise Http404("No such image of this feature.")
            return get_object_or_404(ImageObject, pk=record_pk)
        if not self.feature.files.filter(pk=record_pk).exists():
            raise Http404("No such file of this feature.")
        return get_object_or_404(FileObject, pk=record_pk)

    def is_used_elsewhere(self, record):
        if self.kind == FEATURE_IMAGE:
            return _image_object_is_used(record, exclude_feature=self.feature)
        return _file_object_is_used(record, exclude_feature=self.feature)

    def get(self, request, *args, **kwargs):
        record = self.get_record()
        context = self.get_context_data()
        context.update({
            'feature': self.feature,
            'record': record,
            'kind': self.kind,
            'kept': self.is_used_elsewhere(record),
            'thumbnail_url': (image_thumbnail_url(record) if self.kind == FEATURE_IMAGE
                              else None),
            'return_report': self.return_report(),
            'cancel_url': self.feature_url(),
        })
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        feature = self.feature
        record = self.get_record()
        name = record.filename() if _media_field(record) else f'{self.kind} {record.pk}'
        with transaction.atomic():
            if self.kind == FEATURE_IMAGE:
                ImageObjectship.objects.filter(feature=feature, imageobject=record).delete()
                if not _image_object_is_used(record):
                    _delete_media_record(record, 'feature ImageObject')
            else:
                feature.files.remove(record)
                if not _file_object_is_used(record):
                    _delete_media_record(record, 'feature FileObject')
        label = 'Image' if self.kind == FEATURE_IMAGE else 'File'
        messages.success(request, f'{label} "{name}" was removed from feature '
                                  f'"{feature.name or feature.pk}".')
        return HttpResponseRedirect(self.feature_url())


class DeleteReportFeaturesView(PublicationPermissionMixin, BaseView):
    """Delete all features of a report (plan "features" T7, design note 3).

    Needs ``add_feature`` on the report (add_feature and may edit it; permissions.py). Per
    feature of the report:

    - linked to other reports too: only unlinked from this report. That needs no more than
      ``add_feature`` here, since the feature stays as it is on the other reports;
    - linked only to this report: deleted with its files and images (_delete_feature) if the
      user has ``delete_feature`` on it, else kept (named on the page and in the message).

    GET shows the three lists and changes nothing. POST acts in one transaction on the
    features the confirmation page listed (hidden fields ``delete`` and ``unlink``) that are
    still in the same group, so a feature added or changed meanwhile is left alone. Files
    are removed after the commit. Returns to the report.
    """
    template_name = 'publications/report_features_confirm_delete.html'
    permission = ADD_FEATURE
    http_method_names = ['get', 'post']

    def classify(self):
        """(to_delete, to_unlink, kept): the report's features, each sorted by name."""
        report = self.publication
        user = self.request.user
        features = (Feature.objects.filter(publications=report).distinct()
                    .order_by('name', 'pk')
                    .prefetch_related('publications__authors', 'publications__supervisors',
                                      'publications__editors'))
        to_delete, to_unlink, kept = [], [], []
        for feature in features:
            if any(p.pk != report.pk for p in feature.publications.all()):
                to_unlink.append(feature)
            elif user_may(user, DELETE_FEATURE, feature):
                to_delete.append(feature)
            else:
                kept.append(feature)
        return to_delete, to_unlink, kept

    def get(self, request, *args, **kwargs):
        to_delete, to_unlink, kept = self.classify()
        context = self.get_context_data()
        context.update({
            'publication': self.publication,
            'to_delete': to_delete,
            'to_unlink': to_unlink,
            'kept': kept,
        })
        return render(request, self.template_name, context)

    @staticmethod
    def _posted_ids(request, name):
        return {int(v) for v in request.POST.getlist(name) if str(v).isdigit()}

    def post(self, request, *args, **kwargs):
        report = self.publication
        confirmed_delete = self._posted_ids(request, 'delete')
        confirmed_unlink = self._posted_ids(request, 'unlink')
        with transaction.atomic():
            to_delete, to_unlink, kept = self.classify()
            deleted = [f for f in to_delete if f.pk in confirmed_delete]
            unlinked = [f for f in to_unlink if f.pk in confirmed_unlink]
            for feature in unlinked:
                feature.publications.remove(report)
            for feature in deleted:
                _delete_feature(feature)
        number = report.number or report.pk
        if deleted or unlinked:
            parts = []
            if deleted:
                parts.append(f'{len(deleted)} feature(s) deleted')
            if unlinked:
                parts.append(f'{len(unlinked)} feature(s) that belong to other reports too '
                             f'removed from this report')
            messages.success(request, f'Report {number}: ' + '; '.join(parts) + '.')
        else:
            messages.info(request, f'Report {number}: no feature was deleted or removed.')
        if kept:
            names = ', '.join(f'"{f.name or f.pk}"' for f in kept)
            messages.warning(request, f'{len(kept)} feature(s) kept, you may not delete them: '
                                      f'{names}.')
        return redirect('publications:report', pk=report.pk)


# AJAX: add a person from the report form

@require_http_methods(["POST"])
@permission_required(ADD_PERSON, json_response=True)
def add_person_ajax(request):
    """
    AJAX endpoint to create new persons.
    Based on legacy add_person_ajax view.

    Needs add_person (permissions.py): anonymous gets a JSON 401, a user without the
    permission a JSON 403.
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
        
        # Person has no 'name' attribute (the name is split into its parts on creation)
        person_name = person.get_full_name()
        return JsonResponse({
            'success': f'Person "{person_name}" created successfully with ID {person.id}',
            'person_id': person.id,
            'person_name': person_name
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Failed to create person: {str(e)}'
        }, status=500)



class AddReportsFromFileUploadView(PermissionMixin, BaseFormView):
    """Excel import of reports, for editors only (``manage``: change_publication;
    permissions.py).

    The uploaded file is written to a temporary file for the parser and removed after
    parsing, also when parsing fails."""
    template_name = "publications/add_reports_from_file_upload.html"
    form_class = ImportPublicationFileForm
    permission = MANAGE

    def form_valid(self, form):
        uploaded_file = form.cleaned_data["file"]
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
            file_path = temp_file.name
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
        try:
            filemessages = xlsx_pubs(file_path, user=self.request.user)
        except Exception:
            logger.exception("Excel import: the uploaded file could not be read")
            filemessages = [(messages.ERROR,
                             "The file could not be read as an Excel report list; nothing was imported.")]
        finally:
            try:
                os.unlink(file_path)
            except OSError:
                logger.warning("Excel import: could not remove the temporary file %s", file_path)
        for level, msg in filemessages:
            messages.add_message(self.request, level, msg)

        # Redirect back to the same page to show messages
        return redirect("publications:add_reports_from_file_upload")

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)



class BulkDeletePublicationsView(PermissionMixin, View):
    """Bulk delete, for editors only (``bulk_delete``: delete_publication; permissions.py).

    Reports that still have features are never deleted (plan "features" T13,
    publications.report_delete): the confirm page lists them apart ("has N features, delete
    them first", with a link to the report's delete page) and does not count them; on the
    confirmed POST they are skipped (nothing about them changes) and named in an error
    message, the others are deleted as before."""
    template_name = 'publications/bulk_delete_publications.html'
    permission = BULK_DELETE

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

        # If confirm flag is present, perform deletion (reports with features are skipped, T13)
        if request.POST.get('confirm') == 'yes':
            with transaction.atomic():
                deletable, blocked = report_delete.split_by_features(
                    Publication.objects.filter(pk__in=selected_ids).order_by('-year', '-number', 'pk'))
                count = len(deletable)
                if deletable:
                    Publication.objects.filter(pk__in=[p.pk for p in deletable]).delete()
            if blocked:
                names = ', '.join(
                    f'{report_delete.report_label(p)} ({p.feature_count} feature(s))'
                    for p in blocked)
                messages.error(request, f'Not deleted, {len(blocked)} report(s) still have '
                                        f'features (delete their features first): {names}.')
            if count:
                messages.success(request, f'Deleted {count} publication(s).')
            return redirect('publications:bulk_delete_publications')

        # Otherwise, render confirmation
        deletable, blocked = report_delete.split_by_features(
            Publication.objects.filter(pk__in=selected_ids)
            .order_by('-year', '-number', 'pk').prefetch_related('authors'))
        context = {
            'confirm': True,
            'publications_to_delete': deletable,
            'blocked_publications': blocked,
            'count': len(deletable),
            'selected_ids': selected_ids,
        }
        return render(request, self.template_name, context)