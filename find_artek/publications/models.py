# -*- coding: utf_8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"


from django.contrib.gis.db import models
from django.contrib.auth.models import User
# https://code.djangoproject.com/wiki/CookBookNewformsAdminAndUser
# http://stackoverflow.com/questions/862522/django-populate-user-id-when-saving-a-model/12977709#12977709
# http://www.b-list.org/weblog/2006/nov/02/django-tips-auto-populated-fields/

#from django.db.models import Q
#import re
import os.path
#from unidecode import unidecode
import pdb

#from find_artek.publications import person_utils
from find_artek.publications import utils
from pybtex.database import Person as pybtexPerson
from pybtex.bibtex import utils as pybtex_utils     # functions for splitting strings in a tex aware fashion etc.
from find_artek.publications import latex_codec


def has_model_permission( entity, app, perm, model ):
    """Checks if entity (user or group) has specified permission for the model passed

    entity:     a user or group object
    model:      string representation of model (must be lower case)
    perm:       permission (string). '_model' will be automatically added
    app:        name of the app the model is defined in.
    """
    return entity.has_perm( "{0}.{1}_{2}".format( app, perm, model ) )



# Create your models here.

CURRENT =   00
CREATED =   10
UPDATED =   20
REJECTED =  40
OBSOLETE =  50

quality_flags = (
    (CURRENT, 'Current'),
    (CREATED, 'Created'),
    (UPDATED, 'Changed'),
    (REJECTED, 'Rejected'),
    (OBSOLETE, 'Obsolete'),
)


class BaseModel(models.Model):
    # New base class, that automatically handles created_date and modified_date.
    created_date  = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    created_by    = models.ForeignKey(User, editable=False, related_name="%(class)s_created")
    modified_by   = models.ForeignKey(User, editable=False, related_name="%(class)s_modified")

#    modified_by    = models.ForeignKey("self", blank=True, null=True, default=None,
#                                       related_name='person_modifier',
#                                       on_delete=models.SET_NULL)

    class Meta:
        abstract = True


# ********************************************************************
# * additional File, URL and Image CLASSES
# ********************************************************************

""" The idea below, is to allow upload_to function of the File or Image fields
    to provide a proper path using the report number, if added to an ARTEK report
    or the publication bibtex-key if added to another publications, or maybe a
    project slug-name if added to a project.

    The problem is that the ManyToMany relations are not known at the time of
    saving the Image/File, only after the insertion into the "through"-table
    which happens later.

    There could be two solutions:

    1) Like attempted two ways below, use pre_save signal to avoid saving the
       File/Image, and store it for later, then upon m2m_changed signal do the
       actual saving of the File/Image, which will invoke the upload_to function.
       The challenge here is that FileObject could also be attached to our
       Publication model through a OneToOne field, which does not send the
       m2m_changed signal... how to solve that?

    2) Another method could be to assign a temporary path in File/Image upload_to
       and then iterate over all Files/Images after saving to either Publication
       or GeoObject, and move the files to a proper location...
       But how do we achieve this? A post_save signal for the Publication table
       and GeoObjects table? How do we avoid reading the file into memory, and
       then saving it back out, but just move it in the file-system?
       Maybe using:

       with open(FileObject.file.name) as f:
           newfile = File(f)
       FileObject.file.save(new_file_path, newfile)

       or

       new_name = '/some/path'
       FileObject.file.save(new_name, File(FileObject.file.file))

       ?

       inspiration:
       http://joshourisman.com/2008/11/18/dynamic-upload-path-django-filefieldimagefield/
       http://djangosnippets.org/snippets/1129/
       http://djangosnippets.org/snippets/469/
"""

