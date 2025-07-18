from django import forms
from django.forms import ModelForm
from django.contrib.admin.widgets import AdminFileWidget
from django_select2 import forms as s2forms
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from publications.models import Publication, Person, Feature, Topic, Keyword
from publications.utils import create_ordered_queryset
from django.urls import reverse
import datetime
import ast
import json


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class PersonHeavySelect2TagWidget(s2forms.HeavySelect2TagWidget):

    def __init__(self, *args, initial_data=None, **kwargs):
        """
        Extend the widget to accept initial_data during initialization.
        """
        print(f"PersonHeavySelect2TagWidget:__init__: {initial_data}")
        self.initial_data = initial_data or []
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        """Get the context for rendering the widget.
        This method is overridden to ensure that the entire contents of the Person table is not
        rendered as options in the select2 widget. The 'optgroups' key is set to an empty list.
        """
        context = super().get_context(name, value, attrs)
        #context['widget']['optgroups'] = []
        return context

    def value_new(self, value):
        """Handle creation of new Person objects."""
        print(f'In PersonHeavySelect2TagWidget:value_new: {value}')
        # names = value.split()
        # first = names[0]
        # last = names[-1] if len(names) > 1 else ""
        # middle = " ".join(names[1:-1]) if len(names) > 2 else ""
        # return Person.objects.create(first=first, middle=middle, last=last).pk
        return 9999


