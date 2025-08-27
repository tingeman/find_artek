# === Standard library imports ===
import re


# === Django imports ===

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods

# === Project-specific imports ===
from find_artek.search import get_query
from publications.forms import (
    AuthorSelectForm, SupervisorSelectForm,
)

#from publications.forms.mixins import WorkflowAddEditReportForm, WorkflowAddEditReportFinalSaveForm
from publications.models import (
    Person,
)

from publications.views.base_views import BaseView, BaseDetailView

# TODO: Change to use NameNormalizer
from publications.utils_basic import get_tag




class PersonsView(BaseView):
    template_name = 'publications/persons.html'

    def get(self, request, **kwargs):
        
        person_list = Person.objects.all().order_by('last', 'first')  # .order_by('-year').order_by('number')

        context = {
            'pers_list': person_list,
        }

        context.update(self.get_context_data(**kwargs))

        return render(request, self.template_name, context)


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


# TODO: I think this may be redundant, as we have a similar function in the api/person_ajax_views.py

# @require_http_methods(["GET"])
# @login_required
# def check_person_ajax(request):
#     """
#     AJAX endpoint to check person names and provide disambiguation options.
#     Based on legacy check_person_ajax view.
#     """
#     if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#         return JsonResponse({'error': 'AJAX requests only'}, status=400)
    
#     def process_field(field_name):
#         """Process a field (authors, supervisors, etc.) and return disambiguation data"""
#         persons_needing_choice = []
        
#         for name in request.GET.getlist(f'{field_name}[]'):
#             if not name.strip():
#                 continue
                
#             # Check if name has an ID tag
#             person_id = get_tag(name, 'id')
            
#             if person_id == 0:
#                 # Person marked for creation - no disambiguation needed
#                 continue
#             elif person_id and person_id != 'ldap':
#                 # Existing person ID - verify it exists
#                 try:
#                     Person.objects.get(id=person_id)
#                     continue  # Valid existing person
#                 except Person.DoesNotExist:
#                     # Invalid ID, treat as new name
#                     pass
            
#             # No valid ID tag, need to check for matches
#             matches, match_type = get_person_matches(name)
            
#             if match_type:
#                 # Found matches - need user choice
#                 person_data = {
#                     'name': name,
#                     'p_exact': list(matches) if match_type == 'db_exact' else [],
#                     'p_relaxed': list(matches) if match_type == 'db_relaxed' else [],
#                     'p_ldap': []  # LDAP not implemented in modern version
#                 }
#                 persons_needing_choice.append(person_data)
#             else:
#                 # No matches - will create new person
#                 person_data = {
#                     'name': name,
#                     'p_exact': [],
#                     'p_relaxed': [],
#                     'p_ldap': []
#                 }
#                 persons_needing_choice.append(person_data)
        
#         if persons_needing_choice:
#             # Render disambiguation form
#             context = {
#                 'name_field': field_name,
#                 'persons': persons_needing_choice
#             }
#             html = render_to_string(
#                 'publications/ajax/choose_person_form.html',
#                 {'data': context},
#                 request=request
#             )
#             return {'html': html, 'message': 'choice_needed'}
#         else:
#             # All persons are valid
#             return {'html': '', 'message': 'ok'}
    
#     response = {}
    
#     # Process each field type
#     if 'authors[]' in request.GET:
#         response['authors'] = process_field('authors')
#     if 'supervisors[]' in request.GET:
#         response['supervisors'] = process_field('supervisors')
#     if 'editors[]' in request.GET:
#         response['editors'] = process_field('editors')
    
#     if not response:
#         return JsonResponse({'error': 'No person fields specified'}, status=400)
    
#     return JsonResponse(response)


# TODO: I think this may be redundant, as we have a similar function in the api/person_ajax_views.py

# @require_http_methods(["POST"])
# @login_required
# def add_person_ajax(request):
#     """
#     AJAX endpoint to create new persons.
#     Based on legacy add_person_ajax view.
#     """
#     if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#         return JsonResponse({'error': 'AJAX requests only'}, status=400)
    
#     # Simple person creation - just name required
#     name = request.POST.get('name', '').strip()
#     if not name:
#         return JsonResponse({'error': 'Name is required'}, status=400)
    
#     try:
#         person = Person.objects.create(
#             name=name,
#             created_by=request.user,
#             modified_by=request.user
#         )
        
#         return JsonResponse({
#             'success': f'Person "{person.name}" created successfully with ID {person.id}',
#             'person_id': person.id,
#             'person_name': person.name
#         })
#     except Exception as e:
#         return JsonResponse({
#             'error': f'Failed to create person: {str(e)}'
#         }, status=500)


