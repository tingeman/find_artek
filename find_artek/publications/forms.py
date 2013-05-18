import pdb

from django import forms
from django.forms import ModelForm
from django.contrib.admin.widgets import AdminFileWidget

from olwidget.forms import MapModelForm

from find_artek.publications.models import Publication, Person, Feature
from find_artek import fields as myfields
from find_artek import widgets as mywidgets

#from person_utils import fullname, create_pybtex_person


class AddReportForm(ModelForm):
    """A Form handling the adding or editing of reports

    """
    authors = forms.CharField(max_length=1000, required=False,
                                help_text='Full name of all authors, separated by semicolon (;) or &-sign.',
                                widget=forms.widgets.Textarea(attrs={'rows': 1, 'cols': 50}))

    topic = myfields.TagField(required=False,
                                #help_text='Type topics separated by comma or enter',
                                widget=mywidgets.TagInput(
                                        TagInputAttrs={
                                            'tagSource': "'/pubs/ajax/search/topic/'",
                                            'allowNewTags': "false",
                                            'minLength': "0",
                                            'triggerKeys': [b'enter', b'comma']
                                        }))

    keywords = myfields.TagField(required=False,
                                #help_text='Type keywords separated by comma or enter',
                                widget=mywidgets.TagInput(
                                        TagInputAttrs={
                                            'tagSource': "'/pubs/ajax/search/keyword/'",
                                            'allowNewTags': "true",
                                            'triggerKeys': [b'enter', b'comma']
                                        }))

    pdffile = forms.FileField(required=False, allow_empty_file=True,
                                #help_text='Select file to upload',
                                widget=AdminFileWidget)

    class Meta:
        model = Publication
        # Exclude the following native fields of the Publication model, because
        # we are handling them separately by new fields in the form.
        exclude = ['quality', 'keywords', 'topic', 'file']

    def __init__(self, *args, **kwargs):
        # Call the parents initialization method
        super(AddReportForm, self).__init__(*args, **kwargs)  # Call to ModelForm constructor

        # Set the size of the number input field
        self.fields['number'].widget.attrs['size'] = 5

        if 'instance' in kwargs and kwargs['instance']:
            # A model instance was passed, we are editing an existing model...

            # parse authors and post in textfield
            p = kwargs['instance']

            # Populate author list
            a_set = p.authorship_set.all().order_by('author_id')
            if a_set:
                a_list = [a.person.__unicode__() +
                            ' [id:{0}]'.format(a.person.id) \
                            for a in a_set]
            else:
                a_list = []
            self.fields['authors'].initial = '\n'.join(a_list)

            # populate keywords field
            self.fields['keywords'].initial = [k.keyword for k in p.keywords.all()]

            # populate topic field
            self.fields['topic'].initial = [k.topic for k in p.topics.all()]

            # populate pdffile field
            if p.file:
                self.fields['pdffile'].initial = p.file.file


class AddPublicationsFromFileForm(forms.Form):
    """Form to handle import of publication information from a file.

    """
    BIBTEX = 'bib'
    EXCEL = 'xlsx'
    CSV = 'csv'
    FILE_TYPES = (
        (EXCEL, 'Excel (xls or xlsx)'),
        (BIBTEX, 'Bibtex'),
        (CSV, 'csv (semicolon separated)'),
    )
    type = forms.ChoiceField(choices=FILE_TYPES)
    file = forms.FileField()


class AddFeaturesFromFileForm(forms.Form):
    """Form to handle import of feature information from a file.

    """
    EXCEL = 'xlsx'
    FILE_TYPES = (
        (EXCEL, 'Excel (xls or xlsx)'),
    )
    type = forms.ChoiceField(choices=FILE_TYPES)
    file = forms.FileField()


class AddPersonForm(ModelForm):
    name = forms.CharField(max_length=100, required=True,
                                help_text='Full name of Person')

    class Meta:
        model = Person
        #exclude = ['quality', 'first_relaxed', 'last_relaxed', 'first', 'middle',
        #            'prelast', 'last', 'lineage', 'pre_titulation', 'post_titulation']
        fields = ['position', 'initials', 'institution', 'department',
                    'address_1', 'address_2', 'zip_code', 'town', 'state',
                    'country', 'phone', 'cell_phone', 'email', 'homepage',
                    'id_number', 'note']

        normal_fields = ['name', 'position', 'email', 'id_number']

    def __init__(self, *args, **kwargs):
        # Implementation of trick to have 'name' field appear at the top of the list.
        # could be used to completely reorder...

        super(AddPersonForm, self).__init__(*args, **kwargs)  # Call to ModelForm constructor
        #first argument, index is the position of the field you want it to come before
        self.fields.insert(0, 'name', self.fields['name'])

        # set the name field
        name_fields = ['first', 'middle', 'prelast', 'last', 'lineage', 'pre_titulation', 'post_titulation']
        if 'data' in kwargs and kwargs['data']:
            # initial data were passed to the form as dictionary.
            # Extract name related fields
            if 'name' in kwargs['data']:
                self.fields['name'].initial = kwargs['data']['name']
            else:
                name_args = {k: kwargs['data'][k] for k in name_fields if k in kwargs['data']}  # This formulations should be ok!
                if name_args:
                    self.fields['name'].initial = fullname(name_args)

        if 'instance' in kwargs and kwargs['instance']:
            self.fields['name'].initial = kwargs['instance'].__unicode__()

    def save(self, force_insert=False, force_update=False, commit=True, *args, **kwargs):
        p = super(AddPersonForm, self).save(commit=False, *args, **kwargs)
        if self.cleaned_data['name']:
            p.set_names(self.cleaned_data['name'], commit=False)

        if commit:
            p.save()

        return p

    def normal_fields(self):
        # Used to sort fields in the form rendering.
        return [field for field in self if not field.is_hidden
               and field.name in self.Meta.normal_fields]

    def collapsible_fields(self):
        # Used to sort fields in the form rendering.
        return [field for field in self if not field.is_hidden
               and field.name not in self.Meta.normal_fields]


class AddFeatureForm(MapModelForm):
    class Meta:
        model = Feature
        exclude = ('area', 'URLs', 'files', 'images', 'quality', 'publications',)
        maps = (
#            (('points', 'lines', 'polys'),
            (('points',),
                {'layers': ['osm.mapnik', 'google.satellite'],
                 'default_lat': 65.56755, 'default_lon': -45.043945,
                 'map_options': {
                     'controls': ["LayerSwitcher", "Attribution", "MousePosition"],
#                     'controls': ["LayerSwitcher", "NavToolbar", "PanZoom",
#                                  "Attribution", "MousePosition"],
                 },
                },
             ), )

    # def __init__(self, *args, **kwargs):
    #     # Call the parents initialization method
    #     super(AddFeatureForm, self).__init__(*args, **kwargs)  # Call to ModelForm constructor
