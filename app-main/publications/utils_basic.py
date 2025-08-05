"""
Basic utility functions and classes for publications app.
These do NOT depend on Django models or database access.
"""

import re
from unidecode import unidecode

# Find "[tag:value]" items allowing for whitespace, extract tag and value.
re_tag_items = re.compile(r'\[\s*(?P<tag>[a-zA-Z]*?)\s*[:=]\s*(?P<value>.*?)\s*\]')

# Find "[tag:value]" strings allowing for whitespace (matching the entire string).
re_tag = re.compile(r'(?P<tag>\[\s*[a-zA-Z]*?\s*[:=]\s*.*?\s*\])')

class CaseInsensitively(object):
    """Wrap CaseInsensitively around an object to make comparisons case-insensitive."""
    def __init__(self, s):
        self.__s = s.lower()
    def __hash__(self):
        return hash(self.__s)
    def __eq__(self, other):
        try:
            other = other.__s
        except (TypeError, AttributeError):
            try:
                other = other.lower()
            except:
                pass
        return self.__s == other

class CyclicList(list):
    """Overloaded list class, which will wrap around when accessing indices larger than the length of list."""
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

def extract_tags(s):
    """Get all [tag:value] pairs in the string 's' and return as list of tuples."""
    return re.findall(re_tag_items, s)

def get_tag(s, tag, lower=True):
    """Get the value of [tag:value] for the tag-named passed in argument 'tag' or return None if not found"""
    tags = extract_tags(s)
    if tags:
        if lower:
            for t, v in tags:
                if t.lower() == tag.lower():
                    return v
        else:
            for t, v in tags:
                if t == tag:
                    return v
    return None

def remove_tags(s):
    """Removes all [xx:xx] tags in a string and strips any whitespace from both ends of the string."""
    return re.sub(re_tag, "", s).strip()

def dk_unidecode(string):
    """use unidecode, but first exchange æÆ, øØ and åÅ with ae, oe and aa"""
    kwargs = {'æ': 'ae', 'Æ': 'Ae', 'ø': 'oe', 'Ø': 'Oe', 'å': 'aa', 'Å': 'Aa'}
    for old, new in kwargs.items():
        string = string.replace(old, new)
    return unidecode(string)
