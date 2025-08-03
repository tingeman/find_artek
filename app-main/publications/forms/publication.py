"""Forms related to publications."""

from django import forms
from django.forms import ModelForm
from django.contrib.admin.widgets import AdminFileWidget
from django_select2 import forms as s2forms
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from publications.models import Publication, Person, Feature, Topic, Keyword
from publications.utils import create_ordered_queryset, validate_report_number_format
from publications.forms.person import PersonHeavySelect2TagWidget
import datetime
import ast
import json
import re



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
            data_view="publications:person-autocomplete",
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
            data_view="publications:person-autocomplete",
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


class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ["title", "authors"]
        widgets = {
            "authors": PersonHeavySelect2TagWidget(
                data_view="publications:person-autocomplete",
                attrs={"data-token-separators": "[',',';']",
                       "data-tags": "true",   # enable tagging
                       "data-placeholder": "Add or select authors",
                       "data-minimum-input-length": 2,
                       "style": "width: 400px;",
                }, 
            ),
        }


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
