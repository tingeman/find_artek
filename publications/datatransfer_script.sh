#!bin/bash

PUBLICATION_ROOT='/usr/src/app/find_artek/publications'
APP_ROOT='/usr/src/app/find_artek'

# This script migrate data from the old database into the new database. When this script is running it always runs into a enpty database.



# Echo running implement_models sciprt
echo "Running implement_models.sh"

# Drops database
echo 'DROP DATABASE IF EXISTS root_find_artek_v1_0_0;' | mysql -h database-service -u root -pnotSecureChangeMe
echo 'DATABASE HAS BEEN DELETED'

# Creates database
echo "CREATE DATABASE root_find_artek_v1_0_0 CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;" | mysql -h database-service -u root -pnotSecureChangeMe
echo 'DATABASE HAS BEEN CREATED'

# Delete migration folder 
# The folder is not relevant during transition period
if [ -d "${PUBLICATION_ROOT}/migrations" ]; then
    rm -rf ${PUBLICATION_ROOT}/migrations
    echo 'REMOVING MIGRATION FILES'
else
    echo "Directory does not exist. - no migrationfiles to delete"
fi


# ---------------- Migrate data starts here ---------------- #
# Create a backup file with a timestamp
TIMESTAMP=$(date +'%Y%m%d%H%M%S')
cp ${PUBLICATION_ROOT}/models.py "${PUBLICATION_ROOT}/backup/model_denmark_${TIMESTAMP}.py.bak"

# Using models that fits with the old app
# remove models.py if it exists
if [ -f "${PUBLICATION_ROOT}/models.py" ]; then
    rm ${PUBLICATION_ROOT}/models.py
    echo 'REMOVING models.py'
else
    echo "File does not exist. - no models.py to delete"
fi

# Copy models that look like old models
cp ${PUBLICATION_ROOT}/models_that_looks_like_old_models.py ${PUBLICATION_ROOT}/models.py

# Migrate basic django tables
python ${APP_ROOT}/manage.py migrate

# Migrate tables for the app
python ${APP_ROOT}/manage.py makemigrations publications && python ${APP_ROOT}/manage.py migrate publications

# Run the script that migrate data from the old database to the new database
python ${APP_ROOT}/manage.py runscript publications.datatransfer_script

# ---------------- Migrate data ends here ---------------- #

# ---------------- Update models starts here ---------------- #

# ---------------- Publication change variables: [authors editors supervisors] starts here ---------------- #

# Change from this:
    # # Use plural variable name for many-to-many relationship
    # authors = models.ManyToManyField(Person, through='Authorship', related_name='publication_author', blank=True, default=None)

    # editors = models.ManyToManyField(Person, through='Editorship', related_name='publication_editor', blank=True, default=None)

    # supervisors = models.ManyToManyField(Person, through='Supervisorship', related_name='publication_supervisor', blank=True, default=None)

# To this:
    # # Use plural variable name for many-to-many relationship
    # authorships = models.ManyToManyField(Person, through='Authorship', related_name='author_publication', blank=True, default=None)

    # editorships = models.ManyToManyField(Person, through='Editorship', related_name='editor_publication', blank=True, default=None)

    # supervisorships = models.ManyToManyField(Person, through='Supervisorship', related_name='supervisor_publication', blank=True, default=None)

# Define the old and new variable names
OLD_NAMES=("authors" "editors" "supervisors")
NEW_NAMES=("authorships" "editorships" "supervisorships")

# Loop over the old and new names and run the sed command for each pair
for i in "${!OLD_NAMES[@]}"; do
    OLD="${OLD_NAMES[$i]}"
    NEW="${NEW_NAMES[$i]}"
    sed -i "/$OLD = models.ManyToManyField(Person, through='\([A-Za-z]\+\)', related_name='\([A-Za-z_]\+\)', blank=True, default=None)/{s//${NEW} = models.ManyToManyField(Person, through='\1', related_name='\2', blank=True, default=None)/; t}; /$OLD = models.ManyToManyField(Person, through='\([A-Za-z]\+\)', related_name='\([A-Za-z_]\+ships\)', blank=True, default=None)/{s//${NEW} = models.ManyToManyField(Person, through='\1', related_name='\2_publication', blank=True, default=None)/; t}; /$OLD = models.ManyToManyField(Person, through='\([A-Za-z]\+\)', related_name='\([A-Za-z_]\+publication\)', blank=True, default=None)/!b; /$OLD = models.ManyToManyField(Person, through='\([A-Za-z]\+\)', related_name='\([A-Za-z_]\+publication\)', blank=True, default=None)/{s//${NEW} = models.ManyToManyField(Person, through='\1', related_name='\2', blank=True, default=None)/; t}" ${PUBLICATION_ROOT}/models.py
done


# Replace 'publication_author' with 'author_publication' in models.py
sed -i "s/related_name='publication_author'/related_name='author_publication'/" ${PUBLICATION_ROOT}/models.py

# Replace 'publication_editor' with 'editor_publication' in models.py
sed -i "s/related_name='publication_editor'/related_name='editor_publication'/" ${PUBLICATION_ROOT}/models.py

# Replace 'publication_supervisor' with 'supervisor_publication' in models.py
sed -i "s/related_name='publication_supervisor'/related_name='supervisor_publication'/" ${PUBLICATION_ROOT}/models.py

# ---------------- Publication change variables: [authors editors supervisors] ends here ---------------- #




# Migrate the new models 
python ${APP_ROOT}/manage.py makemigrations publications && python ${APP_ROOT}/manage.py migrate publications
# ---------------- Update models ends here ---------------- #
