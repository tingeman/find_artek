# -*- coding: utf_8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

import pdb

from django.conf import settings
from django.forms import Widget, FileInput
from django.utils.safestring import mark_safe
from django.contrib.admin.widgets import AdminFileWidget
from django.utils.translation import ugettext as _


class TagInput(Widget):
    """A widget that implements an input field for tag picking, based on
    jQuery-Tagit, acquired from https://github.com/hailwood/jQuery-Tagit

    """
    class Media:
        js = [settings.STATIC_URL + "jQuery-Tagit/js/tagit.js"]
        css = {'all': [settings.STATIC_URL + "jQuery-Tagit/css/tagit-my-simple-grey.css"]}

    def __init__(self, *args, **kwargs):
        """A widget that implements an input field for tag picking, based on
        jQuery-Tagit, acquired from https://github.com/hailwood/jQuery-Tagit

        kwargs may contain the key TagInputAttrs, which is a dictionary of
        properties to pass to the jquery tagit widget.
        The keys and values will be insert as arguments of the jQuery tagit call
        in the html output. Thus parameters that should be considered lists by
        the js must be a python string (enclosed in ""), and objects that should
        be considered strings by js must be a python string that includes the
        quotes that are to be visible in the js code. E.G. string "handle" will
        be considered as the OBJECT named handle by js, whereas the string
        "'handle'" will be correctly considered a string by js.
        strings must be byte strings (not unicode) to be rendered correctly

        Possible attributes and default values:

        tagSource               String, Array, Callback     []
        triggerKeys             Array                       ['enter', 'space', 'comma', 'tab']
        allowNewTags            Bool                        true
        initialTags             Array                       []
        minLength               Int                         1
        maxLength               Int                         1
        select                  Bool                        false
        tagsChanged             Callback                    function(tagValue, action, element)
        caseSensitive           Bool                        false
        highlightOnExistColor   String                      #0F0
        maxTags                 Int                         unlimited
        sortable                Bool, String                false
        """

        # Handling arguments and defaults if needed.
        self.TagInputAttrs = {'tagSource': [],
                                'triggerKeys': [b'enter', b'space', b'comma', b'tab'],
                                'allowNewTags': 'true',
                                #'initialTags': [],
                                #'minLength': '1',
                                #'maxLength': '1',
                                'select': 'true',
                                'sortable': 'true'}

        self.TagInputAttrs.update(kwargs.pop("TagInputAttrs", {}))
        Widget.__init__(self, *args, **kwargs)

    def render(self, name, value, attrs=None):
        """Renders this widget into an html string

        args:
        name  (str)  -- name of the field
        value (list) -- a list of initial tags (strings) to be shown
        attrs (dict) -- automatically passed in by django (?unused in this function?)

        NEED TO HANDLE CSS FOR DIFFERENT INSTANTIATIONS OF THE WIDGET...
        Widget for Authors may be green, Keywords red etc...
        """

        if not value:
            value = []

        if self.attrs and 'title' in self.attrs:
            ret = '<ul id="{0}-tag" data-name="{0}" name="{0}" class="TagInput" title="{1}">'.format(name,self.attrs['title'])
        else:
            ret = '<ul id="{0}-tag" data-name="{0}" name="{0}" class="TagInput">'.format(name)

        for v in value:
            ret += '<li data-value="{0}">{0}</li>'.format(v)
        ret += 'Type something here...</ul>'

        tmp = ["<script>",
                "$('#{0}-tag').tagit({{ ".format(name)]

        for k, v in self.TagInputAttrs.items():
            tmp.append("{0}: {1},".format(k, str(v)))

        tmp.extend(["})",
                    "</script>"])

        #ret += ''.join(tmp).format(name)
        ret += ''.join([t.strip() for t in tmp])
        return mark_safe(ret)

    def value_from_datadict(self, data, files, name):
        """
        Returns a list of strings, corresponding to the tags entered

        args:
        data  (dict)  -- request.POST or request.GET is passed as 'data'
        files (list)  -- request.FILES
        name  (str)   -- the name of the field associated with this widget

        """

        tags = []
        if name in data:
            tags = data.getlist(name)
        return tags


class FileWidget(FileInput):
    """
    A FileField Widget that shows its current value if it has one.
    """
    def __init__(self, attrs={}):
        super(FileWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        output = []
        if value and hasattr(value, "url"):
            output.append('%s <a target="_blank" href="%s">%s</a> <br />%s ' % \
                (_('Currently:'), value.url, value, _('Change:')))
        output.append(super(FileWidget, self).render(name, value, attrs))
        return mark_safe(u''.join(output))
