import os

from django.db import models
from django.contrib.auth.models import User
from django.contrib.gis.db import models as geo_models

from publications import utils
from pybtex.database import Person as pybtexPerson
from pybtex.bibtex import utils as pybtex_utils


# Global variables
CURRENT = 0
CREATED = 10
UPDATED = 20
REJECTED = 40
OBSOLETE = 50

quality_flags = (
    (CURRENT, 'Current'),
    (CREATED, 'Created'),
    (UPDATED, 'Changed'),
    (REJECTED, 'Rejected'),
    (OBSOLETE, 'Obsolete'),
)

# Global functions
def get_file_path(obj, filename):
    if obj.upload_to:
        filename = os.path.basename(filename)
        return os.path.join(obj.upload_to, filename)
    else:
        print("Trying to auto-generate file path! Failure!")
        raise NotImplementedError('get_file_path is not implemented for automatic path generation!')
    
def has_model_permission(entity, app, perm, model ):
    """Checks if entity (user or group) has specified permission for the model passed

    entity:     a user or group object
    model:      string representation of model (must be lower case)
    perm:       permission (string). '_model' will be automatically added
    app:        name of the app the model is defined in.
    """
    # QUESTION: What is this doing?
    return entity.has_perm( "{0}.{1}_{2}".format( app, perm, model ) )

def get_image_path(obj, filename):
    if obj.upload_to:
        filename = os.path.basename(filename)
        return os.path.join(obj.upload_to, filename)
    else:
        print("Trying to auto-generate image path! Failure!") 
        raise NotImplementedError('get_image_path is not implemented for automatic path generation!')

# Models
class BaseModel(models.Model):

    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False, related_name="%(class)s_created")
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False, related_name="%(class)s_modified")

    class Meta:
        abstract = True

