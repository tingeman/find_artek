import re
import json

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
from publications.forms import (LoginForm, AddReportForm, AddReportFinalSaveForm, 
                                EditReportForm, EditReportFinalSaveForm,
                                PublicationForm, AuthorSelectForm, SupervisorSelectForm)
from publications.models import Publication, Topic, Feature, Person

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

        context.update({'associated_features': associated_features})
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
        """Return appropriate form class based on operation mode"""
        if self.is_edit_mode():
            return EditReportForm if not self.is_final_save() else EditReportFinalSaveForm
        else:
            return AddReportForm if not self.is_final_save() else AddReportFinalSaveForm

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
            context['pub'] = self.get_object()
        
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
        
        # Prepare authors as string list for select2 widget
        authors = publication.authorship_set.all().order_by('author_id')
        if authors:
            author_list = [str(auth.person.pk) for auth in authors]
            initial_data['authors'] = str(author_list)
        
        # Prepare supervisors as string list for select2 widget  
        supervisors = publication.supervisorship_set.all().order_by('supervisor_id')
        if supervisors:
            supervisor_list = [str(sup.person.pk) for sup in supervisors]
            initial_data['supervisors'] = str(supervisor_list)
            
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
        authors = session_data.get('authors', [])
        supervisors = session_data.get('supervisors', [])
        
        if not self.is_edit_mode() or session_data:
            # Format authors and supervisors for prepopulation
            form.fields['authors'].widget.choices = self._get_person_choices(authors)
            form.fields['supervisors'].widget.choices = self._get_person_choices(supervisors)
        elif self.is_edit_mode():
            # Get current authors and supervisors from publication
            publication = self.get_object()
            if publication:
                authors = [str(auth.person.pk) for auth in publication.authorship_set.all().order_by('author_id')]
                supervisors = [str(sup.person.pk) for sup in publication.supervisorship_set.all().order_by('supervisor_id')]
                form.fields['authors'].widget.choices = self._get_person_choices(authors)
                form.fields['supervisors'].widget.choices = self._get_person_choices(supervisors)
        
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
            return self._handle_regular_get(request)

    def _handle_regular_get(self, request):
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
            return self.form_valid(form)
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

        # Save publication
        self.object = form.save(commit=False)
        self.object.save()

        # Handle file operations
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

        return super().form_valid(form)

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

