import os
from MySQLdb import IntegrityError
import django

# THIS SCRIPT TOTALLY DEPENDS ON 
# models_that_looks_like_old_models.py


# ------------------- person, publication, authorship, editorship, supervisorship ------------------ #
# This part of the script transfers the following tables from the sqlite3 database:
# person, publication, authorship, editorship, supervisorship.
# It also make test if the data is working.
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
    # Connect to the old sqlite database
    p = pathlib.Path('/usr/src/app/find_artek/find_artek.sqlite')
    conn = sqlite3.connect(str(p))

    # create a cursor object
    cursor_object = conn.cursor()





    # ------------------- Handle transfer person starts here ------------------ #
    person_table_data = cursor_object.execute('PRAGMA table_info(publications_person)').fetchall() # GET PERSON RECORDS
    person_column_names = [row[1] for row in person_table_data] # Extract column names

    person_dictionary = []
    for row in cursor_object.execute("SELECT * FROM publications_person"):
        person_dictionary.append(dict(zip(person_column_names, row)))

    person_objects_created = 0
    person_objects_already_exist = 0
    for dictionary in person_dictionary:

        # Convert the string to a datetime object
        for key in ['created_date', 'modified_date']:
            date_string = dictionary[key] # '2012-12-19 22:36:14.891000'
            date_format = '%Y-%m-%d %H:%M:%S.%f'
            try:
                date_object = datetime.strptime(date_string, date_format)
            except ValueError:
                date_format = '%Y-%m-%d %H:%M:%S'
                date_object = datetime.strptime(date_string, date_format)

            dictionary[key] = date_object

        illigal_keys = dict()
        for key in ['created_by_id', 'modified_by_id']:
            illigal_keys[key] = dictionary.pop(key)

        # add the data
        instance, created = models.Person.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

        
        if created:
            print("New person created with name:", instance.first, instance.last)
            person_objects_created += 1
        else:
            person_objects_already_exist += 1
            print("Person already exists with name:", instance.first, instance.last)
    # ------------------- Handle transfer person ends here ------------------ #


    # ------------------- Handle transfer publication starts here ------------------ #
    publication_table_data = cursor_object.execute('PRAGMA table_info(publications_publication)').fetchall() # GET PUBLICATION RECORDS
    publication_column_names = [row[1] for row in publication_table_data] # Extract column names

    publication_dictionary = []
    for row in cursor_object.execute("SELECT * FROM publications_publication"):
        publication_dictionary.append(dict(zip(publication_column_names, row)))

    publication_objects_created = 0
    publication_objects_already_exist = 0
    for dictionary in publication_dictionary:

        # Convert the string to a datetime object
        for key in ['created_date', 'modified_date']:
            date_string = dictionary[key] # '2012-12-19 22:36:14.891000'
            date_format = '%Y-%m-%d %H:%M:%S.%f'
            try:
                date_object = datetime.strptime(date_string, date_format)
            except ValueError:
                date_format = '%Y-%m-%d %H:%M:%S'
                date_object = datetime.strptime(date_string, date_format)

            dictionary[key] = date_object

        illigal_keys = dict()
        for key in ['created_by_id', 'file_id', 'modified_by_id', 'type_id']:
            illigal_keys[key] = dictionary.pop(key)

        instance, created = models.Publication.objects.get_or_create(id=dictionary['id'], defaults=dictionary)
        
        if created:
            print("New publication created with number:", instance.number)
            publication_objects_created += 1
        else:
            publication_objects_already_exist += 1
            print("Publication already exists with number:", instance.number)
    # ------------------- Handle transfer publication ends here ------------------ #



    # ------------------- Handle transfer authorship starts here ------------------ #
    # Extract column names from the tables
    authorship_table_data = cursor_object.execute('PRAGMA table_info(publications_authorship)').fetchall() # GET AUTHOR TABLE INFO
    authorship_column_names = [row[1] for row in authorship_table_data] # Extract column names
    
    author_dictionary = []
    for row in cursor_object.execute("SELECT * FROM publications_authorship"):
        author_dictionary.append(dict(zip(authorship_column_names, row)))

    author_objects_created = 0
    author_objects_already_exist = 0
    for dictionary in author_dictionary:
            
            # add the data
            instance, created = models.Authorship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print(f"New authorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                author_objects_created += 1
            else:
                print(f"New authorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                author_objects_already_exist += 1               
    # ------------------- Handle transfer authorship starts here ------------------ #


    # ------------------- Handle transfer editorship starts here ------------------ #
    # Extract column names from the tables
    editorship_table_data = cursor_object.execute('PRAGMA table_info(publications_editorship)').fetchall() # GET AUTHOR TABLE INFO
    editorship_column_names = [row[1] for row in editorship_table_data] # Extract column names

    editor_dictionary = []
    for row in cursor_object.execute("SELECT * FROM publications_editorship"):
        editor_dictionary.append(dict(zip(editorship_column_names, row)))

    editor_objects_created = 0
    editor_objects_already_exist = 0
    for dictionary in editor_dictionary:
                
                # add the data
                instance, created = models.Editorship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)
    
                if created:
                    print(f"New editorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                    editor_objects_created += 1
                else:
                    print(f"New editorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                    editor_objects_already_exist += 1
    # ------------------- Handle transfer editorship ends here ------------------ #


    # ------------------- Handle transfer supervisorship starts here ------------------ #
    
    # Extract column names from the tables
    supervisorship_table_data = cursor_object.execute('PRAGMA table_info(publications_supervisorship)').fetchall() # GET AUTHOR TABLE INFO
    supervisorship_column_names = [row[1] for row in supervisorship_table_data] # Extract column names

    supervisor_dictionary = []
    for row in cursor_object.execute("SELECT * FROM publications_supervisorship"):
        supervisor_dictionary.append(dict(zip(supervisorship_column_names, row)))

    supervisor_objects_created = 0
    supervisor_objects_already_exist = 0
    for dictionary in supervisor_dictionary:

        # add the data
        instance, created = models.Supervisorship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

        if created:
            print(f"New supervisorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
            supervisor_objects_created += 1
        else:
            print(f"New supervisorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
            supervisor_objects_already_exist += 1

    # ------------------- Handle transfer supervisorship ends here ------------------ #

    # print total number of person_objects_created
    print("Total number of person objects created:", person_objects_created)
    print("Total number of person objects that already exist", person_objects_already_exist)

    # print total number of publication_objects_created
    print("Total number of publication objects created:", publication_objects_created)
    print("Total number of publication objects that already exist", publication_objects_already_exist)

    # print total number of author_objects_created
    print("Total number of author objects created:", author_objects_created)
    print("Total number of author objects that already exist", author_objects_already_exist)

    # print total number of editor_objects_created
    print("Total number of editor objects created:", editor_objects_created)
    print("Total number of editor objects that already exist", editor_objects_already_exist)

    # print total number of supervisor_objects_created
    print("Total number of supervisor objects created:", supervisor_objects_created)
    print("Total number of supervisor objects that already exist", supervisor_objects_already_exist)

# ------------------- person, publication, authorship, editorship, supervisorship ------------------ #

    exit()

if __name__ == '__main__':
    run()
