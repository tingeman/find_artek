import os

from django.db import models
from django.contrib.auth.models import User
from django.contrib.gis.db import models as geo_models


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
    
def has_model_permission( entity, app, perm, model ):
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

# ********************************************************************
# * PUBLICATIONTYPE, JOURNAL and KEYWORD classes starts here
# ********************************************************************

# QUESTION: Is the relation correct?
class Journal(models.Model):
    journal = models.CharField(max_length=100)   # f.ex. Geophysics, Near Surface Geophysics, Journal of Geophysical Exploration

    def __unicode__(self):
        return self.journal
    

class PubType(models.Model):
    type        = models.CharField(max_length=100)               # f.ex. BOOK, ARTICLE
    description = models.CharField(max_length=200, blank=True)   # Expalnation of usage
    req_fields  = models.CharField(max_length=200, blank=True)    # from bibtex definition
    opt_fields  = models.CharField(max_length=200, blank=True)    # from bibtex definition (in practice all
                                                                   # non-required fields will be optional

    def __unicode__(self):
        return self.type


class Topic(models.Model):
    topic = models.CharField(max_length=100)

    def __unicode__(self):
        return self.topic


class Keyword(models.Model):
    keyword = models.CharField(max_length=100)

    def __unicode__(self):
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
    abstract = models.TextField(max_length=255, blank=True)
    remark = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    howpublished = models.CharField(max_length=255, blank=True)
    comment = models.TextField(max_length=255, blank=True)
    timestamp = models.CharField(max_length=100, blank=True)
    grade = models.CharField(max_length=100, blank=True, null=True, default=None)
    verified = models.BooleanField(blank=False, default=False)
    quality = models.SmallIntegerField(choices=quality_flags, default=CREATED)

    class Meta:
        permissions = (
            ("edit_own_publication", "Can edit own publications"),
            ("delete_own_publication", "Can delete own publications"),
            ("verify_publication", "Can verify publications"),
        )

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

    def __unicode__(self):
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

class Authorship(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    author_id = models.IntegerField(null=True, default=None)

    # Fields used for automatic person matching on import
    exact_match = models.BooleanField(default=False)
    multiple_match = models.BooleanField(default=False)
    relaxed_match = models.BooleanField(default=False)
    match_string = models.CharField(max_length=100, blank=True)

    def clear_match_indicators(self, commit=True):
        self.exact_match = False
        self.relaxed_match = False
        self.multiple_match = False
        self.match_string = ""
        if commit:
            self.save()

class Editorship(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    editor_id = models.IntegerField(null=True, default=None)
    exact_match = models.BooleanField(default=False)   # True if one or more exact matches at time of import
    multiple_match = models.BooleanField(default=False)   # True if more than one relaxed match at time of import
    relaxed_match = models.BooleanField(default=False)   # True if one or more relaxed matches at time of import - but no exact matches
    match_string = models.CharField(max_length=100, blank=True)   # Not used, what was the intention

    def clear_match_indicators(self, commit=True):
        self.exact_match = False
        self.relaxed_match = False
        self.multiple_match = False
        self.match_string = ""
        if commit:
            self.save()

class Appendenciesship(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    fileobject = models.ForeignKey(FileObject, on_delete=models.CASCADE)

class Supervisorship(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    supervisor_id = models.IntegerField(null=True, default=None)
    # Fields used for automatic person matching on import
    exact_match = models.BooleanField(default=False)             
    multiple_match = models.BooleanField(default=False)          
    relaxed_match = models.BooleanField(default=False)           
    match_string = models.CharField(max_length=100, blank=True)  

    def clear_match_indicators(self, commit=True):
        self.exact_match = False
        self.relaxed_match = False
        self.multiple_match = False
        self.match_string = ""
        if commit:
            self.save()

class PublicationURLObjectship(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    URLs = models.ForeignKey(URLObject, on_delete=models.CASCADE)



class AddPubFields(models.Model):
    # Model to handle undefined bibtex fields or mulitple instances
    # of the same field
    publication   = models.ForeignKey(Publication, on_delete=models.SET_NULL, null=True)
    bibtexfield   = models.CharField(max_length=100)
    content       = models.CharField(max_length=1000, blank=True)