class Person(BaseModel):

    quality = models.SmallIntegerField(choices=quality_flags, default=CREATED)
    first_relaxed = models.CharField(max_length=10, blank=True)
    last_relaxed = models.CharField(max_length=100, blank=True)
    first = models.CharField(max_length=100, blank=True)
    middle = models.CharField(max_length=100, blank=True)
    prelast = models.CharField(max_length=100, blank=True)
    last = models.CharField(max_length=100, blank=True)
    lineage = models.CharField(max_length=100, blank=True)
    pre_titulation = models.CharField(max_length=100, blank=True)
    post_titulation = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    initials = models.CharField(max_length=100, blank=True)
    institution = models.CharField(max_length=512, blank=True)
    department = models.CharField(max_length=512, blank=True)
    address_1 = models.CharField(max_length=512, blank=True)
    address_2 = models.CharField(max_length=512, blank=True)
    zip_code = models.CharField(max_length=100, blank=True)
    town = models.CharField(max_length=512, blank=True)
    state = models.CharField(max_length=512, blank=True)
    country = models.CharField(max_length=512, blank=True)
    phone = models.CharField(max_length=512, blank=True)
    cell_phone = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    homepage = models.URLField(blank=True)
    id_number = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        permissions = (
            ("edit_own_person", "Can edit own person"),
            ("delete_own_person", "Can delete own person"),
        )

    def __init__(self, *args, **kwargs):
        """Handles the optional 'name' argument for the Person model. It will be interpreted
        as a full name including possible titles and lineage. The name will be split into
        parts and stored in the corresponding fields. The 'name' argument is popped from the
        kwargs dictionary before calling the parent class constructor
        """
        name = kwargs.pop('name', None)
        super(Person, self).__init__(*args, **kwargs)
        # your code here
        if name:
            self.set_names(name, commit=False)

    def __str__(self):
        # Prints "First Middle von Last, Jr <pk:1>"
        full_name = self.get_full_name()
        return full_name + f" [pk:{self.pk}]"

    def get_full_name(self):
        full_name = ' '.join(part for part in (self.first, self.middle,
                                               self.prelast, self.last) if part)
        full_name = ', '.join(part for part in (full_name, self.lineage) if part)
        return full_name

    def get_pybtex_person(self):
        """ Should return a pybtex.Person instance. """
        return pybtexPerson(first=self.first.encode('latex'),
                            middle=self.middle.encode('latex'),
                            prelast=self.prelast.encode('latex'),
                            last=self.last.encode('latex'),
                            lineage=self.lineage.encode('latex'))

    def set_names(self, pers, commit=True):
        """Take pers argument (string or pybtexPerson) and use it to set name
        fields of the model.

        If pers is a string, it is supposed to be a name in a recognizable
        format e.g. "first middle last" or "last, first middle"
        It will be parsed by the pybtex algorithm, and then used to set the
        relevant fields.
        """

        if not isinstance(pers, pybtexPerson):
            pers = pybtexPerson(pers)

        # Define possible name parts to match
        names = ['first', 'middle', 'last', 'prelast', 'lineage']

        for n in names:
            setattr(self, n, ' '.join(getattr(pers, n)()))

        if pers.first():
            initial = pybtex_utils.bibtex_first_letter(pers.first()[0])
            #self.first_relaxed = utils.dk_unidecode(initial.decode('latex')).lower()
            self.first_relaxed = utils.dk_unidecode(initial).lower()
        if pers.last():
            #self.last_relaxed = utils.dk_unidecode(u' '.join(pers.last()).decode('latex')).lower()
            self.last_relaxed = utils.dk_unidecode(u' '.join(pers.last())).lower()

        if commit:
            self.save()

    def is_related_to_user(self, entity):
        """Check if this person is related to the current user.
        Presently checks for id_number (student number) or initials (staff/other)

        This functionality could be changed in future. Could even be a m2m
        relationship between person and user.

        """
        if (self.id_number.lower() == entity.username.lower() or
                self.initials.lower() == entity.username.lower()):
            return True
        else:
            return False

    def is_editable_by(self, entity):
        """Checks if entity (group or user) has permissions to edit this model instance"""

        # check for 'change_person' permission
        if has_model_permission(entity, self._meta.app_label, 'change', self._meta.verbose_name):
            return True

        # check for 'edit_own_person' permission
        if has_model_permission(entity, self._meta.app_label, 'edit_own', self._meta.verbose_name):
            # Test if user/entity is related to this model
            if self.is_related_to_user(entity):
                return True

        # if neither, return False
        return False

    def is_deletable_by(self, entity):
        """Checks if entity (group or user) has permissions to delete this model instance"""

        # check for 'delete_person' permission
        if has_model_permission(entity, self._meta.app_label, 'delete', self._meta.verbose_name):
            return True

        # check for 'delete_own_person' permission
        if has_model_permission(entity, self._meta.app_label, 'delete_own', self._meta.verbose_name):
            # Test if user/entity is related to this model
            if self.is_related_to_user(entity):
                return True

        # if neither, return False
        return False

    def sorted_authorships(self):
        """ Returns the list of publications this person has authored, sorted
        by year, report number and title"""
        pub_list = self.publication_authors.all()  # .order_by('-year').order_by('number')
        pub_list = pub_list.extra(select={'year_int': 'CAST(year AS INTEGER)'})
        pub_list = pub_list.extra(order_by=['-year_int', '-number', 'title'])
        return pub_list

    def sorted_supervisorships(self):
        """ Returns the list of publications this person has supervised, sorted
        by year, report number and title"""
        pub_list = self.publication_supervisors.all()  # .order_by('-year').order_by('number')
        pub_list = pub_list.extra(select={'year_int': 'CAST(year AS INTEGER)'})
        pub_list = pub_list.extra(order_by=['-year_int', '-number', 'title'])
        return pub_list

    def sorted_editorships(self):
        """ Returns the list of publications this person has edited, sorted
        by year, report number and title"""
        pub_list = self.publication_editors.all()  # .order_by('-year').order_by('number')
        pub_list = pub_list.extra(select={'year_int': 'CAST(year AS INTEGER)'})
        pub_list = pub_list.extra(order_by=['-year_int', '-number', 'title'])
        return pub_list


