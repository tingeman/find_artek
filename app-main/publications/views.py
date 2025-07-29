import re
import json
import os

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template import RequestContext
from django.core import serializers
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.views import View
from django.urls import reverse
from django.db.models import QuerySet

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
                                AddFeatureCoordinatesForm)
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
            return AddEditReportFinalSaveForm
        else:
            return AddEditReportForm

    def is_edit_mode(self):
        """Check if we're in edit mode (has pk in URL)"""
        return 'pk' in self.kwargs

    def is_final_save(self):
        """Check if this is a final save after person selection"""
        action = self.request.GET.get('action', '')
        return action in ['add_final', 'edit_final']

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
        """Get initial data for Edit mode"""
        action = self.request.GET.get('action', 'edit')
        
        if action == 'edit_continue':  # Returning from person selection
            session_data = self.request.session.get('edit_report_form_data', {})
            return self._normalize_session_data(session_data)
        
        # Build initial data from the publication
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
        # Pretend this is a POST request with session data
        self.request.method = 'POST'
        session_key = self.get_session_key()
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
                return redirect('reports')
            else:
                return redirect('add_report')
        
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
                    return redirect('edit_report', pk=publication_id)
                return redirect('reports')
            else:
                return redirect('add_report')

    def form_valid(self, form):
        """Unified form processing for both Add and Edit"""
        print(f"AddEditReportView:form_valid: Form contains data: {form.cleaned_data}")
        
        # Set user information
        if not form.instance.pk:
            form.instance.created_by = self.request.user
        form.instance.modified_by = self.request.user

        authors = form.cleaned_data['authors']
        supervisors = form.cleaned_data['supervisors']

        # Handle person selection redirect if needed
        if (not isinstance(authors, QuerySet)) or (not isinstance(supervisors, QuerySet)):
            return self._handle_person_selection_redirect(form)

        # Save publication (without files yet)
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
                            return redirect('add_report')
            else:
                from django.contrib import messages
                messages.error(self.request, "Cannot create report without a year")
                return redirect('add_report')
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

        # Always return a redirect to the success URL
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())

    def _handle_person_selection_redirect(self, form):
        """Handle redirect to person selection"""
        raw_data = dict(self.request.POST.lists())
        session_key = self.get_session_key()
        self.request.session[session_key] = raw_data
        
        if self.is_edit_mode():
            obj = self.get_object()
            if obj:
                self.request.session['edit_report_publication_id'] = obj.pk
            
        action = 'edit' if self.is_edit_mode() else 'add'
        print(f"AddEditReportView: redirecting to {self.select_persons_url}?action={action}")
        return redirect(f"{self.select_persons_url}?action={action}")

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

    def get_success_url(self):
        return reverse('report', kwargs={'pk': self.object.pk})



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
                'redirect_url': 'edit_report_final_save',
                'action': 'edit'
            }
        else:
            return {
                'session_key': 'add_report_form_data', 
                'redirect_url': 'publication_final_save',
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
        return redirect('frontpage')






























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
        
        return redirect('upload_appendix', pk=publication.id)
    
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
        
        return redirect('upload_appendix', pk=publication.id)
    
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
            return redirect('report', pk=publication.id)
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error processing files: {e}')
            return redirect('upload_appendix', pk=publication.id)
    
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
        return redirect('report', pk=publication.id)


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
                
                return redirect('report', pk=publication.pk)
                
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
            return redirect('report', pk=publication.pk)
            
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
        return reverse('report', kwargs={'pk': self.kwargs['report_pk']})


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
            return redirect('report', pk=publication.pk)
        
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
                return redirect('reports')
                
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error deleting publication: {str(e)}')
                return redirect('report', pk=publication.pk)
        
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
            return reverse_lazy('report', kwargs={'pk': pubs.first().pk})
        return reverse_lazy('reports')

    def get_context_data(self, **kwargs):
        # Ensure self.object is set before using it
        if not hasattr(self, 'object') or self.object is None:
            self.object = self.get_object()
        context = super().get_context_data(**kwargs)
        # Ensure base_template is always present
        context['base_template'] = getattr(self, 'base_template', 'publications/base.html')
        pubs = self.object.publications.all()
        if pubs.exists():
            context['cancel_url'] = reverse_lazy('report', kwargs={'pk': pubs.first().pk})
        else:
            context['cancel_url'] = reverse_lazy('reports')
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