#from django.db.models.signals import m2m_changed, pre_save
#from django.dispatch import receiver
#
#_UNSAVED_FILEFIELD = 'unsaved_filefield'
#_UNSAVED_IMAGEFIELD = 'unsaved_imagefield'
#
#def skip_saving(sender, **kwargs):
#    if not instance.pk:
#        if sender == FileObject and not hasattr(instance, _UNSAVED_FILEFIELD):
#            setattr(instance, _UNSAVED_FILEFIELD, instance.file)
#            instance.file = None
#        if sender == ImageObject and not hasattr(instance, _UNSAVED_IMAGEFIELD):
#            setattr(instance, _UNSAVED_IMAGEFIELD, instance.image)
#            instance.image = None
#
#pre_save.connect(skip_saving, sender=FileObject)
#pre_save.connect(skip_saving, sender=ImageObject)
#
#def save_on_m2m(sender, instance, action, **kwargs):
#    if action == 'post_add':
#        if hasattr(instance, _UNSAVED_FILEFIELD):
#            instance.file = getattr(instance, _UNSAVED_FILEFIELD)
#            instance.save()
#            instance.__dict__.pop(_UNSAVED_FILEFIELD)
#        if hasattr(instance, _UNSAVED_IMAGEFIELD):
#            instance.image = getattr(instance, _UNSAVED_IMAGEFIELD)
#            instance.save()
#            instance.__dict__.pop(_UNSAVED_IMAGEFIELD)
#
#
#m2m_changed.connect(save_on_m2m, sender=GeoObjects.files.through)
#m2m_changed.connect(save_on_m2m, sender=GeoObjects.images.through)
#m2m_changed.connect(save_on_m2m, sender=Publications.appendices.through)
#
#
#m2m_changed.connect(skip_saving, sender=ImageObject)
#
#
#
#@receiver(pre_save, sender=FileObject)
#def skip_saving_fileobject(sender, instance, **kwargs):
#    if not instance.pk and not hasattr(instance, _UNSAVED_FILEFIELD):
#        setattr(instance, _UNSAVED_FILEFIELD, instance.file)
#        instance.image = None
#
#@receiver(m2m_changed, sender=FileObject.publications.through)
#def save_file_on_m2m(sender, instance, action, **kwargs):
#    if action == 'post_add' and hasattr(instance, _UNSAVED_FILEFIELD):
#        instance.image = getattr(instance, _UNSAVED_FILEFIELD)
#        instance.save()
#        instance.__dict__.pop(_UNSAVED_FILEFIELD)
#


def get_file_path(obj, filename):
    if obj.upload_to:
        filename = os.path.basename(filename)
        return os.path.join(obj.upload_to, filename)
    else:
        print "Trying to auto-generate file path! Failure!"
        raise NotImplementedError('get_file_path is not implemented for automatic path generation!')


def get_image_path(obj, filename):
    if obj.upload_to:
        filename = os.path.basename(filename)
        return os.path.join(obj.upload_to, filename)
    else:
        print "Trying to auto-generate image path! Failure!"
        raise NotImplementedError('get_image_path is not implemented for automatic path generation!')


class URLObject(BaseModel):
    URL = models.URLField(blank=False)
    description = models.CharField(max_length=1000, blank=True)
    linktext = models.CharField(max_length=50, blank=True)


class FileObject(BaseModel):
    upload_to = None     # If set, this value should be used in upload_to function
    original_URL = models.CharField(max_length=1000, blank=True)
                         # Temporary field for handling multiple registrations of the same
                         # file in the import from MySQL RoadDB database.
                         # Should be deleted when the import is finished and checked!
    file = models.FileField(upload_to=get_file_path)
    description = models.TextField(max_length=65535, blank=True)

    def filesize(self):
        unit = 'bytes'

        try:
            fsize = self.file.size
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
        return os.path.basename(self.file.name)


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
# * PERSON Class
# ********************************************************************

