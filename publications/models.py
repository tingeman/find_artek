from django.db import models
from django.contrib.auth.models import User

#------- global variables start here ----------------
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

#------- global variables ends here ----------------


#------- models start here ----------------


class BaseModel(models.Model):
    created_date  = models.DateTimeField(auto_now_add=True)

    modified_date = models.DateTimeField(auto_now=True)
    created_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False, related_name="%(class)s_created")
    modified_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False, related_name="%(class)s_modified")

    class Meta:
        abstract = True

# make simple test class
class Test(BaseModel):
    name = models.CharField(max_length=100)

    class Meta:
        permissions = (
            ("edit_own_test", "Can edit own test"),
            ("delete_own_test", "Can delete own test"),
        )



class Person(BaseModel):
    # variables here 
    # Additional fields for quality control
    quality           = models.SmallIntegerField(choices=quality_flags, default=CREATED)


    # Fields for the person here 
    first_relaxed     = models.CharField(max_length=10, blank=True)      # first initial, lower case, no special characters
    last_relaxed      = models.CharField(max_length=100, blank=True)     # last name, lower case, no special characters

    ### first ###
    # Note: I had to set blank=True to fix an error when I tried to migrate.

    # I got an error when I tried to migrate: 
    #
    # >> python manage.py makemigrations publications
    # It is impossible to add a non-nullable field 'first' to person without specifying a default. This is because the database needs something to populate existing rows.
    # Please select a fix:
    #  1) Provide a one-off default now (will be set on all existing rows with a null value for this column)
    #  2) Quit and manually define a default value in models.py.
    #
    # I have set blank=True, to fix this error.
    first             = models.CharField(max_length=100, blank=True)     # Allows LaTeX escaped characters
    


    middle            = models.CharField(max_length=100, blank=True)     # Allows LaTeX escaped characters
    prelast           = models.CharField(max_length=100, blank=True)     # Allows LaTeX escaped characters



    ### last ###
    # Note: I had to set blank=True to fix an error when I tried to migrate.

    # I got an error when I tried to migrate: 
    #
    # >> python manage.py makemigrations publications
    # It is impossible to add a non-nullable field 'last' to person without specifying a default. This is because the database needs something to populate existing rows.
    # Please select a fix:
    #  1) Provide a one-off default now (will be set on all existing rows with a null value for this column)
    #  2) Quit and manually define a default value in models.py.
    #
    # I have set blank=True, to fix this error.
    last              = models.CharField(max_length=100, blank=True)     # Allows LaTeX escaped characters
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
    note              = models.TextField(blank=True)



    class Meta:
        permissions = (
            ("edit_own_person", "Can edit own person"),
            ("delete_own_person", "Can delete own person"),
        )








# Create publication model
class Publication(BaseModel):

    #--------- Variables starts here ----------------
    
    # Dictionary of fields not in BibTex
    # This i biograpgy system, that is not in bibtex
    not_bibtex = ('supervisor', 'grade', 'quality', 'created', 'modified', 'modified_by',)

    # --------- Variables ends here ----------------


    # --------- Fields starts here ----------------

    key             = models.CharField(max_length=100, blank=True)          # PK Lastname#Year[letter]


    # uncomment when models are ready
    # type            = models.ForeignKey(PubType)                            # f.ex. BOOK, ARTICLE

    author          = models.ManyToManyField(Person, through='Authorship',
                                             related_name='publication_authors',
                                             blank=True, default=None)
    editor          = models.ManyToManyField(Person, through='Editorship',
                                             related_name='publication_editors',
                                             blank=True, default=None)
    # Additional fields for student reports
    supervisor      = models.ManyToManyField(Person, through='Supervisorship',
                                            related_name='publication_supervisors',
                                            blank=True, default=None)


    #
    
    ### booktitle ###
    # NOTE: I have redueced tje length of the book title fram 65535 to 255 characters, to fix an error when I tried to migrate.
    # In a MariaDB 10.6.11 the max length of a varchar is characters is 16370.
    booktitle       = models.CharField(max_length=255, blank=True)
    ### booktitle ###


    title           = models.CharField(max_length=255, blank=True)
    crossref        = models.CharField(max_length=255, blank=True)
    chapter         = models.CharField(max_length=255, blank=True)
    # journal         = models.ForeignKey(Journal, blank=True, null=True, default=None,
    #                                     on_delete=models.SET_NULL)
    volume          = models.CharField(max_length=255, blank=True)
    number          = models.CharField(max_length=255, blank=True)
    institution     = models.CharField(max_length=255, blank=True)
    organization    = models.CharField(max_length=255, blank=True)
    publisher       = models.CharField(max_length=255, blank=True)
    school          = models.CharField(max_length=255, blank=True)
    address         = models.CharField(max_length=255, blank=True)
    edition         = models.CharField(max_length=255, blank=True)
    pages           = models.CharField(max_length=100, blank=True)
    month           = models.CharField(max_length=100, blank=True)
    year            = models.CharField(max_length=100, blank=True)
    DOI             = models.CharField(max_length=255, blank=True)
    ISBN            = models.CharField(max_length=255, blank=True)
    ISBN13          = models.CharField(max_length=255, blank=True)
    ISSN            = models.CharField(max_length=255, blank=True)
    note            = models.TextField(max_length=255, blank=True)
    series          = models.CharField(max_length=255, blank=True)
    abstract        = models.TextField(max_length=255, blank=True)
    remark          = models.CharField(max_length=255, blank=True)
    subject         = models.CharField(max_length=255, blank=True)   # Could be a short description of the report
    howpublished    = models.CharField(max_length=255, blank=True)
    comment         = models.TextField(max_length=255, blank=True)
    # keywords        = models.ManyToManyField(Keyword, blank=True, null=True,
                                            # related_name='publication_keywords',
                                            # default=None)
    # URLs            = models.ManyToManyField(URLObject, blank=True, null=True, default=None)

    # file            = models.OneToOneField(FileObject, blank=True, null=True,
                                            # default=None, on_delete=models.SET_NULL)
    # appendices      = models.ManyToManyField(FileObject, blank=True, null=True, default=None,
                                            #  related_name='publication_appendices')
    
    timestamp       = models.CharField(max_length=100, blank=True)     # Should this be a DateTimeField


    # topics          = models.ManyToManyField(Topic, blank=True, null=True, default=None)


    grade           = models.CharField(max_length=100, blank=True, null=True, default=None)


    # Additional fields for quality control
    verified       = models.BooleanField(blank=False, default=False)
    quality        = models.SmallIntegerField(choices=quality_flags, default=CREATED)
    # --------- Fields ends here ----------------



    # --------- Sub classes starts here ----------------
    class Meta:
        permissions = (
            ("edit_own_publication", "Can edit own publications"),
            ("delete_own_publication", "Can delete own publications"),
            ("verify_publication", "Can verify publications"),
        )
    # --------- Sub classes ends here ----------------




class Authorship(models.Model):
    # Make sure to take care of what happens when a model is deleted, on_delete=models.CASCADE for example


    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
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
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
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
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
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

#------- models ends here ----------------