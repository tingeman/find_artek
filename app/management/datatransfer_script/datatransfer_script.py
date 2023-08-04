from publications import models
from publications.models import Publication, Person, Authorship
import os
import pathlib
import sqlite3
from datetime import datetime
from django.apps import apps


import django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'find_artek.settings')
django.setup()




# Now you can import Django models and use the ORM

# This is the script that transfers data from the old database into the new one.
# The old database is implemented using Django v1.6 or earlier models.
# When the data is transferred into the new database, the new database tries to resemble the old one (models_that_look_like_old_models.py).
# The new database is implemented using Django v4.1 or later models.

# Note that this SCRIPT TOTALLY DEPENDS ON
# models_that_looks_like_old_models.py


def run():

    # ------------------- Check for non characters that you consider invalid ------------------ #

    # invalid_to_valid put chacters here, that you want to replace
    invalid_to_valid = {
        '‐': '-'
    }

    def check_string(input_string):
        invalid_indices = []
        for i, char in enumerate(input_string):
            if char in invalid_to_valid:
                invalid_indices.append(i)
        return invalid_indices
    # ------------------- Check for non characters that you consider invalid ------------------ #

    time_zone = timezone.get_default_timezone()



    # ------------------- Connect to the old sqlite database ------------------ #
    # Get the absolute path to the directory where the script is located
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # Create the absolute path to the sqlite file
    sqlite_file = os.path.join(script_dir, 'find_artek.sqlite')

    # Check if the sqlite file exists
    if not os.path.isfile(sqlite_file):
        print("The database file does not exist")
        exit()

    p = pathlib.Path(sqlite_file)
    conn = sqlite3.connect(str(p))

    # create a cursor object
    cursor_object = conn.cursor()
    # ------------------- Connect to the old sqlite database ------------------ #




    def handle_transfer_journal():
        # ------------------- Handle transfer journal starts here ------------------ #
        # The table is empty so no need to transfer data
        journal_objects_created = 0
        journal_objects_alerady_exists = 0

        return journal_objects_created, journal_objects_alerady_exists
        # ------------------- Handle transfer journal ends here ------------------ #
    


    def handle_transfer_pubtype():
        # ------------------- Handle transfer pubtype starts here ------------------ #

        # The table is not empty so i do need to transfer data
        # Extract column names from the tables
        pubtype_table_data = cursor_object.execute('PRAGMA table_info(publications_pubtype)').fetchall() 
        pubtype_column_names = [row[1] for row in pubtype_table_data]  # Extract column names

        pubtype_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_pubtype"):
            pubtype_dictionary.append(dict(zip(pubtype_column_names, row)))

        pubtype_objects_created = 0
        pubtype_objects_already_exist = 0
        for dictionary in pubtype_dictionary:

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string


            

            # add the data
            instance, created = models.PubType.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print(f"New pubtype created with name {instance.type} and id {instance.id}")
                pubtype_objects_created += 1
            else:
                print(f"New pubtype created with name {instance.type} and id {instance.id}")
                pubtype_objects_already_exist += 1

        return pubtype_objects_created, pubtype_objects_already_exist
        # ------------------- Handle transfer pubtype ends here ------------------ #
    
    

    def handle_transfer_topic():
        # ------------------- Handle transfer topic starts here ------------------ #
        # Extract column names from the tables
        topic_table_data = cursor_object.execute('PRAGMA table_info(publications_topic)').fetchall() 
        topic_column_names = [row[1] for row in topic_table_data]  # Extract column names

        topic_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_topic"):
            topic_dictionary.append(dict(zip(topic_column_names, row)))

        topic_objects_created = 0
        topic_objects_already_exist = 0
        for dictionary in topic_dictionary:

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string

                
            # add the data
            instance, created = models.Topic.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print("New topic created with name:", instance.topic)
                topic_objects_created += 1
            else:
                print("Topic already exists with name:", instance.topic)
                topic_objects_already_exist += 1
        
        return topic_objects_created, topic_objects_already_exist
        # ------------------- Handle transfer topic ends here ------------------ #


    def handle_transfer_keyword():
        # ------------------- Handle transfer keyword starts here ------------------ #
        # Extract column names from the tables
        keyword_table_data = cursor_object.execute('PRAGMA table_info(publications_keyword)').fetchall()
        keyword_column_names = [row[1] for row in keyword_table_data]  # Extract column names

        keyword_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_keyword"):
            keyword_dictionary.append(dict(zip(keyword_column_names, row)))

        keyword_objects_created = 0
        keyword_objects_already_exist = 0
        for dictionary in keyword_dictionary:

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string


            # add the data
            instance, created = models.Keyword.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print("New keyword created with name:", instance.keyword)
                keyword_objects_created += 1
            else:
                print("Keyword already exists with name:", instance.keyword)
                keyword_objects_already_exist += 1
        
        return keyword_objects_created, keyword_objects_already_exist
        # ------------------- Handle transfer keyword ends here ------------------ #
    
    



    
 

    


    
    
    
    



    def handle_transfer_person():
        # ------------------- Handle transfer person starts here ------------------ #
        person_table_data = cursor_object.execute('PRAGMA table_info(publications_person)').fetchall()  # GET PERSON RECORDS
        person_column_names = [row[1] for row in person_table_data]  # Extract column names

        person_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_person"):
            person_dictionary.append(dict(zip(person_column_names, row)))

        person_objects_created = 0
        person_objects_already_exist = 0
        for dictionary in person_dictionary:

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string


            # Convert the string to a datetime object
            for key in ['created_date', 'modified_date']:
                date_string = dictionary[key]  # '2012-12-19 22:36:14.891000'
                date_format = '%Y-%m-%d %H:%M:%S.%f'
                try:
                    date_object = datetime.strptime(date_string, date_format)
                except ValueError:
                    date_format = '%Y-%m-%d %H:%M:%S'
                    date_object = datetime.strptime(date_string, date_format)

                dictionary[key] = timezone.make_aware(date_object, time_zone)

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

        return  person_objects_created, person_objects_already_exist
        # ------------------- Handle transfer person ends here ------------------ #
    


    def handle_transfer_file():
        # ------------------- Handle transfer file starts here ------------------ #
        # Extract column names from the tables
        file_table_data = cursor_object.execute('PRAGMA table_info(publications_fileobject)').fetchall()
        file_column_names = [row[1] for row in file_table_data]  # Extract column names

        file_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_fileobject"):
            file_dictionary.append(dict(zip(file_column_names, row)))

        file_objects_created = 0
        file_objects_already_exist = 0
        for dictionary in file_dictionary:


            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string


            # Convert the string to a datetime object
            for key in ['created_date', 'modified_date']:
                date_string = dictionary[key]  # '2012-12-19 22:36:14.891000'
                date_format = '%Y-%m-%d %H:%M:%S.%f'
                try:
                    date_object = datetime.strptime(date_string, date_format)
                except ValueError:
                    date_format = '%Y-%m-%d %H:%M:%S'
                    date_object = datetime.strptime(date_string, date_format)

                dictionary[key] = timezone.make_aware(date_object, time_zone)

            illigal_keys = dict()
            for key in ['created_by_id', 'modified_by_id']:
                illigal_keys[key] = dictionary.pop(key)


            # add the data
            instance, created = models.FileObject.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print("New file created with name:", instance.file)
                file_objects_created += 1
            else:
                print("File already exists with name:", instance.file)
                file_objects_already_exist += 1
            
        return file_objects_created, file_objects_already_exist
        # ------------------- Handle transfer file ends here ------------------ #

    def handle_transfer_Image_objects():

        # Extract column names from the tables
        publication_table_data      = cursor_object.execute('PRAGMA table_info(publications_imageobject)').fetchall()  # GET PUBLICATION RECORDS
        publication_column_names    = [row[1] for row in publication_table_data]  # Extract column names

        image_dictionary = []

        # add the data

        for row in cursor_object.execute("SELECT * FROM publications_imageobject"):
            image_dictionary.append(dict(zip(publication_column_names, row)))
        
        image_objects_created = 0
        image_objects_already_exist = 0
        for dictionary in image_dictionary:
            
            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string

                

            # Convert the string to a datetime object
            for key in ['created_date', 'modified_date']:
                date_string = dictionary[key]  # '2012-12-19 22:36:14.891000'
                date_format = '%Y-%m-%d %H:%M:%S.%f'
                try:
                    date_object = datetime.strptime(date_string, date_format)
                except ValueError:
                    date_format = '%Y-%m-%d %H:%M:%S'
                    date_object = datetime.strptime(date_string, date_format)

                dictionary[key] = timezone.make_aware(date_object, time_zone)

            illigal_keys = dict()
            for key in ['created_by_id', 'modified_by_id']:
                illigal_keys[key] = dictionary.pop(key)

            instance, created = models.ImageObject.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print("New publication created with name:", instance.caption)
                image_objects_created += 1
            else:
                print("Publication already exists with name:", instance.caption)
                image_objects_already_exist += 1
            
        return image_objects_created, image_objects_already_exist



    def handle_transfer_publication():
        # ------------------- Handle transfer publication starts here ------------------ #
        publication_table_data = cursor_object.execute(
            'PRAGMA table_info(publications_publication)').fetchall()  # GET PUBLICATION RECORDS
        publication_column_names = [
            row[1] for row in publication_table_data]  # Extract column names

        publication_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_publication"):
            publication_dictionary.append(dict(zip(publication_column_names, row)))

        publication_objects_created = 0
        publication_objects_already_exist = 0
        for dictionary in publication_dictionary:
            

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string

                

            # Convert the string to a datetime object
            for key in ['created_date', 'modified_date']:
                date_string = dictionary[key]  # '2012-12-19 22:36:14.891000'
                date_format = '%Y-%m-%d %H:%M:%S.%f'
                try:
                    date_object = datetime.strptime(date_string, date_format)
                except ValueError:
                    date_format = '%Y-%m-%d %H:%M:%S'
                    date_object = datetime.strptime(date_string, date_format)

                dictionary[key] = timezone.make_aware(date_object, time_zone)

            illigal_keys = dict()
            for key in ['created_by_id', 'modified_by_id']:
                illigal_keys[key] = dictionary.pop(key)

            instance, created = models.Publication.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print("New publication created with number:", instance.number)
                publication_objects_created += 1
            else:
                publication_objects_already_exist += 1
                print("Publication already exists with number:", instance.number)
        
        return publication_objects_created, publication_objects_already_exist
        # ------------------- Handle transfer publication ends here ------------------ #



    def handle_transfer_appendenciesship():
        # ------------------- Handle transfer appendenciesship starts here ------------------ #
        # Extract column names from the tables
        appendenciesship_table_data = cursor_object.execute('PRAGMA table_info(publications_publication_appendices)').fetchall()
        appendenciesship_column_names = [row[1] for row in appendenciesship_table_data]  # Extract column names

        appendenciesship_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_publication_appendices"):
            appendenciesship_dictionary.append(dict(zip(appendenciesship_column_names, row)))

        appendenciesship_objects_created = 0
        appendenciesship_objects_already_exist = 0
        for dictionary in appendenciesship_dictionary:

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string


            # add the data
            instance, created = models.Appendenciesship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print("New appendenciesship created with name:", instance)
                appendenciesship_objects_created += 1
            else:
                print("Appendenciesship already exists with name:", instance)
                appendenciesship_objects_already_exist += 1
        
        return appendenciesship_objects_created, appendenciesship_objects_already_exist
        # ------------------- Handle transfer appendenciesship ends here ------------------ #
    


    def handle_transfer_image_objectsship():
        # ------------------- Handle transfer image_objectsship starts here ------------------ #
        # Extract column names from the tables
        image_objectsship_table_data = cursor_object.execute('PRAGMA table_info(publications_feature_images)').fetchall()
        image_objectsship_column_names = [row[1] for row in image_objectsship_table_data]

        image_objectsship_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_feature_images"):
            image_objectsship_dictionary.append(dict(zip(image_objectsship_column_names, row)))

        image_objectsship_objects_created = 0
        image_objectsship_objects_already_exist = 0
        for dictionary in image_objectsship_dictionary:

            # add the data
            instance, created = models.ImageObjectship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print("New image_objectsship created with name:", instance)
                image_objectsship_objects_created += 1
            else:
                print("New image_objectsship already exists with name:", instance)
                appendenciesship_objects_already_exist += 1

        return image_objectsship_objects_created, image_objectsship_objects_already_exist



    def handle_transfer_publication_topics():
        # ------------------- Handle transfer publication_topics starts here ------------------ #
        # Extract column names from the tables
        publication_topics_table_data = cursor_object.execute('PRAGMA table_info(publications_publication_topics)').fetchall()
        publication_topics_column_names = [row[1] for row in publication_topics_table_data]  # Extract column names

        publication_topics_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_publication_topics"):
            publication_topics_dictionary.append(dict(zip(publication_topics_column_names, row)))

        publication_topics_objects_created = 0
        publication_topics_objects_already_exist = 0
        for dictionary in publication_topics_dictionary:
            
            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string

            
            Publication.objects.get(id=1)
            instance, created = models.Topicship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print("New publication_topics created with id:", instance.id)
                publication_topics_objects_created += 1
            else:
                print("publication_topics already exists with id:", instance.id)
                publication_topics_objects_already_exist += 1

        return publication_topics_objects_created, publication_topics_objects_already_exist
        # ------------------- Handle transfer publication_topics ends here ------------------ #
    
    




    def handle_transfer_publication_keywords():
        # ------------------- Handle transfer publication_keywords starts here ------------------ #
        # Extract column names from the tables
        publication_keywords_table_data = cursor_object.execute('PRAGMA table_info(publications_publication_keywords)').fetchall()
        publication_keywords_column_names = [row[1] for row in publication_keywords_table_data]  # Extract column names

        publication_keywords_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_publication_keywords"):
            publication_keywords_dictionary.append(dict(zip(publication_keywords_column_names, row)))

        publication_keywords_objects_created = 0
        publication_keywords_objects_already_exist = 0
        for dictionary in publication_keywords_dictionary:

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string


            # add the data
            instance, created = models.Keywordship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print("New publication_keywords created with id:", instance.id)
                publication_keywords_objects_created += 1
            else:
                print("publication_keywords already exists with id:", instance.id)
                publication_keywords_objects_already_exist += 1

        return publication_keywords_objects_created, publication_keywords_objects_already_exist
        # ------------------- Handle transfer publication_keywords ends here ------------------ #




    def handle_transfer_authorship():
        # ------------------- Handle transfer authorship starts here ------------------ #
        # Extract column names from the tables
        authorship_table_data = cursor_object.execute('PRAGMA table_info(publications_authorship)').fetchall()
        authorship_column_names = [row[1] for row in authorship_table_data]  # Extract column names

        author_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_authorship"):
            author_dictionary.append(dict(zip(authorship_column_names, row)))

        author_objects_created = 0
        author_objects_already_exist = 0
        for dictionary in author_dictionary:

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string


            # add the data
            instance, created = models.Authorship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print(f"New authorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                author_objects_created += 1
            else:
                print(f"New authorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                author_objects_already_exist += 1
            
        return author_objects_created, author_objects_already_exist
        # ------------------- Handle transfer authorship starts here ------------------ #



    def handle_transfer_editorship():
        # ------------------- Handle transfer editorship starts here ------------------ #
        # Extract column names from the tables
        editorship_table_data = cursor_object.execute('PRAGMA table_info(publications_editorship)').fetchall()
        editorship_column_names = [row[1] for row in editorship_table_data]  # Extract column names

        editor_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_editorship"):
            editor_dictionary.append(dict(zip(editorship_column_names, row)))

        editor_objects_created = 0
        editor_objects_already_exist = 0
        for dictionary in editor_dictionary:

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string


            # add the data
            instance, created = models.Editorship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print(f"New editorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                editor_objects_created += 1
            else:
                print(f"New editorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                editor_objects_already_exist += 1
            
        return editor_objects_created, editor_objects_already_exist
        # ------------------- Handle transfer editorship ends here ------------------ #


    def handle_transfer_supervisorship():
        # ------------------- Handle transfer supervisorship starts here ------------------ #

        # Extract column names from the tables
        supervisorship_table_data = cursor_object.execute('PRAGMA table_info(publications_supervisorship)').fetchall()  # GET AUTHOR TABLE INFO
        supervisorship_column_names = [
            row[1] for row in supervisorship_table_data]  # Extract column names

        supervisor_dictionary = []
        for row in cursor_object.execute("SELECT * FROM publications_supervisorship"):
            supervisor_dictionary.append(dict(zip(supervisorship_column_names, row)))

        supervisor_objects_created = 0
        supervisor_objects_already_exist = 0
        for dictionary in supervisor_dictionary:

            # This part replace invalid characters to valid characters, for example '‐' (8211) to this '-' (45)
            for key, value in dictionary.items():
                input_string = str(value)
                while True:
                    invalid_indices = check_string(input_string)
                    if not invalid_indices:
                        break
                    for i in invalid_indices:
                        invalid_char = input_string[i]
                        if invalid_char in invalid_to_valid:
                            replacement = invalid_to_valid[invalid_char]
                            input_string = input_string[:i] + replacement + input_string[i+1:]
                            dictionary[key] = input_string


            # add the data
            instance, created = models.Supervisorship.objects.get_or_create(id=dictionary['id'], defaults=dictionary)

            if created:
                print(f"New supervisorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                supervisor_objects_created += 1
            else:
                print(f"New supervisorship created with person_id {instance.person_id}, publication_id {instance.publication_id} and id {instance.id}")
                supervisor_objects_already_exist += 1
        
        return supervisor_objects_created, supervisor_objects_already_exist
        # ------------------- Handle transfer supervisorship ends here ------------------ #
    




    # ------------------- IMPORTING TABLES TABLES BELOW STARTS HERE ------------------ #
    # ------------------- journal (DONE), pubtype (DONE), topic (DONE), keyword (DONE)  ------------------ #
    journal_objects_created, journal_objects_alerady_exists = handle_transfer_journal()
    pubtype_objects_created, pubtype_objects_already_exist = handle_transfer_pubtype()
    topic_objects_created, topic_objects_already_exist = handle_transfer_topic()
    keyword_objects_created, keyword_objects_already_exist = handle_transfer_keyword()
    # ------------------- IMPORTING TABLES TABLES ENDS HERE ------------------ #




    # ------------------- IMPORTING TABLES TABLES BELOW STARTS HERE ------------------ #
    # ------------------- person (Done), publication (Done), file (Done), publication_topics (manytomany) (Done), publication_keywords (manytomany) (Done), authorship (Done), editorship (Done), supervisorship (Done) ------------------ #
    person_objects_created, person_objects_already_exist = handle_transfer_person()
    file_objects_created, file_objects_already_exist = handle_transfer_file()
    publication_objects_created, publication_objects_already_exist = handle_transfer_publication()
    appendenciesship_objects_created, appendenciesship_objects_already_exist = handle_transfer_appendenciesship()
    publication_topics_objects_created, publication_topics_objects_already_exist = handle_transfer_publication_topics()
    publication_keywords_objects_created, publication_keywords_objects_already_exist = handle_transfer_publication_keywords()
    author_objects_created, author_objects_already_exist = handle_transfer_authorship()
    editor_objects_created, editor_objects_already_exist = handle_transfer_editorship()
    supervisor_objects_created, supervisor_objects_already_exist = handle_transfer_supervisorship()
    image_objects_created, image_objects_already_exist = handle_transfer_Image_objects()
    # image_objectsship_objects_created, image_objectsship_objects_already_exist = handle_transfer_image_objectsship()
    # ------------------- IMPORTING TABLES TABLES ENDS HERE ------------------ #




    # ------------------- PRINTING TABLES TABLES BELOW STARTS HERE ------------------ #
    # ------------------- journal (DONE), pubtype (DONE), topic (DONE), keyword (DONE)  ------------------ #
    # print total number of journal_objects_created
    print("Total number of journal objects created:", journal_objects_created)
    print("Total number of journal objects that already exist", journal_objects_alerady_exists)

    # print total number of pubtype_objects_created
    print("Total number of pubtype objects created:", pubtype_objects_created)
    print("Total number of pubtype objects that already exist", pubtype_objects_already_exist)
    
    # print total number of topic_objects_created
    print("Total number of topic objects created:",  topic_objects_created)
    print("Total number of topic objects that already exist", topic_objects_already_exist)
    
    # print total number of keyword_objects_created
    print("Total number of keyword objects created:", keyword_objects_created)
    print("Total number of keyword objects that already exist", keyword_objects_already_exist)

    # ------------------- PRINTING TABLES TABLES ENDS HERE ------------------ #


    # Print handle_transfer_Image_objects()
    # handle_transfer_Image_objects()

    # print image_objectsship_objects_created, image_objectsship_objects_already_exist
    # print("Total number of image_objectsship objects created:", image_objectsship_objects_created)
    # print("Total number of image_objectsship objects that already exist", image_objectsship_objects_already_exist)


    print("Total number of image objects created:", image_objects_created)
    print("Total number of image objects that already exist", image_objects_already_exist)

    # ------------------- PRINTING TABLES TABLES BELOW STARTS HERE ------------------ #
    # ------------------- person, publication, topics (manytomany), publication_keywords (manytomany), authorship, editorship, supervisorship ------------------ #
    # print total number of person_objects_created
    print("Total number of person objects created:", person_objects_created)
    print("Total number of person objects that already exist", person_objects_already_exist)
    
    # print total number of file_objects_created
    print("Total number of file objects created:", file_objects_created)
    print("Total number of file objects that already exist", file_objects_already_exist)

    # print total number of publication_objects_created
    print("Total number of publication objects created:", publication_objects_created)
    print("Total number of publication objects that already exist", publication_objects_already_exist)

    # print total number of appendenciesship_objects_created
    print("Total number of appendenciesship objects created:", appendenciesship_objects_created)
    print("Total number of appendenciesship objects that already exist", appendenciesship_objects_already_exist)

    # print total number of topics_objects_created
    print("Total number of topics objects created:", publication_topics_objects_created)
    print("Total number of topics objects that already exist", publication_topics_objects_already_exist)

    # print total number of publication_keywords_objects_created
    print("Total number of publication_keywords objects created:", publication_keywords_objects_created)
    print("Total number of publication_keywords objects that already exist", publication_keywords_objects_already_exist)

    # print total number of author_objects_created
    print("Total number of author objects created:", author_objects_created)
    print("Total number of author objects that already exist", author_objects_already_exist)

    # print total number of editor_objects_created
    print("Total number of editor objects created:", editor_objects_created)
    print("Total number of editor objects that already exist", editor_objects_already_exist)

    # print total number of supervisor_objects_created
    print("Total number of supervisor objects created:", supervisor_objects_created)
    print("Total number of supervisor objects that already exist", supervisor_objects_already_exist)
    # ------------------- person, publication, topics (manytomany), publication_keywords (manytomany), authorship, editorship, supervisorship ------------------ #
    # ------------------- PRINTING TABLES TABLES BELOW ENDS HERE ------------------ #


    exit()


if __name__ == '__main__':
    run()
