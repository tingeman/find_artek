# -*- coding: utf_8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

import re
from unidecode import unidecode


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
        for k in xrange(i, j):
            newlist.append(self[k])
        return newlist


# Find [tag:value] allowing for whitespace.
re_tag_items = re.compile(r'\[\s*(?P<tag>[a-zA-Z]*?)\s*[:=]\s*(?P<value>.*?)\s*\]')

# Find [tag:value] strings allowing for whitespace.
re_tag = re.compile(r'(?P<tag>\[\s*[a-zA-Z]*?\s*[:=]\s*.*?\s*\])')


def extract_tags(s):
    # Get all [tag:value] pairs in the string 's'
    # and return as dictionary with key=tag and value=value.
    return re.findall(re_tag_items, s)


def get_tag(s, tag, lower=True):
    # get the value of [tag:value] for the tag-named passed in argument 'tag'
    # or return None if not found

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
