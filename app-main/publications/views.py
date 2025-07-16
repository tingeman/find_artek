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
class AddReportView(BaseFormView):
    model = Publication
    form_class = AddReportForm    # PublicationForm
    template_name = 'publications/add_edit_report.html'
    select_persons_url = 'select-persons'

    def __init__(self, *args, **kwargs):
        print('In AddReportView:__init__')
        super().__init__(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = self.request.GET.get('action', 'new')
        # if self.object:
        #     context['associated_features'] = self.object.feature_set.all()
        return context

    def get_initial(self):
        # Check the 'action' query parameter
        action = self.request.GET.get('action', 'new')  # Default to new form, if no action is given

        if action == 'edit':
            # Prefill the form with existing session data
            session_data = self.request.session.get('add_report_form_data', {})
            
            # Normalize session data for form initialization
            normalized_data = {}
            for key, value in session_data.items():
                if isinstance(value, list) and len(value) == 1:
                    # Convert single-item lists to a string
                    normalized_data[key] = value[0]
                else:
                    # Keep multi-value fields as lists
                    normalized_data[key] = value

            print(f"AddReportView:get_initial: normalized data: {normalized_data}")
            return normalized_data
        else:
            # Default to an empty form if action is unrecognized
            return {}

    def get_form(self):
        # Get the form instance
        form = super().get_form()

        # Retrieve session data for authors and supervisors
        session_data = self.request.session.get('add_report_form_data', {})
        authors = session_data.get('authors', [])
        supervisors = session_data.get('supervisors', [])   
      
        # Format authors for prepopulation
        choices = self.get_person_choices(authors)
        print(f"AddReportView:get_form: author choices: {choices}")
        form.fields['authors'].widget.choices = choices

        # Format supervisors for prepopulation
        choices = self.get_person_choices(supervisors)
        print(f"AddReportView:get_form: supervisor choices: {choices}")
        form.fields['supervisors'].widget.choices = choices

        return form

    def get_person_choices(self, persons=[]):
        choices = []
        for person in persons:
            if isinstance(person, int) or (isinstance(person, str) and person.isnumeric()):  # Existing person (ID)
                # Fetch the name from the database
                person = Person.objects.filter(pk=int(person)).first()
                if person:
                    choices.append((person.pk, str(person)))
            elif isinstance(person, str):  # New person (name)
                choices.append((person, person))
        return choices
    
    def get(self, request, *args, **kwargs):
        action = request.GET.get('action', 'new') # Default to new form, if no action is given
        if action == 'new':
            # Clear session data to start fresh
            request.session.pop('add_report_form_data', None)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        print(f"AddReportView:post: {request.POST}")
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        print(f"AddReportView:form_valid: Form contains the following data: {form.cleaned_data}")

        if not form.instance.pk:
            form.instance.created_by = self.request.user
        form.instance.modified_by = self.request.user

        # session_data = self.request.session.get('add_report_form_data', {})
        # authors = session_data.get('authors', [])
        # supervisors = session_data.get('supervisors', [])   
        authors = form.cleaned_data['authors']
        supervisors = form.cleaned_data['supervisors']

        if (not isinstance(authors, QuerySet)) or (not isinstance(supervisors, QuerySet)):
            # the authors or supervisors field is not a queryset, so one of them must contain person names not already in the database
            # store all the form data in the session and redirect to the author/supervisor selection page
            raw_data = dict(self.request.POST.lists())
            self.request.session['add_report_form_data'] = raw_data
            print(f"AddReportView:form_valid: raw data: {raw_data}")
            print(f"AddReportView:form_valid: redirecting to {self.select_persons_url}")
            return redirect(self.select_persons_url)

        # Otherwise, save publication normally
        self.object = form.save(commit=False)
        self.object.save()
        
        # Handle file upload if present
        uploaded_file = form.cleaned_data.get('pdffile')
        if uploaded_file:
            file_obj = handle_publication_file_upload(self.object, uploaded_file)
            self.object.file = file_obj
            self.object.save()
        
        # Handle authors - preserve order using author_id
        self.object.authorship_set.all().delete()
        for i, author in enumerate(authors):
            from publications.models import Authorship
            Authorship.objects.create(
                publication=self.object, 
                person=author, 
                author_id=i
            )
            
        # Handle supervisors - preserve order using supervisor_id
        self.object.supervisorship_set.all().delete()  
        for i, supervisor in enumerate(supervisors):
            from publications.models import Supervisorship
            Supervisorship.objects.create(
                publication=self.object, 
                person=supervisor, 
                supervisor_id=i
            )
            
        return super().form_valid(form)    
           
    def get_success_url(self):
        return reverse('report', kwargs={'pk': self.object.pk})



@method_decorator(login_required, name='dispatch')
class PersonSelectView(BaseView):
    template_name = 'publications/persons_select.html'
    
    def __init__(self, *args, **kwargs):
        print('In PersonSelectView:__init__')
        super().__init__(*args, **kwargs)

    def get(self, request):
        print('In PersonSelectView:get')
        
        session_data = self.request.session.get('add_report_form_data', {})
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
            'supervisors_form': supervisors_form
        })

    def post(self, request):
        print(f"PersonSelectView:post: request.post data: {request.POST}")

        session_data = self.request.session.get('add_report_form_data', {})
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
            print(f"personSelectView:post: supervisors_form cleaned data: {supervisors_form.cleaned_data}")
            selected_supervisors = []
            for key, value in supervisors_form.cleaned_data.items():
                if key.startswith("supervisor_"):
                    if value == 'create_new':
                        print(f"  - Create new supervisor: {key}: {value}")
                        # Create a new Person instance
                        name = supervisors[int(key.split('_')[1])]
                        person = Person.objects.create(name=name)
                        selected_authors.append(person.pk)
                        print(f"  - created new supervisor: {person}")
                    else:
                        # Use the selected Person primary key
                        print(f"Select existing supervisor: {key}: {value}")
                        selected_supervisors.append(int(value))

            # Update the session with the selected author primary keys
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
        self.request.session['add_report_form_data'] = session_data
        self.request.session.modified = True

        print(f"PersonSelectView:post: session data: {self.request.session.get('add_report_form_data')}")

        if author_form_valid and supervisor_form_valid:
            #raise Exception("Not implemented yet")  # Redirect to finalize publication save
            print(f"PersonSelectView:post: redirecting to publication_final_save")
            return redirect('publication_final_save')  # Redirect to finalize publication save
        else:
            print(f"PersonSelectView:post: forms are invalid, redirecting back to select_persons")
            return render(request, self.template_name, {
                'authors_form': authors_form,
                'supervisors_form': supervisors_form
            })
          