# ********************************************************************
# * PUBLICATIONTYPE, JOURNAL and KEYWORD classes starts here
# ********************************************************************

# QUESTION: Is the relation correct?
class Journal(models.Model):
    journal = models.CharField(max_length=100)   # f.ex. Geophysics, Near Surface Geophysics, Journal of Geophysical Exploration

    def __str__(self):
        return self.journal
    

class PubType(models.Model):
    type        = models.CharField(max_length=100)               # f.ex. BOOK, ARTICLE
    description = models.CharField(max_length=200, blank=True)   # Expalnation of usage
    req_fields  = models.CharField(max_length=200, blank=True)    # from bibtex definition
    opt_fields  = models.CharField(max_length=200, blank=True)    # from bibtex definition (in practice all
                                                                   # non-required fields will be optional

    def __str__(self):
        return self.type


class Topic(models.Model):
    topic = models.CharField(max_length=100)

    def __str__(self):
        return self.topic


class Keyword(models.Model):
    keyword = models.CharField(max_length=100)

    def __str__(self):
        return self.keyword


class ImageObject(BaseModel):
    upload_to = None     # If set, this value should be used in upload_to function
    original_URL = models.CharField(max_length=1000, blank=True)
                         # Temporary field for handling multiple registrations of the same
                         # file in the import from MySQL RoadDB database.
                         # Should be deleted when the import is finished and checked!
    image = models.ImageField(upload_to=get_image_path)
    caption = models.TextField(max_length=1000)

    def filesize(self):
        unit = 'bytes'

        try:
            fsize = self.image.size
        except:
            return " inaccessible! "

        if fsize > 1024 * 1024 * 1024:
            fsize = fsize / 1024 / 1024 / 1024
            unit = 'Gb'
        elif fsize > 1024 * 1024:
            fsize = fsize / 1024 / 1024
            unit = 'Mb'
        elif fsize > 1024:
            fsize = fsize / 1024
            unit = 'kb'

        return "{0:.1f} {1}".format(fsize, unit)

    def filename(self):
        return os.path.basename(self.image.name)

# ********************************************************************
# * PUBLICATIONTYPE, JOURNAL and KEYWORD classes ends here
# ********************************************************************        return self.topic



class FileObject(BaseModel):
    upload_to = None  # If set, this value should be used in upload_to function
    original_URL = models.CharField(max_length=1000, blank=True)
    file = models.FileField(upload_to=get_file_path, max_length=1000, blank=False)
    description = models.TextField(max_length=65535, blank=True)

    # QUESTION: What is this?
    def filesize(self):
        try:
            file_size = self.file.size
        except:
            return "inaccessible!"

        if file_size > 1024 * 1024 * 1024:
            file_size = file_size / 1024 / 1024 / 1024
            unit = 'GB'
        elif file_size > 1024 * 1024:
            file_size = file_size / 1024 / 1024
            unit = 'MB'
        elif file_size > 1024:
            file_size = file_size / 1024
            unit = 'KB'
        else:
            file_size = file_size
            unit = 'bytes'

        return "{0:.1f} {1}".format(file_size, unit)
    
    def filename(self):
        return os.path.basename(self.file.name)


class URLObject(BaseModel):
    URL = models.URLField(blank=False)
    description = models.CharField(max_length=1000, blank=True)
    linktext = models.CharField(max_length=50, blank=True)


