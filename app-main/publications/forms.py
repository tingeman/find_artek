from django import forms
from django.forms import ModelForm
from django_select2 import forms as s2forms
from publications.models import Publication, Person, Feature
from django.urls import reverse



class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


# class AuthorSelect2TagWidget(s2forms.HeavySelect2TagWidget):
#     # def __init__(self, *args, **kwargs):
#     #     print('In AuthorSelect2TagWidget:__init__')
#     #     super().__init__(*args, **kwargs)
#     def get_url(self):
#         print('In AuthorSelect2TagWidget:get_url')
#         return reverse('person-autocomplete')  # The URL for fetching existing authors

class AuthorSelect2HeavyTagWidget(s2forms.HeavySelect2TagWidget):
    """
    A HeavySelect2TagWidget configured for the Author autocomplete view.
    The data_view parameter will be passed during initialization in the form.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('queryset', Person.objects.none())  # Use an empty queryset as default
        super().__init__(*args, **kwargs)


class CoAuthorsWidget(s2forms.ModelSelect2MultipleWidget):
    search_fields = [
        "username__icontains",
        "email__icontains",
    ]


class AddReportForm(ModelForm):
    """A Form handling the adding or editing of reports
    """
    authors = forms.CharField(
        widget=AuthorSelect2HeavyTagWidget(
             data_view='person-autocomplete',
            attrs={'data-placeholder': "Add or select authors",
                   'data-tags': 'true',  # Equivalent to `tags: true` in JS
        })
    )


    # authors = forms.CharField(max_length=1000, required=False,
    #                             help_text='Full name of all authors, separated by semicolon (;) or &-sign.',
    #                             widget=forms.widgets.Textarea(attrs={'rows': 1, 'cols': 50}))

    supervisors = forms.CharField(max_length=1000, required=False,
                                help_text='Full name of all supervisors, separated by semicolon (;) or &-sign.',
                                widget=forms.widgets.Textarea(attrs={'rows': 1, 'cols': 50}))

#     topics = myfields.TagField(required=False,
#                                 #help_text='Type topics separated by comma or enter',
#                                 widget=mywidgets.TagInput(
#                                         TagInputAttrs={
#                                             'tagSource': "'/pubs/ajax/search/topic/'",
#                                             'allowNewTags': "false",
#                                             'minLength': "0",
#                                             'triggerKeys': [b'enter', b'comma']
#                                         }))

#     keywords = myfields.TagField(required=False,
#                                 #help_text='Type keywords separated by comma or enter',
#                                 widget=mywidgets.TagInput(
#                                         TagInputAttrs={
#                                             'tagSource': "'/pubs/ajax/search/keyword/'",
#                                             'allowNewTags': "true",
#                                             'triggerKeys': [b'enter', b'comma']
#                                         }))

#     pdffile = forms.FileField(required=False, allow_empty_file=True,
#                                 #help_text='Select file to upload',
#                                 widget=AdminFileWidget)

    date = forms.DateField(widget=forms.DateInput(format = '%Y-%m-%d'),
                       input_formats=('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'),
                       required=False)


    class Meta:
        model = Publication
        # # Only show the following fields
        # fields = ['type', 'title', 'number', 'year', 'abstract', 'comment',
        #           'authors', 'supervisors', 'topics', 'keywords', 'pdffile']
        # # Exclude the following native fields of the Publication model, because
        # # we are handling them separately by new fields in the form.
        # # exclude = ['quality', 'keywords', 'topic', 'file']

        fields = ['type', 'title', 'number', 'year', 'abstract', 'comment',
                  'authors', 'supervisors']

    def __init__(self, *args, **kwargs):
        print('In AddReportForm:__init__')
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        if instance:
            print(f'AddReportForm:__init__:instance: {instance}')
            # Restrict the queryset to authors already associated with this publication
            self.fields['authors'].widget.queryset = instance.authors.all()
        else:
            print('AddReportForm:__init__:No instance')
            # For a new publication, no authors are pre-selected
            self.fields['authors'].widget.queryset = Person.objects.none()



    def clean_authors(self):
        authors_data = self.cleaned_data['authors']  # This will be a comma-separated list of author names
        author_names = [name.strip() for name in authors_data.split(',')]
        authors = []

        for name in author_names:
            # Check if the author already exists, otherwise create a new one
            first_name, middle_name, last_name = self.parse_name(name)
            person, created = Person.objects.get_or_create(
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name
            )
            authors.append(person)

        return authors

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
    
    def save(self, full_name):
        # instance = super().save(commit=False)
        # instance.save()
        # self.cleaned_data['authors'] = instance.authors.set(self.cleaned_data['authors'])
        # return instance
        pass



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





class PersonHeavySelect2TagWidget(s2forms.HeavySelect2TagWidget):
    def value_new(self, value):
        """Handle creation of new Person objects."""
        names = value.split()
        first = names[0]
        last = names[-1] if len(names) > 1 else ""
        middle = " ".join(names[1:-1]) if len(names) > 2 else ""
        return Person.objects.create(first=first, middle=middle, last=last).pk


class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ["title", "authors"]
        widgets = {
            "authors": PersonHeavySelect2TagWidget(
                data_view="test-person-autocomplete",
                attrs={"data-token-separators": "[',',';']"},
            ),
        }