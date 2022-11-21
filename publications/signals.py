from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

from django.dispatch import receiver
from django.contrib.auth.models import Group

import sys
import pdb

import logging
logger = logging.getLogger(__name__)


"""This module is being imported in the publications __init__ module and from the urls module.
"""

super_user_list = []
#super_user_list = [u's103346',
#                   u's103355',
#                   u'thin']
