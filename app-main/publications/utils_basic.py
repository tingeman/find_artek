"""
Basic utility functions and classes for publications app.
These do NOT depend on Django models or database access.
"""

import re
from unidecode import unidecode
import codecs
import latexcodec  
import logging

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

def get_emails(s):
    """Extract all email addresses from a string."""
    # Regex to match email addresses
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.findall(email_pattern, s)

def remove_emails(s):
    """Remove email addresses from a string."""
    # Regex to match email addresses
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.sub(email_pattern, '', s).strip()

def dk_unidecode(string):
    """use unidecode, but first exchange æÆ, øØ and åÅ with ae, oe and aa"""
    kwargs = {'æ': 'ae', 'Æ': 'Ae', 'ø': 'oe', 'Ø': 'Oe', 'å': 'aa', 'Å': 'Aa'}
    for old, new in kwargs.items():
        string = string.replace(old, new)
    return unidecode(string)

logger = logging.getLogger(__name__)
def safe_latex_decode(s):
    try:
        # Only decode if string contains LaTeX markup (heuristic: contains backslash or curly braces)
        if isinstance(s, str) and ('\\' in s or '{' in s or '}' in s):
            return codecs.decode(s.encode('utf-8'), 'latex')
        else:
            return s
    except Exception as e:
        logger.warning(f"latex decode failed for '{s}': {e}")
        return s
