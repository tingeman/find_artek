from django.db import models
from django.contrib.auth.models import User

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

class Publication(models.Model):

    not_bibtex = ('supervisor', 'grade', 'quality', 'created', 'modified', 'modified_by')

    key = models.CharField(max_length=100, blank=True)

    author = models.ManyToManyField(Person, through='Authorship',
                                     related_name='publication_authors',
                                     blank=True, default=None)

    editor = models.ManyToManyField(Person, through='Editorship',
                                     related_name='publication_editors',
                                     blank=True, default=None)

    supervisor = models.ManyToManyField(Person, through='Supervisorship',
                                        related_name='publication_supervisors',
                                        blank=True, default=None)

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

    year = models.CharField(max_length=100, blank=True)

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