class Publication(BaseModel):
    not_bibtex = ('supervisor', 'grade', 'quality', 'created', 'modified', 'modified_by')
    
    key = models.CharField(max_length=100, blank=True)
    type = models.ForeignKey(PubType, on_delete=models.PROTECT)
    # Use plural variable name for many-to-many relationship
    authors = models.ManyToManyField(Person, through='Authorship', related_name='publication_author', blank=True, default=None)
    editors = models.ManyToManyField(Person, through='Editorship', related_name='publication_editor', blank=True, default=None)
    supervisors = models.ManyToManyField(Person, through='Supervisorship', related_name='publication_supervisor', blank=True, default=None)
    publication_topics = models.ManyToManyField(Topic, through='Topicship', blank=True, default=None)
    publication_keywords = models.ManyToManyField(Keyword, through='Keywordship', blank=True, default=None)
    appendices = models.ManyToManyField(FileObject, through='Appendenciesship', related_name='publication_appendices', blank=True, default=None)
    URLs = models.ManyToManyField(URLObject, through='PublicationURLObjectship', blank=True, default=None)
    file = models.OneToOneField(FileObject, blank=False, null=True, on_delete=models.CASCADE)
    journal = models.ForeignKey(Journal, blank=True, default=None, on_delete=models.SET_NULL, related_name='publications', null=True)
    booktitle = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255, blank=True)
    crossref = models.CharField(max_length=255, blank=True)
    chapter = models.CharField(max_length=255, blank=True)
    volume = models.CharField(max_length=255, blank=True)
    number = models.CharField(max_length=255, blank=True)
    institution = models.CharField(max_length=255, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    school = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    edition = models.CharField(max_length=255, blank=True)
    pages = models.CharField(max_length=100, blank=True)
    month = models.CharField(max_length=100, blank=True)
    year = models.IntegerField(blank=True)
    DOI = models.CharField(max_length=255, blank=True)
    ISBN = models.CharField(max_length=255, blank=True)
    ISBN13 = models.CharField(max_length=255, blank=True)
    ISSN = models.CharField(max_length=255, blank=True)
    note = models.TextField(max_length=255, blank=True)
    series = models.CharField(max_length=255, blank=True)
    # abstract = models.TextField(max_length=255, blank=True)
    abstract = models.TextField(blank=True)
    remark = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    howpublished = models.CharField(max_length=255, blank=True)
    comment = models.TextField(max_length=255, blank=True)
    timestamp = models.CharField(max_length=100, blank=True)
    grade = models.CharField(max_length=100, blank=True, null=True, default=None)
    verified = models.BooleanField(blank=False, default=False)
    quality = models.SmallIntegerField(choices=quality_flags, default=CREATED)

    _key = None   # a cache for temporary key

    class Meta:
        permissions = (
            ("edit_own_publication", "Can edit own publications"),
            ("delete_own_publication", "Can delete own publications"),
            ("verify_publication", "Can verify publications"),
        )

    def __str__(self):
        # Workaround to avoid recursion error. 
        # We use a temporary string representation, stored in _key
        # this proper key representation is generated if possible (not a new publication)

        print(f"Publication: key: {self.key}")    
        if (not self.key) and (self._key is None):
            if not self.pk:
                return 'New publication instance'
            else:
                self._key = f'pk:{self.pk}'
            self.create_key()

        if self.key:
            return self.key
        else:
            return self._key

    def create_key(self):
        """Creates are unique reference key (bibtext key) for the publication. 
        The key is based on the first author's last name and the year of publication.
        If the key already exists, a letter is added after the year to make it unique."""
        
        success = False
        key = None

        if not self.pk:
            # this is a new intstance, so it has no relationships to other models yet
            # it also has no primary key, so we cannot create a key yet
            return
        elif self.authors.all():
            alphabet = ['']
            alphabet.extend(list('abcdefghijklmnopqrstuvwxyz'))
            if self.type.type == 'STUDENTREPORT':
                for letter in alphabet:
                    key = '{0}({1}{2})'.format(self.sorted_authors()[0].last, self.year, letter)
                    if not Publication.objects.filter(key=key):
                        success = True
                        break
                if not success:
                    raise ValueError('Could not construct valid key!')
                
        if not key:
            key = f'pk:{self.pk}'

        if success:
            self.key = key
            self.save()
        else:
            self._key = key
            # Dont save the key if it simply represents the pk
    
    def sorted_authors(self):
        """ Returns the authors as a list of Person instances sorted
        according to the author index (so in the correct order from
        the publication. """
        return self.authors.all().order_by('authorship__author_id')

    def sorted_authorships(self):
        """ Returns the authorships as a list of Authorship instances sorted
        according to the author index (so in the correct order from
        the publication. """
        return self.authorship_set.all().order_by('author_id')

    def sorted_supervisors(self):
        """ Returns the supervisors as a list of Person instances sorted
        according to the supervisor index (so in the correct order from
        the publication. """
        return self.supervisor.all().order_by('supervisorship__supervisor_id')

    def sorted_supervisorships(self):
        """ Returns the supervisorships as a list of supervisorship instances sorted
        according to the supervisor index (so in the correct order from
        the publication. """
        return self.supervisorship_set.all().order_by('supervisor_id')

    def sorted_editors(self):
        """ Returns the editors as a list of Person instances sorted
        according to the editor index (so in the correct order from
        the publication. """
        return self.editor.all().order_by('editorship__editor_id')

    def sorted_editorships(self):
        """ Returns the editorships as a list of editorship instances sorted
        according to the editor index (so in the correct order from
        the publication. """
        return self.editorship_set.all().order_by('editor_id')

    def is_editable_by(self, entity):
        """Checks if entity (group or user) has permissions to edit this model instance"""

        # check for 'change_publication' permission
        if has_model_permission(entity, self._meta.app_label, 'change', self._meta.verbose_name):
            return True

        # check for 'edit_own_publication' permission
        if has_model_permission(entity, self._meta.app_label, 'edit_own', self._meta.verbose_name):
            # Test if user/entity is related to this model
            persons = self.author.all() | self.supervisor.all() | self.editor.all()
            for p in persons:
                if p.is_related_to_user(entity):
                    return True

        # if neither, return False
        return False

    def is_deletable_by(self, entity):
        """Checks if entity (group or user) has permissions to delete this model instance"""

        # check for 'delete_publication' permission
        if has_model_permission(entity, self._meta.app_label, 'delete', self._meta.verbose_name):
            return True

        # check for 'delete_own_publication' permission
        if has_model_permission(entity, self._meta.app_label, 'delete_own', self._meta.verbose_name):
            # Test if user/entity is related to this model
            persons = self.author.all() | self.supervisor.all() | self.editor.all()
            for p in persons:
                if p.is_related_to_user(entity):
                    return True

        # if neither, return False
        return False

    def is_verifiable_by(self, entity):
        """Checks if entity (group or user) has permissions to verify this model instance"""

        # check for 'delete_publication' permission
        if has_model_permission(entity, self._meta.app_label, 'verify', self._meta.verbose_name):
            return True

        # if neither, return False
        return False


class Feature(BaseModel):
    PHOTO =             'PHOTO'
    SAMPLE =            'SAMPLE'
    BOREHOLE =          'BOREHOLE'
    GEOPHYSICAL_DATA =  'GEOPHYSICAL DATA'
    FIELD_MEASUREMENT = 'FIELD MEASUREMENT'
    LAB_MEASUREMENT =   'LAB MEASUREMENT'
    RESOURCE =          'RESOURCE'
    OTHER =             'OTHER'

    feature_types = (
        (PHOTO,             'Photo'),
        (SAMPLE,            'Sample'),
        (BOREHOLE,          'Borehole'),
        (GEOPHYSICAL_DATA,  'Geophysical data'),
        (FIELD_MEASUREMENT, 'Field measurement'),
        (LAB_MEASUREMENT,   'Lab measurement'),
        (RESOURCE,          'Resource'),
        (OTHER,             'Other'),
    )

    pos_qualities = (
        ('Approximate', 'Approximate'),
        ('GPS (phase)', 'GPS (phase)'),
        ('GPS (code)', 'GPS (code)'),
        ('Unknown', 'Unknown'),
    )


    name          = models.CharField(max_length=100, blank=True)
    type          = models.CharField(max_length=30, choices=feature_types, default='OTHER', blank=True)
    area          = models.CharField(max_length=100, blank=True)
    date          = models.DateField(blank=True)
    direction     = models.CharField(max_length=100, blank=True)
    description   = models.TextField(max_length=65535, blank=True)
    comment       = models.TextField(max_length=65535, blank=True)
    URLs          = models.ManyToManyField(URLObject, blank=True)
    files         = models.ManyToManyField(FileObject, blank=True)
    images        = models.ManyToManyField(ImageObject, through='ImageObjectship', blank=True)

    points        = geo_models.MultiPointField(srid=4326, blank=True, null=True)
    lines         = geo_models.MultiLineStringField(srid=4326, blank=True, null=True)
    polys         = geo_models.MultiPolygonField(srid=4326, blank=True, null=True)

    pos_quality   = models.CharField(max_length=30, choices=pos_qualities, default='Unknown', blank=True)
    quality       = models.SmallIntegerField(choices=quality_flags, default=CREATED)
    publications  = models.ManyToManyField(Publication, blank=True)

    class Meta:
        permissions = (
            ("edit_own_feature", "Can edit own featuress"),
            ("delete_own_feature", "Can delete own features"),
        )

    def __str__(self):
        return '%s %s' % (self.name, 'Geometry')

    @classmethod
    def feature_type_list(self):
        return [f[0] for f in self.feature_types]

    def is_editable_by(self, entity):
        """Checks if entity (group or user) has permissions to edit this model instance"""

        # check for 'change_' permission
        if has_model_permission(entity, self._meta.app_label, 'change', self._meta.verbose_name):
            return True

        # check for 'edit_own_' permission
        if has_model_permission(entity, self._meta.app_label, 'edit_own', self._meta.verbose_name):
            # Test if user/entity is related to this model
            if hasattr(entity, 'username'):
                if entity.username == self.created_by.username or entity.username == self.modified_by.username:
                    return True

        # if neither, return False
        return False

    def is_deletable_by(self, entity):
        """Checks if entity (group or user) has permissions to delete this model instance"""

        # check for 'delete_' permission
        if has_model_permission(entity, self._meta.app_label, 'delete', self._meta.verbose_name):
            return True

        # check for 'delete_own_' permission
        if has_model_permission(entity, self._meta.app_label, 'delete_own', self._meta.verbose_name):
            # Test if user/entity is related to this model
            if hasattr(entity, 'username'):
                if entity.username == self.created_by.username or entity.username == self.modified_by.username:
                    return True

        # if neither, return False
        return False

class ImageObjectship(models.Model):
    imageobject = models.ForeignKey(ImageObject, on_delete=models.CASCADE)
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE)