class Person(BaseModel):
    first_relaxed     = models.CharField(max_length=10, blank=True)      # first initial, lower case, no special characters
    last_relaxed      = models.CharField(max_length=100, blank=True)     # last name, lower case, no special characters
    first             = models.CharField(max_length=100)     # Allows LaTeX escaped characters
    middle            = models.CharField(max_length=100, blank=True)     # Allows LaTeX escaped characters
    prelast           = models.CharField(max_length=100, blank=True)     # Allows LaTeX escaped characters
    last              = models.CharField(max_length=100)     # Allows LaTeX escaped characters
    lineage           = models.CharField(max_length=100, blank=True)     # [Jr, Sr]
    pre_titulation    = models.CharField(max_length=100, blank=True)     # [Dr., PhD, Mr, etc]
    post_titulation   = models.CharField(max_length=100, blank=True)     # [PhD, etc.?]
    position          = models.CharField(max_length=100, blank=True)     # [Professor, student...]
    initials          = models.CharField(max_length=100, blank=True)
    institution       = models.CharField(max_length=512, blank=True)
    department        = models.CharField(max_length=512, blank=True)
    address_1         = models.CharField(max_length=512, blank=True)
    address_2         = models.CharField(max_length=512, blank=True)
    zip_code          = models.CharField(max_length=100, blank=True)
    town              = models.CharField(max_length=512, blank=True)
    state             = models.CharField(max_length=512, blank=True)
    country           = models.CharField(max_length=512, blank=True)
    phone             = models.CharField(max_length=512, blank=True)
    cell_phone        = models.CharField(max_length=100, blank=True)
    email             = models.EmailField(blank=True)
    homepage          = models.URLField(blank=True)
    id_number         = models.CharField(max_length=100, blank=True)   # [student_number, employee_number]
    note              = models.CharField(max_length=65535, blank=True)

    # Additional fields for quality control

    quality           = models.SmallIntegerField(choices=quality_flags,
                                                 default=CREATED)

    class Meta:
        permissions = (
            ("edit_own_person", "Can edit own person"),
            ("delete_own_person", "Can delete own person"),
        )

    # Methods

    def __init__(self, *args, **kwargs):
        name = kwargs.pop('name', None)
        super(Person, self).__init__(*args, **kwargs)
        # your code here
        if name:
            self.set_names(name, commit=False)

    def __unicode__(self):
        # First Middle von Last, Jr
        full_name = ' '.join(part for part in (self.first, self.middle,
                                               self.prelast, self.last) if part)
        return ', '.join(part for part in (full_name, self.lineage) if part)

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
            try:
                setattr(self, n, ' '.join(getattr(pers, n)()))
            except:
                pdb.set_trace()

        if pers.first():
            initial = pybtex_utils.bibtex_first_letter(pers.first()[0])
            self.first_relaxed = utils.dk_unidecode(initial.decode('latex')).lower()
        if pers.last():
            self.last_relaxed = utils.dk_unidecode(u' '.join(pers.last()).decode('latex')).lower()

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
# * PUBLICATIONTYPE, JOURNAL and KEYWORD classes
# ********************************************************************

class PubType(models.Model):
    type        = models.CharField(max_length=100)               # f.ex. BOOK, ARTICLE
    description = models.CharField(max_length=200, blank=True)   # Expalnation of usage
    req_fields  = models.CharField(max_length=65535, blank=True)    # from bibtex definition
    opt_fields  = models.CharField(max_length=65535, blank=True)    # from bibtex definition (in practice all
                                                                   # non-required fields will be optional

    def __unicode__(self):
        return self.type


class Journal(models.Model):
    journal = models.CharField(max_length=100)       # f.ex. Geophysics, Near Surface Geophysics, Journal of Geophysical Exploration

    def __unicode__(self):
        return self.journal


class Keyword(models.Model):
    keyword = models.CharField(max_length=100)

    def __unicode__(self):
        return self.keyword


class Topic(models.Model):
    topic = models.CharField(max_length=100)

    def __unicode__(self):
        return self.topic

# ********************************************************************
# * PUBLICATION Class
# ********************************************************************

