import json, os
import pathlib
import sqlite3

from django.conf import settings




def connect_to_old_database():
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

    return cursor_object
    # ------------------- Connect to the old sqlite database ------------------ #




def run():
    base_path = os.path.dirname(os.path.abspath(__file__))  # Get the directory where the script is located
    json_path = os.path.join(base_path, 'files_not_in_database.json')  # Construct the full path to the JSON file

    file_not_in_new_database_but_in_old_database = []
    file_not_in_old_database = []
    
    with open(json_path) as file:  # Use the full path to open the file
        data = json.load(file)
        # Process the data from the JSON file
    
    # create a cursor object
    cursor_object = connect_to_old_database()

    # extract the table names from publications_publication
    publications_publication_table_names = cursor_object.execute('PRAGMA table_info(publications_publication)').fetchall() 

    publication_dictionary = []

    for row in cursor_object.execute("SELECT * FROM publications_publication"):
        publication_dictionary.append(dict(zip(publications_publication_table_names[0][1], row)))
    
    print(publication_dictionary)
    
    # cursor_object.execute("SELECT name FROM sqlite_master WHERE type='table';")




    # # check if the file exists in the old database
    # for file in data:
    #     # cursor_object.execute("SELECT * FROM publications_publication WHERE number='02-11'", (file,))        
    #     rows = cursor_object.fetchall()
    #     if len(rows) == 0:
    #         file_not_in_old_database.append(file)
    #     else:
    #         file_not_in_new_database_but_in_old_database.append(file)

    # check if the file exists in the old database
    for file in data:
        # Use ? as a placeholder for parameters in the SQL query
        # cursor_object.execute("SELECT * FROM publications_publication WHERE number=?", (file[0],))   
        cursor_object.execute("SELECT * FROM publications_publication")     

        publication_rows = cursor_object.fetchall()

        # check if the file exists in the old database
        
        rows = 0

        if len(rows) == 0: # then try again by searching for the file name without the extension in the title
            # cursor_object.execute("SELECT * FROM publications_publication WHERE title LIKE ?", ('%' + file[:-4] + '%',))



            file_not_in_old_database.append(file)
        else:
            file_not_in_new_database_but_in_old_database.append(file)

        

        # export the files_not_in_database to a json file
        base_path = os.path.dirname(os.path.abspath(__file__))
        json_file_path = os.path.join(base_path, 'file_not_in_old_database.json')

        with open(json_file_path, 'w') as outfile:
            json.dump(file_not_in_old_database, outfile, indent=4)


        # export the files_not_in_database to a json file
        base_path = os.path.dirname(os.path.abspath(__file__))
        json_file_path = os.path.join(base_path, 'file_not_in_new_database_but_in_old_database.json')


        with open(json_file_path, 'w') as outfile:
            json.dump(file_not_in_new_database_but_in_old_database, outfile, indent=4)



if __name__ == '__main__':
    run()