@method_decorator(login_required, name='dispatch')
class AddReportFinalSaveView(BaseFormView):
    model = Publication
    form_class = AddReportFinalSaveForm  
    template_name = None
    select_persons_url = 'select-persons'
    add_report_url = 'add_report'
        
    def __init__(self, *args, **kwargs):
        print('In AddReportFinalSaveView:__init__')
        super().__init__(*args, **kwargs)

    # def get_initial(self):
    #     print('In AddReportFinalSaveView:get_initial')
    #     # Prefill the form with existing session data
    #     session_data = self.request.session.get('add_report_form_data', {})
        
    #     print(f"AddReportFinalSaveView:get_initial: session data: {session_data}")

    #     # Normalize session data for form initialization
    #     normalized_data = {}
    #     for key, value in session_data.items():
    #         if isinstance(value, list) and len(value) == 1:
    #             # Convert single-item lists to a string
    #             normalized_data[key] = value[0]
    #         else:
    #             # Keep multi-value fields as lists
    #             normalized_data[key] = value

    #     print(f"AddReportFinalSaveView:get_initial: normalized data: {normalized_data}")
    #     return normalized_data

    def get_normalized_data(self):
        print('In AddReportFinalSaveView:get_normalized_data')
        # Prefill the form with existing session data
        session_data = self.request.session.get('add_report_form_data', {})
        
        print(f"AddReportFinalSaveView:get_normalized_data: session data: {session_data}")

        # Normalize session data for form initialization
        normalized_data = {}
        for key, value in session_data.items():
            if isinstance(value, list) and len(value) == 1:
                # Convert single-item lists to a string
                normalized_data[key] = value[0]
            else:
                # Keep multi-value fields as lists
                normalized_data[key] = value

        print(f"AddReportFinalSaveView:get_normalized_data: normalized data: {normalized_data}")
        return normalized_data


    def get_form(self):
        print('In AddReportFinalSaveView:get_form')
        
        # Get the form instance
        self.request.method = 'POST'  # pretend that this is a POST request
        self.request.POST = self.get_normalized_data()  # add the session data as if it were posted from the form
        #pdb.set_trace()
        form = super().get_form()

        # # Retrieve session data for authors and supervisors
        # session_data = self.request.session.get('add_report_form_data', {})
        # authors = session_data.get('authors', [])
        # supervisors = session_data.get('supervisors', [])   
      
        # # Format authors for prepopulation
        # choices = self.get_person_choices(authors)
        # print(f"AddReportView:get_form: author choices: {choices}")
        # form.fields['authors'].widget.choices = choices

        # # Format supervisors for prepopulation
        # choices = self.get_person_choices(supervisors)
        # print(f"AddReportView:get_form: supervisor choices: {choices}")
        # form.fields['supervisors'].widget.choices = choices

        return form

    # def get_person_choices(self, persons=[]):
    #     choices = []
    #     for person in persons:
    #         if isinstance(person, int) or (isinstance(person, str) and person.isnumeric()):  # Existing person (ID)
    #             # Fetch the name from the database
    #             person = Person.objects.filter(pk=int(person)).first()
    #             if person:
    #                 choices.append((person.pk, str(person)))
    #         elif isinstance(person, str):  # New person (name)
    #             choices.append((person, person))
    #     return choices

    def get(self, request, *args, **kwargs):
        print('In AddReportFinalSaveView:get')
        # Redirect to a different view if accessed without proper session data
        if not request.session.get('add_report_form_data', {}):
            # redirect to add_report view
            return redirect('add_report')
        
        form = self.get_form()
        #print(f"AddReportFinalSaveView:get: form: {form}")
        print(f"AddReportFinalSaveView:get: form initial: {form.initial}")
        print(f"AddReportFinalSaveView:get: form data: {form.data}")

        if form.is_valid():
            # Call form_valid directly since there's no actual form submission in GET
            print(f"AddReportFinalSaveView:get: form is valid")
            return self.form_valid(form)
        else:
            print(f"AddReportFinalSaveView:get: form is not valid, redirecting to {self.add_report_url}")
            print(f"AddReportFinalSaveView:get: form is bound?: {form.is_bound}")
            print(f"AddReportFinalSaveView:get: form errors: {form.errors}")
            print(f"AddReportFinalSaveView:get: form non_field_errors: {form.non_field_errors()}")
            redirect('add_report')

    def form_valid(self, form):
        print(f"AddReportFinalSaveView:form_valid: Form contains the following data: {form.cleaned_data}")

        if not form.instance.pk:
            form.instance.created_by = self.request.user
        form.instance.modified_by = self.request.user

        authors = form.cleaned_data['authors']
        supervisors = form.cleaned_data['supervisors']

        if (not isinstance(authors, QuerySet)) or (not isinstance(supervisors, QuerySet)):
            # the authors or supervisors field is not a queryset, so one of them must contain person names not already in the database
            # store all the form data in the session and redirect to the author/supervisor selection page
            raw_data = dict(self.request.POST.lists())
            self.request.session['add_report_form_data'] = raw_data
            print(f"AddReportFinalSaveView:form_valid: raw data: {raw_data}")
            print(f"AddReportFinalSaveView:form_valid: redirecting to {self.select_persons_url}")
            return redirect(self.select_persons_url)
        else:
            print(f"AddReportFinalSaveView:form_valid: authors and supervisors are QuerySets")

        # Otherwise, save publication normally
        self.object = form.save(commit=False)
        self.object.save()
        print(f"AddReportFinalSaveView:form_valid: authors: {authors}")
        
        # Handle file upload if present
        uploaded_file = form.cleaned_data.get('pdffile')
        if uploaded_file:
            file_obj = handle_publication_file_upload(self.object, uploaded_file)
            self.object.file = file_obj
            self.object.save()
            print(f"AddReportFinalSaveView:form_valid: PDF file uploaded and saved")
        
        # Handle authors - preserve order using author_id
        self.object.authorship_set.all().delete()
        for i, author in enumerate(authors):
            from publications.models import Authorship
            Authorship.objects.create(
                publication=self.object, 
                person=author, 
                author_id=i
            )
            
        print(f"AddReportFinalSaveView:form_valid: supervisors: {supervisors}")
        
        # Handle supervisors - preserve order using supervisor_id
        self.object.supervisorship_set.all().delete()  
        for i, supervisor in enumerate(supervisors):
            from publications.models import Supervisorship
            Supervisorship.objects.create(
                publication=self.object, 
                person=supervisor, 
                supervisor_id=i
            )
            
        print(f"AddReportFinalSaveView:form_valid: publication saved")
        return super().form_valid(form)    
           
    def get_success_url(self):
        print('In AddReportFinalSaveView:get_success_url')
        return reverse('report', kwargs={'pk': self.object.pk})



          





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