class Publication(BaseModel):
    key             = models.CharField(max_length=100, blank=True)          # PK Lastname#Year[letter]
    type            = models.ForeignKey(PubType)                            # f.ex. BOOK, ARTICLE
    author          = models.ManyToManyField(Person, through='Authorship',
                                             related_name='publication_authors',
                                             blank=True,null=True, default=None)
    editor          = models.ManyToManyField(Person, through='Editorship',
                                             related_name='publication_editors',
                                             blank=True,null=True, default=None)
    booktitle       = models.CharField(max_length=65535, blank=True)
    title           = models.CharField(max_length=65535, blank=True)
    crossref        = models.CharField(max_length=65535, blank=True)
    chapter         = models.CharField(max_length=65535, blank=True)
    journal         = models.ForeignKey(Journal, blank=True, null=True, default=None,
                                        on_delete=models.SET_NULL)
    volume          = models.CharField(max_length=100, blank=True)
    number          = models.CharField(max_length=100, blank=True)
    institution     = models.CharField(max_length=65535, blank=True)
    organization    = models.CharField(max_length=65535, blank=True)
    publisher       = models.CharField(max_length=65535, blank=True)
    school          = models.CharField(max_length=65535, blank=True)
    address         = models.CharField(max_length=65535, blank=True)
    edition         = models.CharField(max_length=65535, blank=True)
    pages           = models.CharField(max_length=100, blank=True)
    month           = models.CharField(max_length=100, blank=True)
    year            = models.CharField(max_length=100, blank=True)
    DOI             = models.CharField(max_length=65535, blank=True)
    ISBN            = models.CharField(max_length=65535, blank=True)
    ISBN13          = models.CharField(max_length=65535, blank=True)
    ISSN            = models.CharField(max_length=65535, blank=True)
    note            = models.TextField(max_length=65535, blank=True)
    series          = models.CharField(max_length=65535, blank=True)
    abstract        = models.TextField(max_length=65535, blank=True)
    remark          = models.CharField(max_length=65535, blank=True)
    subject         = models.CharField(max_length=65535, blank=True)   # Could be a short description of the report
    howpublished    = models.CharField(max_length=65535, blank=True)
    comment         = models.TextField(max_length=65535, blank=True)
    keywords        = models.ManyToManyField(Keyword, blank=True, null=True,
                                            related_name='publication_keywords',
                                            default=None)
    URLs            = models.ManyToManyField(URLObject, blank=True, null=True, default=None)

    file            = models.OneToOneField(FileObject, blank=True, null=True,
                                            default=None, on_delete=models.SET_NULL)
    appendices      = models.ManyToManyField(FileObject, blank=True, null=True, default=None,
                                             related_name='publication_appendices')
    timestamp       = models.CharField(max_length=100, blank=True)     # Should this be a DateTimeField
#    entry          = models.CharField(max_length=65535, blank=True)   # Should we have the Full bibtex entry (needed?)

    topics          = models.ManyToManyField(Topic, blank=True, null=True, default=None)

    # Additional fields for student reports
    supervisor      = models.ManyToManyField(Person, through='Supervisorship',
                                            related_name='publication_supervisors',
                                            blank=True, null=True, default=None)
    grade           = models.CharField(max_length=100, blank=True, null=True, default=None)
    #appendixURL     = models.URLField(blank=True)

    # Support for undefined fields or multiple instances of same field:
    #    AddPubField-model (Additional Publication Field) has a ForeignKey relationship to
    #    this model (Publication-model)

    # Additional fields for quality control

    verified       = models.BooleanField(blank=False, default=False)
    quality        = models.SmallIntegerField(choices=quality_flags,
                                         default=CREATED)

    # Dictionary of fields not in BibTex
    not_bibtex = ('supervisor', 'grade', 'quality', 'created', 'modified', 'modified_by',)
    # any others ??

    class Meta:
        permissions = (
            ("edit_own_publication", "Can edit own publications"),
            ("delete_own_publication", "Can delete own publications"),
            ("verify_publication", "Can verify publications"),
        )

    # Methods

    def __unicode__(self):
        if not self.key:
            self.create_key()
        return self.key

    def create_key(self):
        if not self.author.all():
            return

        alphabet = ['']
        alphabet.extend(list('abcdefghijklmnopqrstuvwxyz'))
        success = False
        if self.type.type == 'STUDENTREPORT':
            for letter in alphabet:
                key = '{0}({1}{2})'.format(self.author.all().order_by('authorship__author_id')[0].last,
                                            self.year, letter)
                if not Publication.objects.filter(key=key):
                    success = True
                    break

            if not success:
                raise ValueError('Could not construct valid key!')
        else:
            key = ''

        if success:
            self.key = key
            self.save()

    def sorted_authors(self):
        """ Returns the authors as a list of Person instances sorted
        according to the author index (so in the correct order from
        the publication. """
        return self.author.all().order_by('authorship__author_id')

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

    @staticmethod
    def get_type(self):
        """ Returns the bibtex style publication type. """
        return self.type.type

    @staticmethod
    def get_reference(self):
        """ Should return a fully formatted reference, according to bibtex
        standards. Could take an option to format as plain text, or valid
        html with mark-up. Should call pybtex for formatting. """
        pass

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


