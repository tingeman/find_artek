#!bin/bash

# Define the default values for the named parameters
SKIP_DATA_TRANSFER=0
PROMPT_BEFORE_NEXT_PROBLEM=0

# Parse the named parameters
while [ $# -gt 0 ]; do

    if [[ $1 == *"--"* ]]
    then
        param="${1/--/}"
        declare $param="$2"

        # if $param is skip-data-transfer
        if [[ $param == "skip-data-transfer" ]]; then
            # Check if the value is true
            if [[ $2 == "true" ]]; then
                # Set the value to 1
                SKIP_DATA_TRANSFER=1
            fi
        fi

        # if $param is prompt-before-next-problem
        if [[ $param == "prompt-before-next-problem" ]]; then
            # Check if the value is true
            if [[ $2 == "true" ]]; then
                # Set the value to 1
                PROMPT_BEFORE_NEXT_PROBLEM=1
            fi
        fi

        # echo $param $1 $2 # Optional to see the parameter:value result
    fi

  shift 1 # rykker positionelle parameter en gang til venstre
done


# ---------------- # PROBLEM 1 STARTS HERE # ---------------- #
# ---------------- # This part solves problem 1 out to 2 problems # ---------------- #
# Problem 1 is to transfer the data successfully, keeping the key relationships, between the tables, so the models work properbly
# Problem 2 is to rafactor the models, so they are easier to read (my excusion for me to tinkering with the models).

#

PUBLICATION_ROOT='/usr/src/app/find_artek/publications'
APP_ROOT='/usr/src/app/find_artek'

# This script migrate data from the old database into the new database. When this script is running it always runs into a empty database.

# Echo running implement_models script
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

# The purpose is to run a debug session separately in the datatransfer_script.py script, then you can press enter in the terminal afterwards.
# If run the command like this: bash publications/datatransfer_script.sh --skip-data-transfer --prompt-before-next-problem
# Check if the skip data transfer option was specified
if [[ $SKIP_DATA_TRANSFER -eq 0 ]]; then
    # Do the data transfer
    echo "Performing data transfer..."
    # ...
    # Run the script that migrate data from the old database to the new database
    python ${APP_ROOT}/manage.py runscript publications.datatransfer_script
else
    echo "Skipping data transfer..."
fi
# ---------------- Migrate data ends here ---------------- #

# ---------------- # PROBLEM 1 ENDS HERE # ---------------- #




# Check if the prompt before problem 2 option was specified
if [[ $PROMPT_BEFORE_NEXT_PROBLEM -eq 1 ]]; then
  # Prompt the user before running problem 2
  read -p "Press [Enter] to run problem 2..."
fi


# ---------------- # PROBLEM 2 STARTS HERE # ---------------- #
# ---------------- Refactor models starts here ---------------- #


# Implement the racfactored models
python ${APP_ROOT}/manage.py makemigrations publications && python ${APP_ROOT}/manage.py migrate publications
# ---------------- Refactor models ends here ---------------- #
# ---------------- # PROBLEM 2 ENDS HERE # ---------------- #