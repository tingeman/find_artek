from django import forms
from django.forms import ModelForm
from django.contrib.admin.widgets import AdminFileWidget
from django_select2 import forms as s2forms
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.shortcuts import redirect
from publications.models import Publication, Person, Feature, Topic, Keyword
from publications.utils import create_ordered_queryset
from django.urls import reverse
import json
import datetime
import ast
import json


class PersonWorkflowMixin:
    """Mixin for forms that need person disambiguation workflow"""
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Enhanced clean method that handles person workflow"""
        print("🔍 DEBUG: PersonWorkflowMixin.clean() called")
        print(f"🔍 DEBUG: Session keys: {list(self.request.session.keys()) if self.request else 'No request'}")
        print(f"🔍 DEBUG: Has updated_form_data in session: {'updated_form_data' in self.request.session if self.request else 'No request'}")
        
        # Clear workflow redirect FIRST if we have session data to process
        if self.request and 'updated_form_data' in self.request.session:
            if hasattr(self, '_workflow_redirect'):
                delattr(self, '_workflow_redirect')
                print("🔍 DEBUG: Cleared workflow redirect before processing session data")
        
        cleaned_data = super().clean()
        
        # Check if we have updated form data from completed workflow
        if self.request and 'updated_form_data' in self.request.session:
            updated_data = self.request.session.pop('updated_form_data')
            
            print(f"🔍 DEBUG: Restoring updated_form_data from workflow: {updated_data}")
            print(f"🔍 DEBUG: Session keys before workflow restoration: {list(self.request.session.keys())}")
            
            # Merge updated data into cleaned_data, converting tagged names to Person instances
            for field_name, value in updated_data.items():
                print(f"🔍 DEBUG: Processing field '{field_name}': {value} (type: {type(value)})")
                if field_name in self.fields:
                    # Special handling for person fields - convert IDs and CREATE markers to Person instances
                    if field_name in ['authors', 'supervisors'] and isinstance(value, list):
                        print(f"🔍 DEBUG: Processing person field '{field_name}' with list value: {value}")
                        from publications.models import Person
                        
                        converted_persons = []
                        for item in value:
                            if isinstance(item, str):
                                # Check if it's a CREATE marker
                                if item.startswith('CREATE:'):
                                    person_name = item[7:]  # Remove 'CREATE:' prefix
                                    # Create new person
                                    try:
                                        person = Person(created_by=self.request.user, modified_by=self.request.user)
                                        person.set_names(person_name)
                                        person.save()
                                        converted_persons.append(person)
                                        print(f"🔍 DEBUG: Created new person from CREATE marker: {person_name} -> {person}")
                                    except Exception as e:
                                        print(f"❌ DEBUG: Failed to create person from CREATE marker {person_name}: {e}")
                                        # Keep the original item for further processing
                                        converted_persons.append(item)
                                elif item.startswith('SKIP:'):
                                    # Keep the SKIP: prefix - this prevents workflow from triggering again
                                    converted_persons.append(item)
                                    print(f"🔍 DEBUG: Keeping skipped item with prefix: {item}")
                                elif item.isdigit():
                                    # It's a person ID
                                    try:
                                        person = Person.objects.get(id=int(item))
                                        converted_persons.append(person)
                                        print(f"🔍 DEBUG: Restored person from ID: {item} -> {person}")
                                    except Person.DoesNotExist:
                                        print(f"❌ DEBUG: Person with ID {item} not found")
                                        # Keep the original item for further processing
                                        converted_persons.append(item)
                                else:
                                    # Some other string format - keep as string
                                    # This allows non-person data to pass through unchanged
                                    converted_persons.append(item)
                                    print(f"🔍 DEBUG: Keeping string item unchanged: {item}")
                            else:
                                # Already a Person instance or other type
                                converted_persons.append(item)
                        
                        # Convert to QuerySet if we have Person instances
                        if converted_persons and all(isinstance(p, Person) for p in converted_persons):
                            from publications.forms import create_ordered_queryset
                            cleaned_data[field_name] = create_ordered_queryset(Person, [p.pk for p in converted_persons])
                            print(f"🔍 DEBUG: Converted {field_name} to QuerySet with {len(converted_persons)} persons")
                        else:
                            cleaned_data[field_name] = converted_persons
                            print(f"🔍 DEBUG: {field_name} still has unresolved data: {converted_persons}")
                    else:
                        # For all other fields, SKIP restoration - let Django handle them normally
                        # This prevents type conversion issues with fields like ModelChoiceField
                        print(f"🔍 DEBUG: Skipping non-person field {field_name} (value: {value}, type: {type(value)})")
                        pass
                        
            print(f"🔍 DEBUG: Final cleaned_data after workflow restoration: {cleaned_data}")
            
            # Clear any workflow redirect since we've processed the workflow data
            if hasattr(self, '_workflow_redirect'):
                delattr(self, '_workflow_redirect')
                print("🔍 DEBUG: Cleared workflow redirect after successful data restoration")
        
        return cleaned_data
    
    def clean_authors_with_workflow(self):
        """Enhanced clean_authors method with workflow support"""
        authors = self.cleaned_data.get('authors', [])
        
        # Check if disambiguation workflow is needed
        workflow_result = self.check_person_disambiguation_needed(['authors'])
        
        if workflow_result:
            field_name, person_names = workflow_result
            # Start workflow and return redirect response
            return self.start_person_workflow(field_name, person_names)
        
        return authors

    def clean_supervisors_with_workflow(self):
        """Enhanced clean_supervisors method with workflow support"""
        supervisors = self.cleaned_data.get('supervisors', [])
        
        # Check if disambiguation workflow is needed
        workflow_result = self.check_person_disambiguation_needed(['supervisors'])
        
        if workflow_result:
            field_name, person_names = workflow_result
            # Start workflow and return redirect response
            return self.start_person_workflow(field_name, person_names)
        
        return supervisors

    def clean_editors_with_workflow(self):
        """Enhanced clean_editors method with workflow support"""
        editors = self.cleaned_data.get('editors', [])
        
        # Check if disambiguation workflow is needed
        workflow_result = self.check_person_disambiguation_needed(['editors'])
        
        if workflow_result:
            field_name, person_names = workflow_result
            # Start workflow and return redirect response
            return self.start_person_workflow(field_name, person_names)
        
        return editors
    
    def check_person_disambiguation_needed(self, field_names):
        """
        Check if person disambiguation is needed for specified fields.
        Returns the first field that needs disambiguation, or None if all are resolved.
        """
        if not self.request:
            return None
        
        # Import here to avoid circular imports
        from publications.person_workflow import extract_person_names
        
        for field_name in field_names:
            if field_name in self.cleaned_data:
                field_data = self.cleaned_data[field_name]
                
                # Convert to list if it's a single value
                if isinstance(field_data, str):
                    field_data = [field_data]
                elif hasattr(field_data, '__iter__') and not isinstance(field_data, str):
                    field_data = list(field_data)
                else:
                    continue
                
                # Check if any names need disambiguation
                names_needing_resolution = extract_person_names(
                    MockFormData(field_data), field_name
                )
                
                if names_needing_resolution:
                    return field_name, names_needing_resolution
        
        return None
    
    def start_person_workflow(self, field_name, person_names):
        """Start person disambiguation workflow"""
        if not self.request:
            raise ValueError("Request object required for workflow")
        
        # Clear any existing workflow data to prevent interference
        if 'updated_form_data' in self.request.session:
            del self.request.session['updated_form_data']
            print("🔍 DEBUG: Cleared old workflow session data before starting new workflow")
        
        # Import here to avoid circular imports
        from publications.person_workflow import PersonWorkflowSession
        
        workflow = PersonWorkflowSession(self.request)
        
        # Store RAW POST data instead of cleaned data to avoid model instance serialization issues
        raw_form_data = dict(self.request.POST)
        
        # Convert QueryDict list values to simple values where appropriate
        simplified_form_data = {}
        for key, value_list in raw_form_data.items():
            if len(value_list) == 1:
                # Single value - store as string
                simplified_form_data[key] = value_list[0]
            else:
                # Multiple values - store as list
                simplified_form_data[key] = value_list
        
        print(f"🔍 DEBUG: Storing raw POST data for workflow: {simplified_form_data}")
        
        # Test JSON serialization to ensure it will work
        try:
            import json
            json.dumps(simplified_form_data)
            print("✅ Raw POST data is JSON serializable")
        except (TypeError, ValueError) as e:
            print(f"❌ Raw POST data serialization failed: {e}")
            print(f"Problematic data: {simplified_form_data}")
        
        workflow.start_workflow(field_name, person_names, simplified_form_data, self.request.path)
        
        return redirect('publications:disambiguate_person_step')


class MockFormData:
    """Mock form data object for extract_person_names function"""
    
    def __init__(self, data_list):
        self.data = data_list
    
    def getlist(self, field_name):
        return self.data
    
    def get(self, field_name, default=None):
        return self.data if self.data else default


def clean_authors_with_workflow(form_instance):
    """
    Standalone utility function for enhanced clean_authors method with workflow support.
    
    This is a utility function that can be called from any form's clean_authors method
    to add workflow support. For forms that inherit from PersonWorkflowMixin,
    use the clean_authors_with_workflow method instead.
    
    Args:
        form_instance: The form instance that should have PersonWorkflowMixin capabilities
    
    Returns:
        Either the processed authors data or a redirect response for workflow
    """
    if not hasattr(form_instance, 'check_person_disambiguation_needed'):
        raise ValueError("Form instance must have PersonWorkflowMixin capabilities")
    
    authors = form_instance.cleaned_data.get('authors', [])
    
    # Check if disambiguation workflow is needed
    workflow_result = form_instance.check_person_disambiguation_needed(['authors'])
    
    if workflow_result:
        field_name, person_names = workflow_result
        # Start workflow and return redirect response
        return form_instance.start_person_workflow(field_name, person_names)
    
    return authors


def clean_supervisors_with_workflow(form_instance):
    """
    Standalone utility function for enhanced clean_supervisors method with workflow support.
    
    This is a utility function that can be called from any form's clean_supervisors method
    to add workflow support. For forms that inherit from PersonWorkflowMixin,
    use the clean_supervisors_with_workflow method instead.
    
    Args:
        form_instance: The form instance that should have PersonWorkflowMixin capabilities
    
    Returns:
        Either the processed supervisors data or a redirect response for workflow
    """
    if not hasattr(form_instance, 'check_person_disambiguation_needed'):
        raise ValueError("Form instance must have PersonWorkflowMixin capabilities")
    
    supervisors = form_instance.cleaned_data.get('supervisors', [])
    
    # Check if disambiguation workflow is needed
    workflow_result = form_instance.check_person_disambiguation_needed(['supervisors'])
    
    if workflow_result:
        field_name, person_names = workflow_result
        # Start workflow and return redirect response
        return form_instance.start_person_workflow(field_name, person_names)
    
    return supervisors


def clean_editors_with_workflow(form_instance):
    """
    Standalone utility function for enhanced clean_editors method with workflow support.
    
    This is a utility function that can be called from any form's clean_editors method
    to add workflow support. For forms that inherit from PersonWorkflowMixin,
    use the clean_editors_with_workflow method instead.
    
    Args:
        form_instance: The form instance that should have PersonWorkflowMixin capabilities
    
    Returns:
        Either the processed editors data or a redirect response for workflow
    """
    if not hasattr(form_instance, 'check_person_disambiguation_needed'):
        raise ValueError("Form instance must have PersonWorkflowMixin capabilities")
    
    editors = form_instance.cleaned_data.get('editors', [])
    
    # Check if disambiguation workflow is needed
    workflow_result = form_instance.check_person_disambiguation_needed(['editors'])
    
    if workflow_result:
        field_name, person_names = workflow_result
        # Start workflow and return redirect response
        return form_instance.start_person_workflow(field_name, person_names)
    
    return editors


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class AddPersonForm(forms.ModelForm):
    """Form for creating new Person instances"""
    
    # Add a name field that will be processed by the Person model
    name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Full name (e.g., "John Doe" or "Doe, John")'
        }),
        help_text="Enter the person's full name. It will be automatically split into first, middle, and last name components."
    )
    
    class Meta:
        model = Person
        fields = ['email', 'institution', 'department']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'institution': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Institution'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department'}),
        }
    
    def save(self, commit=True):
        """Override save to handle the name field properly"""
        instance = super().save(commit=False)
        name = self.cleaned_data.get('name')
        if name:
            # The Person model will handle name parsing in its __init__ method
            # But since we're working with an existing instance, we need to call set_names
            instance.set_names(name, commit=False)
        
        if commit:
            instance.save()
        return instance


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
            return []  # Return empty list instead of None
            
        # Handle different input formats
        if isinstance(value, (list, tuple)):
            # List of PKs - convert to Person objects for display
            pks = [int(pk) for pk in value if str(pk).isdigit()]
            if pks:
                from publications.models import Person
                persons = Person.objects.filter(pk__in=pks)
                # Return list of PKs as strings (Select2 expects string values)
                return [str(person.pk) for person in persons]
            else:
                return []  # Return empty list if no valid PKs
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
            try:
                return [str(item.pk if hasattr(item, 'pk') else item) for item in value]
            except:
                return []  # Return empty list if iteration fails
        else:
            # Single value
            return [str(value)]
            
        return []  # Return empty list as fallback instead of None

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
        """Get person choices with enhanced matching and metadata display"""
        matches = self.get_person_matches(name)
        
        # Format choices with additional identifying information
        choices = []
        for match in matches:
            person = match['person']
            confidence = match['confidence']
            match_type = match['match_type']
            
            # Build display string with unique identifiers
            display_parts = [person.get_full_name()]
            
            # Add confidence indicator
            confidence_str = f"{confidence:.0%}"
            display_parts.append(f"({confidence_str})")
            
            # Add unique identifiers
            identifiers = []
            if person.pk:
                identifiers.append(f"pk:{person.pk}")
            if person.email:
                identifiers.append(f"email:{person.email}")
            if person.id_number:
                identifiers.append(f"id:{person.id_number}")
            
            if identifiers:
                display_parts.append(f"[{', '.join(identifiers)}]")
            
            # Add match type if not exact
            if match_type != 'exact_full':
                display_parts.append(f"({match_type})")
            
            display_string = ' '.join(display_parts)
            choices.append((person.pk, display_string))
        
        return choices

    def get_person_matches(self, name_string):
        """Get potential person matches using comprehensive matching strategies"""
        from publications.models import Person
        from pybtex.database import Person as PyBTeXPerson
        from django.db.models import Q
        import re
        
        # Parse the name using PyBTeX
        parsed_person = PyBTeXPerson(name_string)
        
        # Extract components
        first = ' '.join(parsed_person.first()) if parsed_person.first() else ''
        middle = ' '.join(parsed_person.middle()) if parsed_person.middle() else ''
        prelast = ' '.join(parsed_person.prelast()) if parsed_person.prelast() else ''
        last = ' '.join(parsed_person.last()) if parsed_person.last() else ''
        lineage = ' '.join(parsed_person.lineage()) if parsed_person.lineage() else ''
        
        matches = []
        seen_ids = set()
        
        # Helper function to add match if not already seen
        def add_match(person, match_type, confidence, notes=''):
            if person.id not in seen_ids:
                seen_ids.add(person.id)
                matches.append({
                    'person': person,
                    'match_type': match_type,
                    'confidence': confidence,
                    'notes': notes,
                    'pk': person.pk,
                    'email': person.email,
                    'id_number': person.id_number
                })
        
        # Helper function for special character substitution
        def normalize_name(name):
            """Normalize special characters for matching"""
            substitutions = {
                'ø': 'oe', 'ö': 'oe', 'ü': 'ue', 'ä': 'ae', 'å': 'aa',
                'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
                'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a',
                'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
                'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o',
                'ú': 'u', 'ù': 'u', 'û': 'u',
                'ç': 'c', 'ñ': 'n'
            }
            normalized = name.lower()
            for char, replacement in substitutions.items():
                normalized = normalized.replace(char, replacement)
            return normalized
        
        # Helper function for alternative character substitutions
        def get_name_variants(name):
            """Get multiple variants of a name with different character substitutions"""
            variants = [name.lower()]
            
            # Danish/Norwegian specific substitutions
            variants.append(name.lower().replace('ø', 'oe'))
            variants.append(name.lower().replace('ø', 'o'))
            variants.append(name.lower().replace('æ', 'ae'))
            variants.append(name.lower().replace('æ', 'a'))
            variants.append(name.lower().replace('å', 'aa'))
            variants.append(name.lower().replace('å', 'a'))
            
            # Remove duplicates while preserving order
            seen = set()
            unique_variants = []
            for variant in variants:
                if variant not in seen:
                    seen.add(variant)
                    unique_variants.append(variant)
            
            return unique_variants
        
        # Helper function to check if names are truly identical (case-insensitive only)
        def are_names_identical(search_name, db_name):
            """Check if two names are exactly identical (case-insensitive only)"""
            return search_name.lower().strip() == db_name.lower().strip()
        
        # Helper function to check if names differ only by special characters
        def are_names_character_variants(search_name, db_name):
            """Check if two names differ only by special character substitutions"""
            if are_names_identical(search_name, db_name):
                return False  # They're identical, not variants
            
            # Normalize both and see if they match
            search_normalized = normalize_name(search_name)
            db_normalized = normalize_name(db_name)
            return search_normalized == db_normalized
        
        # Strategy 1: TRUE EXACT match on all name components (case-insensitive but no character substitution)
        if first and last:
            query = Q(first__iexact=first, last__iexact=last)
            if middle:
                query &= Q(middle__iexact=middle)
            if prelast:
                query &= Q(prelast__iexact=prelast)
            if lineage:
                query &= Q(lineage__iexact=lineage)
            
            potential_matches = Person.objects.filter(query)
            for person in potential_matches:
                # Check if it's truly identical (case-insensitive) vs character variant
                person_first = person.first or ''
                person_middle = person.middle or ''
                person_last = person.last or ''
                person_prelast = person.prelast or ''
                person_lineage = person.lineage or ''
                
                # Check if ALL components are case-identical (no character substitution)
                is_case_only_diff = (
                    are_names_identical(first, person_first) and
                    are_names_identical(middle, person_middle) and
                    are_names_identical(last, person_last) and
                    are_names_identical(prelast, person_prelast) and
                    are_names_identical(lineage, person_lineage)
                )
                
                # Check if any component is a character variant
                has_character_variants = (
                    are_names_character_variants(first, person_first) or
                    are_names_character_variants(middle, person_middle) or
                    are_names_character_variants(last, person_last) or
                    are_names_character_variants(prelast, person_prelast) or
                    are_names_character_variants(lineage, person_lineage)
                )
                
                if is_case_only_diff:
                    add_match(person, 'exact_full', 1.0, 'Exact match on all name components')
                elif has_character_variants:
                    add_match(person, 'normalized_full', 0.85, 'Character variant match (full name)')
        
        # Strategy 2: Exact match on first, middle, last (ignoring prelast/lineage)
        if first and last and not any(m['match_type'] in ['exact_full', 'normalized_full'] for m in matches):
            query = Q(first__iexact=first, last__iexact=last)
            if middle:
                query &= Q(middle__iexact=middle)
            
            potential_matches = Person.objects.filter(query)
            for person in potential_matches:
                # Check if core components are case-identical vs character variants
                person_first = person.first or ''
                person_middle = person.middle or ''
                person_last = person.last or ''
                
                is_case_only_diff = (
                    are_names_identical(first, person_first) and
                    are_names_identical(middle, person_middle) and
                    are_names_identical(last, person_last)
                )
                
                has_character_variants = (
                    are_names_character_variants(first, person_first) or
                    are_names_character_variants(middle, person_middle) or
                    are_names_character_variants(last, person_last)
                )
                
                if is_case_only_diff:
                    add_match(person, 'exact_core', 0.95, 'Exact match on core name components')
                elif has_character_variants:
                    add_match(person, 'normalized_core', 0.80, 'Character variant match (core names)')
        
        # Strategy 3: First + Last name matching (exact search)
        if first and last:
            first_last_matches = Person.objects.filter(
                Q(first__iexact=first) & Q(last__iexact=last)
            )
            for person in first_last_matches:
                person_first = person.first or ''
                person_last = person.last or ''
                
                first_is_case_identical = are_names_identical(first, person_first)
                last_is_case_identical = are_names_identical(last, person_last)
                
                first_is_character_variant = are_names_character_variants(first, person_first)
                last_is_character_variant = are_names_character_variants(last, person_last)
                
                if first_is_case_identical and last_is_case_identical:
                    add_match(person, 'exact_first_last', 0.90, 'Exact first + last name match')
                elif (first_is_character_variant or first_is_case_identical) and (last_is_character_variant or last_is_case_identical):
                    add_match(person, 'normalized_first_last', 0.85, 'First + last name character variant match')
        
        # Strategy 4: First + Middle name matching (when last name missing)
        if first and last and not middle:
            # Check if "last" could actually be a middle name
            first_middle_matches = Person.objects.filter(
                Q(first__iexact=first) & Q(middle__iexact=last)
            )
            for person in first_middle_matches:
                person_first = person.first or ''
                person_middle = person.middle or ''
                
                first_is_exact = are_names_identical(first, person_first)
                middle_is_exact = are_names_identical(last, person_middle)
                
                if first_is_exact and middle_is_exact:
                    add_match(person, 'exact_first_middle', 0.85, f'Exact first name + middle name "{last}" match')
        
        # Strategy 4b: First + Middle variant matching
        if first and last and not middle:
            first_variants = get_name_variants(first)
            last_variants = get_name_variants(last)
            
            for person in Person.objects.all():
                if person.id in seen_ids or not person.first or not person.middle:
                    continue
                
                person_first_variants = get_name_variants(person.first)
                person_middle_variants = get_name_variants(person.middle)
                
                # Check if search terms match first + middle with variants
                first_match = any(fv == pfv for fv in first_variants for pfv in person_first_variants)
                middle_match = any(lv == pmv for lv in last_variants for pmv in person_middle_variants)
                
                if first_match and middle_match:
                    add_match(person, 'normalized_first_middle', 0.82, f'First name + middle name variant match')
        
        # Strategy 5: Initial matching - first initial + middle + last
        if first and last:
            first_initial = first[0].upper()
            query = Q(first__istartswith=first_initial, last__iexact=last)
            if middle:
                query &= Q(middle__iexact=middle)
            
            initial_matches = Person.objects.filter(query)
            for person in initial_matches:
                # Check if last name is case-identical vs character variant
                person_last = person.last or ''
                person_middle = person.middle or ''
                
                last_is_case_identical = are_names_identical(last, person_last)
                middle_is_case_identical = are_names_identical(middle, person_middle) if middle else True
                
                last_is_character_variant = are_names_character_variants(last, person_last)
                middle_is_character_variant = are_names_character_variants(middle, person_middle) if middle else False
                
                if last_is_case_identical and middle_is_case_identical:
                    add_match(person, 'initial_match', 0.8, f'First initial "{first_initial}" + exact last name match')
                elif (last_is_character_variant or last_is_case_identical) and (middle_is_character_variant or middle_is_case_identical):
                    add_match(person, 'initial_variant', 0.75, f'First initial "{first_initial}" + character variant last name match')
        
        # Strategy 5b: Initial matching with middle name - first initial + middle + last
        if first and last:
            first_initial = first[0].upper()
            # Try matching where the provided "last" name is actually someone's middle name
            middle_matches = Person.objects.filter(
                Q(first__istartswith=first_initial) & Q(middle__iexact=last)
            )
            for person in middle_matches:
                person_middle = person.middle or ''
                middle_is_exact = are_names_identical(last, person_middle)
                
                if middle_is_exact:
                    add_match(person, 'initial_middle', 0.75, f'First initial "{first_initial}" + exact middle name "{last}" match')
        
        # Strategy 6: ID number matching (if name_string could be an ID)
        if re.match(r'^[a-zA-Z0-9]+$', name_string.strip()) and len(name_string.strip()) >= 3:
            id_matches = Person.objects.filter(id_number__iexact=name_string.strip())
            for person in id_matches:
                add_match(person, 'id_number', 0.9, f'ID number match: {person.id_number}')
        
        # Strategy 7: Special character normalization matching (for remaining cases)
        if first and last:
            first_variants = get_name_variants(first)
            last_variants = get_name_variants(last)
            
            # Find persons whose names match variants (but exclude already found matches)
            all_persons = Person.objects.all()
            for person in all_persons:
                if person.id in seen_ids:
                    continue
                    
                person_first_variants = get_name_variants(person.first) if person.first else ['']
                person_last_variants = get_name_variants(person.last) if person.last else ['']
                
                # Check for variant matches (only proceed if not already matched)
                first_match = any(fv in person_first_variants for fv in first_variants) or any(pfv in first_variants for pfv in person_first_variants)
                last_match = any(lv in person_last_variants for lv in last_variants) or any(plv in last_variants for plv in person_last_variants)
                
                if first_match and last_match:
                    # Check middle name too if provided
                    if middle:
                        middle_variants = get_name_variants(middle)
                        person_middle_variants = get_name_variants(person.middle) if person.middle else ['']
                        middle_match = any(mv in person_middle_variants for mv in middle_variants)
                        
                        if middle_match:
                            add_match(person, 'normalized_remaining', 0.70, 'Additional normalized character match (full)')
                    else:
                        add_match(person, 'normalized_remaining', 0.65, 'Additional normalized character match (core)')
        
        # Strategy 8: Last name only with first initial (broader search)
        if first and last and len(matches) < 5:
            first_initial = first[0].upper()
            broad_matches = Person.objects.filter(
                Q(first__istartswith=first_initial) & Q(last__icontains=last)
            )
            for person in broad_matches:
                add_match(person, 'broad_initial', 0.6, f'Broad search: "{first_initial}" + partial last name')
        
        # Strategy 9: Fuzzy matching on last name (lowest priority)
        if last and len(matches) < 8:
            # Split compound last names and search for parts
            last_parts = re.split(r'[-\s]+', last)
            for part in last_parts:
                if len(part) >= 3:  # Only search meaningful parts
                    fuzzy_matches = Person.objects.filter(last__icontains=part)
                    for person in fuzzy_matches:
                        add_match(person, 'fuzzy_last', 0.4, f'Fuzzy match on last name part: "{part}"')
        
        # Strategy 10: Email domain matching (if name_string looks like email)
        if '@' in name_string:
            email_matches = Person.objects.filter(email__iexact=name_string.strip())
            for person in email_matches:
                add_match(person, 'email_exact', 0.95, f'Email match: {person.email}')
        
        # Sort by confidence score (descending)
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Limit to top 15 matches to avoid overwhelming the user
        return matches[:15]

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
                data_view="publications:person-autocomplete",
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
        required=True,
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
        # Make required fields obvious
        self.fields['name'].required = True
        self.fields['type'].required = True
        self.fields['pos_quality'].required = True
        self.fields['date'].required = True
        self.fields['x_coordinate'].required = True
        self.fields['y_coordinate'].required = True
        self.fields['spatial_reference_system'].required = True
        
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
        date = cleaned_data.get('date')
        name = cleaned_data.get('name')
        pos_quality = cleaned_data.get('pos_quality')
        
        # Check that all required fields are provided
        if not name:
            self.add_error('name', 'Feature name is required')
        
        if not pos_quality:
            self.add_error('pos_quality', 'Position quality is required')
        
        # Check that all coordinate fields are provided together
        coordinate_fields = [x_coord, y_coord, srid]
        has_any_coords = any(field is not None for field in coordinate_fields)
        has_all_coords = all(field is not None for field in coordinate_fields)
        
        if has_any_coords and not has_all_coords:
            if x_coord is None:
                self.add_error('x_coordinate', 'X coordinate is required when providing coordinate information')
            if y_coord is None:
                self.add_error('y_coordinate', 'Y coordinate is required when providing coordinate information')
            if srid is None:
                self.add_error('spatial_reference_system', 'Spatial Reference System is required when providing coordinates')
        
        # All coordinate fields are required for this form
        if not has_all_coords:
            if x_coord is None:
                self.add_error('x_coordinate', 'X coordinate is required')
            if y_coord is None:
                self.add_error('y_coordinate', 'Y coordinate is required')
            if srid is None:
                self.add_error('spatial_reference_system', 'Spatial Reference System is required')
        
        # Date field is required
        if not date:
            self.add_error('date', 'Date is required')
        
        # If we have all coordinate data, validate ranges
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