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

    def __init__(self, *args, **kwargs):
        """
        Initialize the widget with proper django-select2 patterns.
        Remove the unused initial_data parameter since Django handles initial values.
        """
        super().__init__(*args, **kwargs)

    def format_value(self, value):
        """
        Convert the initial value (list of PKs) to the format expected by Select2.
        This is crucial for preselection to work properly.
        """
        print(f"PersonHeavySelect2TagWidget:format_value: {value}")
        
        if value is None or value == '':
            return None
            
        # Handle different input formats
        if isinstance(value, (list, tuple)):
            # List of PKs - convert to Person objects for display
            pks = [int(pk) for pk in value if str(pk).isdigit()]
            if pks:
                from publications.models import Person
                persons = Person.objects.filter(pk__in=pks)
                # Return list of PKs as strings (Select2 expects string values)
                return [str(person.pk) for person in persons]
        elif isinstance(value, str) and value:
            try:
                # Try to parse as list representation
                parsed_value = ast.literal_eval(value)
                if isinstance(parsed_value, (list, tuple)):
                    return self.format_value(parsed_value)
                else:
                    return [str(value)]
            except (ValueError, SyntaxError):
                # Single value
                return [str(value)]
        elif hasattr(value, '__iter__'):
            # QuerySet or other iterable
            return [str(item.pk if hasattr(item, 'pk') else item) for item in value]
        else:
            # Single value
            return [str(value)]
            
        return None

    def value_from_datadict(self, data, files, name):
        """
        Extract and format the value from form submission data.
        """
        value = super().value_from_datadict(data, files, name)
        print(f"PersonHeavySelect2TagWidget:value_from_datadict: {value}")
        return value

    def get_context(self, name, value, attrs):
        """Get the context for rendering the widget.
        Ensure that preselected values are properly included in the context.
        """
        context = super().get_context(name, value, attrs)
        
        # Don't clear optgroups - they're needed for preselection display
        # The commented line was interfering with preselection:
        # context['widget']['optgroups'] = []
        
        print(f"PersonHeavySelect2TagWidget:get_context: name={name}, value={value}")
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