class AddEditReportForm(ModelForm):
    """A unified form for both adding and editing reports
    
    Automatically adapts behavior based on whether an instance is provided:
    - When instance=None: Adding mode (number field editable, no delete_pdf option)
    - When instance provided: Editing mode (number field readonly, delete_pdf option available)
    """
    
    # Class variable for file size limit (in MB)
    MAX_FILE_SIZE_MB = 300

    year = forms.IntegerField(
        initial=datetime.datetime.now().year,
        widget=forms.NumberInput(attrs={
            'min': 1900,
            'max': datetime.datetime.now().year,
            'placeholder': 'Enter year'
        })
    )

    authors = forms.CharField(max_length=1000, required=False,
        widget=PersonHeavySelect2TagWidget(
            data_view="person-autocomplete",
            attrs={"data-token-separators": "['&',';']",
                    "data-tags": "true",   # enable tagging
                    "data-placeholder": "Add or select authors (separate by semicolon (;) or &-sign)",
                    "data-minimum-input-length": 3,
                    "style": "width: 50em;",
                    "data-initial": "",  # Will be dynamically populated by the view
            }, 
        ),
    )

    supervisors = forms.CharField(max_length=1000, required=False,
        widget=PersonHeavySelect2TagWidget(
            data_view="person-autocomplete",
            attrs={"data-token-separators": "['&',';']",
                    "data-tags": "true",   # enable tagging
                    "data-placeholder": "Add or select supervisors (separate by semicolon (;) or &-sign)",
                    "data-minimum-input-length": 3,
                    "style": "width: 50em;",
            }, 
        ),
    )

    publication_topics = forms.ModelMultipleChoiceField(
        queryset=Topic.objects.all(),
        required=False,
        widget=s2forms.Select2TagWidget(
            attrs={
                "data-tags": "true",  # Enable tagging
                "data-token-separators": "[',', ';']",
                "data-placeholder": "Add or select topics (separate by comma or enter)",
                "data-minimum-input-length": 0,
                "style": "width: 100%;",  # Optional: Set widget width
            }
        ),
    )

    publication_keywords = forms.ModelMultipleChoiceField(
        queryset=Keyword.objects.all(),
        required=False,
        widget=s2forms.Select2TagWidget(
            attrs={
                "data-tags": "true",  # Enable tagging
                "data-token-separators": "[',', ';']",
                "data-placeholder": "Add or select keywords (separated by comma or enter)",
                "data-minimum-input-length": 0,
                "style": "width: 100%;",  # Optional: Set widget width
            }
        ),
    )

    # pdffile = forms.FileField(
    #     required=False, 
    #     allow_empty_file=True,
    #     #help_text='Select file to upload',
    #     widget=AdminFileWidget
    # )
    
    pdffile = forms.FileField(
        required=False,
        help_text='Upload PDF file for this report',  # Will be updated in __init__
        widget=forms.FileInput(attrs={
            'accept': '.pdf',
            'class': 'file-upload-input',
            'id': 'pdf-upload'
        })
    )

    # Field for deleting existing PDF files (only shown in edit mode)
    delete_pdf = forms.BooleanField(
        required=False,
        label="Delete existing PDF file",
        help_text="Check this box to delete the current PDF file"
    )

    class Meta:
        model = Publication
        # Include all fields including delete_pdf for edit mode
        fields = ['type', 'title', 'number', 'year', 'abstract', 'comment',
                  'authors', 'supervisors', 'publication_topics', 'publication_keywords', 'pdffile', 'delete_pdf']
        exclude = []

    def __init__(self, *args, **kwargs):
        print('In AddEditReportForm:__init__')
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        # Set dynamic help text using class variable
        self.fields['pdffile'].help_text = f'Upload PDF file for this report (max {self.MAX_FILE_SIZE_MB}MB)'

        print(f'AddEditReportForm:__init__: delete_pdf field before configuration: widget={type(self.fields["delete_pdf"].widget).__name__}')

        if instance:
            # EDIT MODE: Configure form for editing existing publication
            print(f'AddEditReportForm:__init__:EDIT MODE - instance: {instance}')
            print(f'AddEditReportForm:__init__:EDIT MODE - instance.file: {instance.file}')
            
            # Make the number field read-only for editing
            self.fields['number'].widget.attrs['readonly'] = True
            self.fields['number'].help_text = "Report number cannot be changed when editing"
            
            # Configure PDF-related fields based on whether there's an existing file
            if instance.file:
                current_file_name = instance.file.file.name.split('/')[-1] if instance.file.file else "Unknown file"
                self.fields['pdffile'].help_text = f'Current file: {current_file_name}. Upload a new PDF to replace it (max {self.MAX_FILE_SIZE_MB}MB)'
                
                # Show the delete_pdf option since there's an existing file
                # Explicitly set widget to ensure it's visible
                self.fields['delete_pdf'].widget = forms.CheckboxInput(attrs={'class': 'delete-pdf-checkbox'})
                self.fields['delete_pdf'].help_text = f"Check this box to delete the current PDF file ({current_file_name})"
                
                print(f'AddEditReportForm:__init__:EDIT MODE - Configured delete_pdf field for existing file: {current_file_name}')
            else:
                # No existing file, hide the delete option
                self.fields['delete_pdf'].widget = forms.HiddenInput()
                self.fields['pdffile'].help_text = f'Upload PDF file for this report (max {self.MAX_FILE_SIZE_MB}MB)'
                
                print('AddEditReportForm:__init__:EDIT MODE - No existing file, hiding delete_pdf field')
            
            # Restrict the queryset to authors already associated with this publication
            self.fields['authors'].widget.queryset = instance.authors.all()
            self.fields['supervisors'].widget.queryset = instance.supervisors.all()
        else:
            # ADD MODE: Configure form for adding new publication
            print('AddEditReportForm:__init__:ADD MODE - No instance')
            
            # Hide the delete_pdf field in add mode since there's no existing file
            self.fields['delete_pdf'].widget = forms.HiddenInput()
            
            # For a new publication, no authors are pre-selected
            self.fields['authors'].widget.queryset = Person.objects.none()
            self.fields['supervisors'].widget.queryset = Person.objects.none()

        print(f'AddEditReportForm:__init__: delete_pdf field after configuration: widget={type(self.fields["delete_pdf"].widget).__name__}')

    def clean_authors(self):
        print(f"AddEditReportForm:clean_authors: {self.cleaned_data['authors']}")
        authors_data = self.cleaned_data['authors']  # This will be a comma-separated list of author primary keys or author names

        if authors_data:
            # author_data is a string of the type "['1001', '996', 'Anders And']"
            # Parse the string into a list of strings
            parsed_authors = ast.literal_eval(authors_data)
            
            # If the authors field is empty, return an empty list
            if not parsed_authors:
                print('AddEditReportForm:clean_authors:No authors')
                return Person.objects.none()

            print(f'AddEditReportForm:clean_authors:parsed_authors: {parsed_authors}')

            # check if parsed_authors is a string or an integer
            if isinstance(parsed_authors, (int, str)):
                print('AddEditReportForm:clean_authors:parsed_authors is a string or an integer')
                parsed_authors = [parsed_authors]   # Convert to list

            # if all entries are numeric, assume they are primary keys
            if all([str(c).isnumeric() for c in parsed_authors]):
                print('AddEditReportForm:clean_authors:All numeric')
                author_pks = [int(pk) for pk in parsed_authors]
                # Create an ordered QuerySet to preserve the original logic
                return create_ordered_queryset(Person, author_pks)
            else:
                print('AddEditReportForm:clean_authors:Not all numeric')
                return parsed_authors
        else:
            print('AddEditReportForm:clean_authors:No authors')
            return Person.objects.none()

    def clean_supervisors(self):
        print(f"AddEditReportForm:clean_supervisors: {self.cleaned_data['supervisors']}")
        supervisors_data = self.cleaned_data['supervisors']  # This will be a comma-separated list of supervisor primary keys or supervisor names

        if supervisors_data:
            # supervisor_data is a string of the type "['1001', '996', 'Anders And']"
            # Parse the string into a list of strings
            parsed_supervisors = ast.literal_eval(supervisors_data)
            
            # If the supervisors field is empty, return an empty list
            if not parsed_supervisors:
                print('AddEditReportForm:clean_supervisors:No supervisors')
                return Person.objects.none()

            print(f'AddEditReportForm:clean_supervisors:parsed_supervisors: {parsed_supervisors}')

            # check if parsed_supervisors is a string or an integer
            if isinstance(parsed_supervisors, (int, str)):
                print('AddEditReportForm:clean_supervisors:parsed_supervisors is a string or an integer')
                parsed_supervisors = [parsed_supervisors]   # Convert to list

            # if all entries are numeric, assume they are primary keys
            if all([str(c).isnumeric() for c in parsed_supervisors]):
                print('AddEditReportForm:clean_supervisors:All numeric')
                supervisor_pks = [int(pk) for pk in parsed_supervisors]
                # Create an ordered QuerySet to preserve the original logic
                return create_ordered_queryset(Person, supervisor_pks)
            else:
                print('AddEditReportForm:clean_supervisors:Not all numeric')
                return parsed_supervisors
        else:
            print('AddEditReportForm:clean_supervisors:No supervisors')
            return Person.objects.none()

    def parse_name(self, full_name):
        """
        Splits a full name into first, middle, and last components.
        Adjust this logic based on your requirements.
        """
        parts = full_name.split()
        first_name = parts[0]
        middle_name = ' '.join(parts[1:-1]) if len(parts) > 2 else None
        last_name = parts[-1] if len(parts) > 1 else None
        return first_name, middle_name, last_name
    
    def is_valid(self):
        print('In AddEditReportForm:is_valid')
        return super().is_valid()
    
    def clean_pdffile(self):
        """Validate the uploaded PDF file"""
        uploaded_file = self.cleaned_data.get('pdffile')
        
        if uploaded_file:
            # Check file type
            if not uploaded_file.name.lower().endswith('.pdf'):
                raise ValidationError('Only PDF files are allowed.')
            
            # Check file size using class variable
            max_size = self.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB to bytes
            if uploaded_file.size > max_size:
                raise ValidationError(f'File size cannot exceed {self.MAX_FILE_SIZE_MB}MB.')
        
        return uploaded_file
    
    def clean_number(self):
        """Prevent number from being changed in edit mode"""
        if self.instance and self.instance.pk:
            # In edit mode, always return the original number
            return self.instance.number
        # In add mode, return the cleaned data
        return self.cleaned_data.get('number')
    
    # def save(self, full_name):
    #     # instance = super().save(commit=False)
    #     # instance.save()
    #     # self.cleaned_data['authors'] = instance.authors.set(self.cleaned_data['authors'])
    #     # return instance
    #     pass


