import re
import os
from unidecode import unidecode
from django.db.models import Case, When, Value, IntegerField
from django.conf import settings
from django.core.files.storage import default_storage


class CaseInsensitively(object):
    """Wrap CaseInsensitively around an object to make comparisons
    case-insensitive.

    example:
    if CaseInsensitively('Hello world') in ['hello world', 'Hej Verden']:
        print "The if clause evaluates True!"

    """
    def __init__(self, s):
        self.__s = s.lower()

    def __hash__(self):
        return hash(self.__s)

    def __eq__(self, other):
        # ensure proper comparison between instances of this class
        try:
            other = other.__s
        except (TypeError, AttributeError):
            try:
                other = other.lower()
            except:
                pass
        return self.__s == other


class CyclicList(list):
    """Overloaded list class, which will wrap around
    when accessing indices larger than the length of
    list."""

#    from itertools import cycle

    def __getitem__(self, index):
        if isinstance(index, int):
            return list.__getitem__(self, index % len(self))
        else:
            raise TypeError("index must be int or slice")

    def __getslice__(self, i, j):
        newlist = []
        for k in range(i, j):
            newlist.append(self[k])
        return newlist


# Find "[tag:value]" items allowing for whitespace, extract tag and value.
re_tag_items = re.compile(r'\[\s*(?P<tag>[a-zA-Z]*?)\s*[:=]\s*(?P<value>.*?)\s*\]')

# Find "[tag:value]" strings allowing for whitespace (matching the entire string).
re_tag = re.compile(r'(?P<tag>\[\s*[a-zA-Z]*?\s*[:=]\s*.*?\s*\])')


def extract_tags(s):
    """Get all [tag:value] pairs in the string 's'
    and return as dictionary with key=tag and value=value.
    """
    return re.findall(re_tag_items, s)


def get_tag(s, tag, lower=True):
    """Get the value of [tag:value] for the tag-named passed in argument 'tag'
    or return None if not found
    """

    tags = extract_tags(s)
    if tags:
        # iterate over tag:value pairs
        if lower:  # all tag names converted to lower case
            for t, v in tags:
                if t.lower() == tag.lower():
                    return v
        else:  # no case change performed on input string
            for t, v in tags:
                if t == tag:
                    return v
    return None


def remove_tags(s):
    """Removes all [xx:xx] tags in a string and strips any whitespace from both
    ends of the string, returning the resulting string.
    """
    return re.sub(re_tag, "", s).strip()


def dk_unidecode(string):
    """use unidecode, but first exchange æÆ, øØ and åÅ with ae, oe and aa
    """
    kwargs = {'æ': 'ae', 'Æ': 'Ae',
              'ø': 'oe', 'Ø': 'Oe',
              'å': 'aa', 'Å': 'Aa'}

    for old, new in kwargs.items():
        string = string.replace(old, new)

    # now call regular unidecode
    return unidecode(string)


def create_ordered_queryset(model_class, pk_list):
    """
    Create an ordered QuerySet that preserves the order of the input pk_list.
    Uses Django's Case/When to order by the position in the original list.
    
    Args:
        model_class: The Django model class to query
        pk_list: List of primary keys in the desired order
        
    Returns:
        QuerySet: An ordered QuerySet that preserves the input order
        
    Example:
        # Get Person objects in specific order
        person_ids = [3, 1, 4, 2]
        ordered_persons = create_ordered_queryset(Person, person_ids)
        # Result will be Person objects in order [pk=3, pk=1, pk=4, pk=2]
    """
    if not pk_list:
        return model_class.objects.none()
    
    # Create Case/When clauses to preserve order
    preserved_order = Case(*[
        When(pk=pk, then=Value(i)) 
        for i, pk in enumerate(pk_list)
    ], output_field=IntegerField())
    
    # Filter and order the QuerySet
    queryset = model_class.objects.filter(pk__in=pk_list).annotate(
        preserved_order=preserved_order
    ).order_by('preserved_order')
    
    return queryset


def handle_publication_file_upload(publication, uploaded_file):
    """
    Handle the upload, renaming, and storage of a publication PDF file.
    
    Args:
        publication: The Publication instance
        uploaded_file: The uploaded file from the form
        
    Returns:
        FileObject: The created FileObject instance
    """
    if not uploaded_file:
        return None
        
    # Generate the new filename based on report number
    new_filename = f"{publication.number}.pdf"
    
    # Create the directory path: reports/YYYY/
    year_dir = f"reports/{publication.year}"
    file_path = os.path.join(year_dir, new_filename)
    
    # Ensure the directory exists
    full_dir_path = os.path.join(settings.MEDIA_ROOT, year_dir)
    os.makedirs(full_dir_path, exist_ok=True)
    
    # Save the file with the new name
    saved_path = default_storage.save(file_path, uploaded_file)
    
    # Create FileObject instance
    from publications.models import FileObject
    file_obj = FileObject.objects.create(
        file=saved_path,
        description=f"PDF file for report {publication.number} ({publication.year})"
    )
    
    return file_obj