class ChangeReportNumberForm(forms.Form):
    """
    Specialized form for changing an existing report's number.
    Handles validation and triggers file/directory renaming.
    """
    new_number = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter new report number (format: YY-NN)',
            'class': 'report-number-field'
        }),
        help_text="New report number in format YY-NN. Files and directories will be renamed automatically."
    )
    
    confirm_change = forms.BooleanField(
        required=True,
        label="I understand this will rename files and directories",
        help_text="Check this box to confirm you want to change the report number and rename associated files"
    )
    
    def __init__(self, *args, publication=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.publication = publication
        if publication:
            self.fields['new_number'].widget.attrs['placeholder'] = f'Current: {publication.number}'
    
    def clean_new_number(self):
        """Validate the new report number"""
        new_number = self.cleaned_data.get('new_number')
        
        if not new_number:
            raise ValidationError("New report number is required")
        
        # Validate format
        from publications.utils import validate_report_number_format
        is_valid, error_message = validate_report_number_format(new_number)
        if not is_valid:
            raise ValidationError(error_message)
        
        # Check if it's the same as current number
        if self.publication and new_number == self.publication.number:
            raise ValidationError("New number must be different from current number")
        
        # Check if number already exists for this year
        if self.publication and self.publication.year:
            existing = Publication.objects.filter(
                year=self.publication.year, 
                number=new_number
            ).exclude(pk=self.publication.pk)
            
            if existing.exists():
                raise ValidationError(f"Report number {new_number} already exists for year {self.publication.year}")
        
        return new_number


class AddEditReportForm(ModelForm):
    """A unified form for both adding and editing reports
    
    Automatically adapts behavior based on whether an instance is provided:
    - When instance=None: Adding mode (number field editable, no delete_pdf option)
    - When instance provided: Editing mode (number field readonly, delete_pdf option available)
    """
    
    # Class variable for file size limit (in MB)
    MAX_FILE_SIZE_MB = 300

    year = forms.IntegerField(
        required=True,  # Required in forms for proper report numbering
        initial=datetime.datetime.now().year,
        widget=forms.NumberInput(attrs={
            'min': 1900,
            'max': datetime.datetime.now().year + 5,  # Allow future years for planning
            'placeholder': 'Enter year'
        }),
        help_text="Year of publication (required for proper report numbering and file organization)"
    )

    # Report number field - auto-generated after save, not editable during creation
    number = forms.CharField(
        max_length=10,
        required=False,  # Not required during form submission - auto-generated
        widget=forms.TextInput(attrs={
            'readonly': True,  # Always readonly in forms
            'placeholder': 'Auto-generated after save',
            'class': 'report-number-field'
        }),
        help_text="Report number will be automatically assigned in format YY-NN when the report is saved"
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
            
            # Configure authors and supervisors for edit mode
            # Note: Initial data for authors/supervisors is now set in the view's _get_edit_initial method
            # to be consistent with how topics and keywords are handled
        else:
            # ADD MODE: Configure form for adding new publication
            print('AddEditReportForm:__init__:ADD MODE - No instance')
            
            # Hide the delete_pdf field in add mode since there's no existing file
            self.fields['delete_pdf'].widget = forms.HiddenInput()
            
            # In ADD mode, number field is readonly and shows placeholder
            self.fields['number'].widget.attrs['readonly'] = True
            self.fields['number'].widget.attrs['placeholder'] = 'Will be auto-generated when report is saved'
            self.fields['number'].help_text = "Report number will be automatically assigned when you save the report"

        print(f'AddEditReportForm:__init__: delete_pdf field after configuration: widget={type(self.fields["delete_pdf"].widget).__name__}')

    def clean_authors(self):
        print(f"AddEditReportForm:clean_authors: {self.cleaned_data['authors']}")
        authors_data = self.cleaned_data['authors']  # Can be list of PKs or string representation

        if authors_data:
            # Handle different input formats for HeavySelect2TagWidget compatibility
            if isinstance(authors_data, list):
                # Direct list format (from widget prepopulation)
                parsed_authors = [str(pk) for pk in authors_data]  # Convert to strings for consistency
                print(f'AddEditReportForm:clean_authors:List format: {parsed_authors}')
            elif isinstance(authors_data, str):
                try:
                    # Try to parse as list representation: "['1001', '996', 'Anders And']"
                    parsed_authors = ast.literal_eval(authors_data)
                    print(f'AddEditReportForm:clean_authors:Parsed string format: {parsed_authors}')
                except (ValueError, SyntaxError):
                    # If parsing fails, treat as single value
                    parsed_authors = [authors_data]
                    print(f'AddEditReportForm:clean_authors:Single value: {parsed_authors}')
            else:
                parsed_authors = [str(authors_data)]
                print(f'AddEditReportForm:clean_authors:Other format: {parsed_authors}')
            
            # If the authors field is empty, return an empty list
            if not parsed_authors:
                print('AddEditReportForm:clean_authors:No authors')
                return Person.objects.none()

            print(f'AddEditReportForm:clean_authors:Final parsed_authors: {parsed_authors}')

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
        supervisors_data = self.cleaned_data['supervisors']  # Can be list of PKs or string representation

        if supervisors_data:
            # Handle different input formats for HeavySelect2TagWidget compatibility
            if isinstance(supervisors_data, list):
                # Direct list format (from widget prepopulation)
                parsed_supervisors = [str(pk) for pk in supervisors_data]  # Convert to strings for consistency
                print(f'AddEditReportForm:clean_supervisors:List format: {parsed_supervisors}')
            elif isinstance(supervisors_data, str):
                try:
                    # Try to parse as list representation: "['1001', '996', 'Anders And']"
                    parsed_supervisors = ast.literal_eval(supervisors_data)
                    print(f'AddEditReportForm:clean_supervisors:Parsed string format: {parsed_supervisors}')
                except (ValueError, SyntaxError):
                    # If parsing fails, treat as single value
                    parsed_supervisors = [supervisors_data]
                    print(f'AddEditReportForm:clean_supervisors:Single value: {parsed_supervisors}')
            else:
                parsed_supervisors = [str(supervisors_data)]
                print(f'AddEditReportForm:clean_supervisors:Other format: {parsed_supervisors}')
            
            # If the supervisors field is empty, return an empty list
            if not parsed_supervisors:
                print('AddEditReportForm:clean_supervisors:No supervisors')
                return Person.objects.none()

            print(f'AddEditReportForm:clean_supervisors:Final parsed_supervisors: {parsed_supervisors}')

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
    
    def clean_year(self):
        """Validate year and ensure it's reasonable"""
        year = self.cleaned_data.get('year')
        if not year:
            raise ValidationError("Year is required")
        
        current_year = datetime.datetime.now().year
        if year < 1900:
            raise ValidationError("Year cannot be before 1900")
        if year > current_year + 5:
            raise ValidationError(f"Year cannot be more than 5 years in the future (max: {current_year + 5})")
        
        return year

    def clean_number(self):
        """Handle report number validation - simplified since auto-generation happens at save"""
        number = self.cleaned_data.get('number')
        
        if self.instance and self.instance.pk:
            # In edit mode, return the existing number (unless specifically changing it)
            return self.instance.number
        else:
            # In add mode, number is auto-generated at save time, not during form validation
            # Return None to indicate auto-generation is needed
            return None
    
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


class UploadAppendixForm(forms.Form):
    """
    Form for uploading multiple appendix files to a publication.
    Uses session-based batch management for file handling.
    
    Note: For very large files (>100MB), we may need to implement 
    a secondary upload scheme with chunked uploads or direct storage.
    """
    appendix_files = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'multiple': True,
            'accept': '.pdf,.doc,.docx,.txt,.zip,.jpg,.jpeg,.png,.gif,.xls,.xlsx,.ppt,.pptx',
            'class': 'form-control',
        }),
        required=False,
        help_text="Select multiple files to upload as appendices. Supported formats: PDF, DOC, TXT, ZIP, images, Office documents."
    )
    
    def clean_appendix_files(self):
        """Validate uploaded files"""
        files = self.files.getlist('appendix_files')
        
        if not files:
            return files
            
        # File size limit (50MB per file)
        max_size = 50 * 1024 * 1024  # 50MB
        
        for file in files:
            if file.size > max_size:
                raise ValidationError(
                    f'File "{file.name}" is too large. Maximum file size is 50MB.'
                )
                
            # Basic file type validation based on extension
            allowed_extensions = {
                '.pdf', '.doc', '.docx', '.txt', '.zip', 
                '.jpg', '.jpeg', '.png', '.gif', 
                '.xls', '.xlsx', '.ppt', '.pptx'
            }
            
            file_ext = file.name.lower().split('.')[-1] if '.' in file.name else ''
            if f'.{file_ext}' not in allowed_extensions:
                raise ValidationError(
                    f'File "{file.name}" has an unsupported file type. '
                    f'Allowed types: {", ".join(sorted(allowed_extensions))}'
                )
        
        return files