class AddEditReportFinalSaveForm(AddEditReportForm):
    """Final save form that ensures authors and supervisors are QuerySet instances
    
    Used when processing person selections from the person select view.
    Validates that authors and supervisors have been converted from names to QuerySet objects.
    """
    
    def clean_authors(self):
        result = super().clean_authors()
        if not isinstance(result, QuerySet):
            raise ValidationError("Authors must be a QuerySet instance")
        return result

    def clean_supervisors(self):
        result = super().clean_supervisors()
        if not isinstance(result, QuerySet):
            raise ValidationError("Supervisors must be a QuerySet instance")
        return result


# Keep AddReportForm as an alias for backward compatibility
AddReportForm = AddEditReportForm
    





#     def __init__(self, *args, **kwargs):
#         # Call the parents initialization method
#         super(AddReportForm, self).__init__(*args, **kwargs)  # Call to ModelForm constructor

#         # Set the size of the number input field
#         try:
#             self.fields['number'].widget.attrs['size'] = 5
#         except:
#             pass

#         if 'instance' in kwargs and kwargs['instance']:
#             # A model instance was passed, we are editing an existing model...

#             # parse authors and post in textfield
#             p = kwargs['instance']

#             # Populate author list
#             a_set = p.authorship_set.all().order_by('author_id')
#             if a_set:
#                 a_list = [a.person.__unicode__() +
#                             ' [id:{0}]'.format(a.person.id) \
#                             for a in a_set]
#             else:
#                 a_list = []
#             #self.fields['authors'].initial = '\n'.join(a_list)
#             self.initial['authors'] = '\n'.join(a_list)

