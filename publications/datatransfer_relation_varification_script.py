# The purpose of this script is to verify that the data relations in the models are working as expected.

import os
import django

# set the environment variable for the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'find_artek.settings')

# configure Django settings
django.setup()

# Now you can import Django models and use the ORM
from django.contrib.auth.models import User
from publications import models

import sqlite3
import pathlib
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404
from publications.models import Publication, Person, Authorship
from datetime import datetime

def run():

    # PUT VERIFICATIONS HERE

    # get person with id 3
    person = Person.objects.get(id=3)

    # get all publications for person
    publications = person.publications.all()
    




if __name__ == '__main__':
    run()