class DeleteReportForm(forms.Form):
    """Form for confirming publication deletion"""
    action = forms.CharField(widget=forms.HiddenInput(), required=False)
    publication_pk = forms.IntegerField(widget=forms.HiddenInput())
    
    def clean_action(self):
        action = self.cleaned_data.get('action')
        if action not in ['delete', 'cancel']:
            raise ValidationError('Invalid action')
        return action


class AddFeatureCoordinatesForm(ModelForm):
    """Form for adding a point feature with known coordinates"""
    
    # Coordinate fields
    x_coordinate = forms.DecimalField(
        max_digits=15, 
        decimal_places=6,
        help_text="X coordinate (Easting/Longitude)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'})
    )
    y_coordinate = forms.DecimalField(
        max_digits=15, 
        decimal_places=6,
        help_text="Y coordinate (Northing/Latitude)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'})
    )
    
    # SRID field with simple help text
    spatial_reference_system = forms.CharField(
        max_length=10,
        label="Spatial Reference System (SRID)",
        help_text="Enter EPSG code (e.g., 4326, 32622).",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 4326'})
    )
    
    # Date field with proper widget
    date = forms.DateField(
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        ),
        input_formats=['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'],
        required=False,
        help_text="Date when the feature was observed/measured"
    )

    class Meta:
        model = Feature
        fields = ['name', 'type', 'area', 'date', 'direction', 'description', 
                 'comment', 'pos_quality']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Feature name'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Area/Location'}),
            'direction': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Direction/Orientation'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'pos_quality': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'name': 'Unique identifier or name for this feature',
            'type': 'Type of feature being registered',
            'area': 'General area or location description',
            'direction': 'Direction or orientation if applicable',
            'description': 'Detailed description of the feature',
            'comment': 'Additional comments or notes',
            'pos_quality': 'Quality/accuracy of the position measurement',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make name field required
        self.fields['name'].required = True
        self.fields['type'].required = True
        
        # Set better labels for coordinate fields
        self.fields['x_coordinate'].label = "X Coordinate"
        self.fields['y_coordinate'].label = "Y Coordinate"

    def clean_spatial_reference_system(self):
        """Validate SRID"""
        srid = self.cleaned_data.get('spatial_reference_system')
        if not srid:
            raise ValidationError('Spatial Reference System is required')
        
        try:
            srid_int = int(srid)
            if srid_int <= 0:
                raise ValidationError('SRID must be a positive integer')
        except ValueError:
            raise ValidationError('SRID must be a valid integer')
            
        # Check if SRID exists in spatial reference database
        try:
            from django.contrib.gis.gdal import SpatialReference
            sr = SpatialReference(srid_int)
            # If we get here, the SRID is valid
        except Exception:
            # Issue a warning but don't reject
            self.add_error('spatial_reference_system', 
                          f'Warning: SRID {srid_int} may not be recognized by the system. '
                          f'Please verify this is correct.')
        
        return srid
    
    def clean(self):
        """Cross-field validation for coordinates"""
        cleaned_data = super().clean()
        x_coord = cleaned_data.get('x_coordinate')
        y_coord = cleaned_data.get('y_coordinate')
        srid = cleaned_data.get('spatial_reference_system')
        
        if x_coord is not None and y_coord is not None and srid:
            try:
                srid_int = int(srid)
                
                # Coordinate range validation based on coordinate system type
                if srid_int == 4326:  # WGS84 Geographic
                    if not (-180 <= x_coord <= 180):
                        self.add_error('x_coordinate', 
                                     f'Warning: Longitude {x_coord} is outside normal range (-180 to 180)')
                    if not (-90 <= y_coord <= 90):
                        self.add_error('y_coordinate', 
                                     f'Warning: Latitude {y_coord} is outside normal range (-90 to 90)')
                
                elif 32600 <= srid_int <= 32700:  # UTM zones
                    if not (0 <= x_coord <= 1000000):
                        self.add_error('x_coordinate', 
                                     f'Warning: UTM Easting {x_coord} seems outside normal range (0-1,000,000m)')
                    if not (0 <= y_coord <= 10000000):
                        self.add_error('y_coordinate', 
                                     f'Warning: UTM Northing {y_coord} seems outside normal range (0-10,000,000m)')
                
                elif 25800 <= srid_int <= 25900:  # ETRS89 UTM zones
                    if not (0 <= x_coord <= 1000000):
                        self.add_error('x_coordinate', 
                                     f'Warning: UTM Easting {x_coord} seems outside normal range (0-1,000,000m)')
                    if not (0 <= y_coord <= 10000000):
                        self.add_error('y_coordinate', 
                                     f'Warning: UTM Northing {y_coord} seems outside normal range (0-10,000,000m)')
                
                # General validation for projected coordinates (should be positive)
                elif srid_int != 4326 and (x_coord < 0 or y_coord < 0):
                    if x_coord < 0:
                        self.add_error('x_coordinate', 
                                     'Warning: Negative coordinates are unusual for projected coordinate systems')
                    if y_coord < 0:
                        self.add_error('y_coordinate', 
                                     'Warning: Negative coordinates are unusual for projected coordinate systems')
                
            except ValueError:
                pass  # SRID validation already handled above
                
        return cleaned_data