class Authorship(models.Model):
    person = models.ForeignKey(Person)
    publication = models.ForeignKey(Publication)
    author_id = models.IntegerField(null=True, default=None)
    # Fields used for automatic person matching on import
    exact_match = models.BooleanField(default=False)             # True if one or more exact matches at time of import
    multiple_match = models.BooleanField(default=False)          # True if more than one relaxed match at time of import
    relaxed_match = models.BooleanField(default=False)           # True if one or more relaxed matches at time of import - but no exact matches
    match_string = models.CharField(max_length=100, blank=True)  # Not used ?????  What was the intention

    def clear_match_indicators(self, commit=True):
        self.exact_match = False
        self.relaxed_match = False
        self.multiple_match = False
        self.match_string = ""
        if commit:
            self.save()


class Editorship(models.Model):
    person = models.ForeignKey(Person)
    publication = models.ForeignKey(Publication)
    editor_id = models.IntegerField(null=True, default=None)
    # Fields used for automatic person matching on import
    exact_match = models.BooleanField(default=False)             # True if one or more exact matches at time of import
    multiple_match = models.BooleanField(default=False)          # True if more than one relaxed match at time of import
    relaxed_match = models.BooleanField(default=False)           # True if one or more relaxed matches at time of import - but no exact matches
    match_string = models.CharField(max_length=100, blank=True)  # Not used ?????  What was the intention

    def clear_match_indicators(self, commit=True):
        self.exact_match = False
        self.relaxed_match = False
        self.multiple_match = False
        self.match_string = ""
        if commit:
            self.save()


class Supervisorship(models.Model):
    person = models.ForeignKey(Person)
    publication = models.ForeignKey(Publication)
    supervisor_id = models.IntegerField(null=True, default=None)
    # Fields used for automatic person matching on import
    exact_match = models.BooleanField(default=False)             # True if one or more exact matches at time of import
    multiple_match = models.BooleanField(default=False)          # True if more than one relaxed match at time of import
    relaxed_match = models.BooleanField(default=False)           # True if one or more relaxed matches at time of import - but no exact matches
    match_string = models.CharField(max_length=100, blank=True)  # Not used ?????  What was the intention

    def clear_match_indicators(self, commit=True):
        self.exact_match = False
        self.relaxed_match = False
        self.multiple_match = False
        self.match_string = ""
        if commit:
            self.save()


class AddPubFields(models.Model):
    # Model to handle undefined bibtex fields or mulitple instances
    # of the same field
    publication   = models.ForeignKey(Publication)
    bibtexfield   = models.CharField(max_length=100)
    content       = models.CharField(max_length=65535, blank=True)



# ********************************************************************
# * GEOOBJECT MODEL and related FUNCTIONS
# ********************************************************************

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
    type          = models.CharField(max_length=30, choices=feature_types,
                                        default='OTHER', blank=True)
    area          = models.CharField(max_length=100, blank=True)
    date          = models.DateField(blank=True, null=True)
    direction     = models.CharField(max_length=100, blank=True)
    description   = models.TextField(max_length=65535, blank=True)
    comment       = models.TextField(max_length=65535, blank=True)
    URLs          = models.ManyToManyField(URLObject, null=True, blank=True)
    files         = models.ManyToManyField(FileObject, null=True, blank=True)
    images        = models.ManyToManyField(ImageObject, null=True, blank=True)

    points        = models.MultiPointField(srid=4326, blank=True, null=True)
    lines         = models.MultiLineStringField(srid=4326, blank=True, null=True)
    polys         = models.MultiPolygonField(srid=4326, blank=True, null=True)

    pos_quality   = models.CharField(max_length=30, choices=pos_qualities,
                                        default='Unknown', blank=True)

#    geometry      = models.GeometryCollectionField(srid=4326, blank=True, null=True)
    objects       = models.GeoManager()

    quality       = models.SmallIntegerField(choices=quality_flags,
                                             default=CREATED)

    publications  = models.ManyToManyField(Publication, null=True, blank=True)

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



# from find_artek.publications import models
# p = models.get_person(u'T Ingeman-Nielsen',exact=False)
# pp = p[0].get_pybtex_person()
# myp = models.choose_person(p,pp)