class Topicship(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)

class Keywordship(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE)



class Personship(models.Model):
    """Intended for subclassing to Authorship, Editorship, Supervisorship etc."""
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)

    # Fields used for automatic person matching on import
    exact_match = models.BooleanField(default=False)   # True if one or more exact matches at time of import
    multiple_match = models.BooleanField(default=False)   # True if more than one relaxed match at time of import
    relaxed_match = models.BooleanField(default=False)   # True if one or more relaxed matches at time of import - but no exact matches
    match_string = models.CharField(max_length=100, blank=True)   # Not used, what was the intention

    class Meta:
        abstract = True

    def clear_match_indicators(self, commit=True):
        self.exact_match = False
        self.relaxed_match = False
        self.multiple_match = False
        self.match_string = ""
        if commit:
            self.save()



class Authorship(Personship):
    author_id = models.IntegerField(null=True, default=None)


class Editorship(Personship):
    editor_id = models.IntegerField(null=True, default=None)


class Supervisorship(Personship):
    supervisor_id = models.IntegerField(null=True, default=None)


class Appendenciesship(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    fileobject = models.ForeignKey(FileObject, on_delete=models.CASCADE)


class PublicationURLObjectship(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    URLs = models.ForeignKey(URLObject, on_delete=models.CASCADE)


class AddPubFields(models.Model):
    # Model to handle undefined bibtex fields or mulitple instances
    # of the same field
    publication   = models.ForeignKey(Publication, on_delete=models.SET_NULL, null=True)
    bibtexfield   = models.CharField(max_length=100)
    content       = models.CharField(max_length=1000, blank=True)