#             # Populate supervisor list
#             s_set = p.supervisorship_set.all().order_by('supervisor_id')
#             if s_set:
#                 s_list = [s.person.__unicode__() +
#                             ' [id:{0}]'.format(s.person.id) \
#                             for s in s_set]
#             else:
#                 s_list = []
#             #self.fields['supervisors'].initial = '\n'.join(s_list)
#             self.initial['supervisors'] = '\n'.join(s_list)


#             #pdb.set_trace()

#             # populate keywords field
#             #self.fields['keywords'].initial = [k.keyword for k in p.keywords.all()]
#             self.initial['keywords'] = [k.keyword for k in p.keywords.all()]

#             # populate topic field
#             #self.fields['topic'].initial = [k.topic for k in p.topics.all()]
#             self.initial['topics'] = [k.topic for k in p.topics.all()]

#             # populate pdffile field
#             if p.file:
#                 #self.fields['pdffile'].initial = p.file.file
#                 self.initial['pdffile'] = p.file.file



# class UserAddReportForm(AddReportForm):
#     """A Form handling the adding or editing of reports when accessed by
#     a normal user (not superuser)

#     """
#     class Meta:
#         model = Publication
#         # Only show the following fields
#         fields = ['type', 'title', 'year', 'abstract', 'comment',
#                   'authors', 'supervisors', 'topics', 'keywords', 'pdffile']






class PersonSelectForm(forms.Form):
    # An abstract class intended for subclassing
    class Meta:
        abstract = True

    person_type = None   # Define in subclass as "author" or "supervisor"

    def __init__(self, *args, persons=None, **kwargs):
        super().__init__(*args, **kwargs)

        if persons is not None:
            # Add a headline in the form, it should be pure text and not a field
            for i, person in enumerate(persons):
                if str(person).isnumeric():  # Assume it's a primary key, this formulation works with both int and str
                    person = Person.objects.get(pk=person)
                    self.fields[f'{self.person_type}_{i}'] = forms.ChoiceField(
                        label=f"{self.person_type.capitalize()} {i + 1}: Exact match on primary key",
                        widget=forms.RadioSelect,
                        choices=[(person.pk, person.get_full_name() + f" [pk:{person.pk}]")],
                        disabled=True,
                    )
                    self.fields[f'{self.person_type}_{i}'].initial = self.fields[f'{self.person_type}_{i}'].choices[0][0]
                else:  # Assume it's a name
                    self.fields[f'{self.person_type}_{i}'] = forms.ChoiceField(
                        label=f"{self.person_type.capitalize()} {i + 1}: Select matching person or create new",
                        choices=self.get_person_choices(person),
                        widget=forms.RadioSelect,
                        required=True,
                    )
                    # Add a "Create New" option
                    self.fields[f'{self.person_type}_{i}'].choices.insert(0, ('create_new', f'{person} (Create new Person)'))
                    # Set first option as selected
                    self.fields[f'{self.person_type}_{i}'].initial = self.fields[f'{self.person_type}_{i}'].choices[0][0]

    def get_person_choices(self, name):
        # Search for matching `Person` instances
        parts = name.split()  # Split name into parts (first and last)
        matches = Person.objects.filter(
            first__icontains=parts[0],
            last__icontains=parts[-1] if len(parts) > 1 else ''
        )
        return [(person.pk, person.get_full_name() + f" [pk:{person.pk}]") for person in matches]

    # Is this method needed?
    # def get_selected_authors(self):
    #     selected_authors = []
    #     for key, value in self.cleaned_data.items():
    #         if key.startswith("author_"):
    #             selected_authors.append(value)
    #     return selected_authors


class AuthorSelectForm(PersonSelectForm):
    person_type = "author"

    def __init__(self, *args, authors=None, **kwargs):
        super().__init__(*args, persons=authors, **kwargs)

class SupervisorSelectForm(PersonSelectForm):
    person_type = "supervisor"

    def __init__(self, *args, supervisors=None, **kwargs):
        super().__init__(*args, persons=supervisors, **kwargs)

class EditorSelectForm(PersonSelectForm):
    person_type = "editor"

    def __init__(self, *args, editors=None, **kwargs):
        super().__init__(*args, persons=editors, **kwargs)






















    

class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ["title", "authors"]
        widgets = {
            "authors": PersonHeavySelect2TagWidget(
                data_view="test-person-autocomplete",
                attrs={"data-token-separators": "[',',';']",
                       "data-tags": "true",   # enable tagging
                       "data-placeholder": "Add or select authors",
                       "data-minimum-input-length": 2,
                       "style": "width: 400px;",
                }, 
            ),
        }