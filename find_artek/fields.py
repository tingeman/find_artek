import pdb

from django import forms
from django.core.exceptions import ValidationError
from django.core import validators

from find_artek.widgets import TagInput


class TagField(forms.Field):
    """This field implements a TagInput widget in a (model)form.
    The widget allows the entry of strings that will be handled as tags.
    by default, the stop characters are 'space', 'comma', 'enter' and 'tab'.
    The field will return a list of unicode strings.

    """
    widget = TagInput
    default_error_messages = {
        'invalid_tags':     (u'you have specified invalid tags!'),
        'wrong_tag_format': (u'validate recieved wrongly formatted tags!'),
    }

    def to_python(self, value):
        if value in validators.EMPTY_VALUES:
            return None

        if not hasattr(value, '__iter__') or isinstance(value, basestring):
            value = [value]
            #pdb.set_trace()
            #raise ValidationError(self.error_messages['not_an_a'])

        return value

    def validate(self, value):
        if value:
            if not hasattr(value, '__iter__') or isinstance(value, basestring):
                raise ValidationError(self.error_messages['wrong_tag_format'])
