#!bin/bash

# Define the default values for the named parameters
SKIP_DATA_TRANSFER=0
PROMPT_BEFORE_NEXT_PROBLEM=0
USING_SQLITE=0

script_dir="$(dirname "$(realpath "$0")")"
# test=$(bash -c "cd $(dirname $script_dir)/.. && pwd")
# echo $test
# exit 1
APP_ROOT=$(bash -c "cd $(dirname $script_dir)/.. && pwd")
PUBLICATION_ROOT="${APP_ROOT}/publications"
# ls -al $APP_ROOT
# bash -c "cd $APP_ROOT && pwd && ls -al"
# echo $APP_ROOT

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

        # if $param is prompt-before-next-problem
        if [[ $param == "use-sqlite" ]]; then
            # Check if the value is true
            if [[ $2 == "true" ]]; then
                # Set the value to 1
                USING_SQLITE=1
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

# if using USING_SQLITE, then # if else USING_MYSQL 
if [[ $USING_SQLITE -eq 1 ]]; then

    echo "using sqlite"
    # ls -al $APP_ROOT
    if [ -f ${APP_ROOT}/find_artek_new.sqlite ]; then
        rm $APP_ROOT/find_artek_new.sqlite
        echo 'REMOVING find_artek_new.sqlite'
    else
        echo "File does not exist. - no find_artek_new.sqlite to delete"
    fi

else
    echo "using mysql"

    # Adjust these variables as needed
    DB_HOST="find-artek-mariadb-service"
    DB_USER="mariadb"
    DB_PASSWORD="mariadb"
    DB_NAME="find-artek-django"

    # Drops the existing database
    echo "DROP DATABASE IF EXISTS \`${DB_NAME}\`;" | mysql -h ${DB_HOST} -u ${DB_USER} -p${DB_PASSWORD}
    echo 'DATABASE HAS BEEN DELETED'

    # Creates a new database
    echo "CREATE DATABASE \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;" | mysql -h ${DB_HOST} -u ${DB_USER} -p${DB_PASSWORD}

    echo 'DATABASE HAS BEEN CREATED'
fi






# This script migrate data from the old database into the new database. When this script is running it always runs into a empty database.

# Echo running implement_models script
echo "Running implement_models.sh"


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
cp ${PUBLICATION_ROOT}/models.py "${APP_ROOT}/management/datatransfer_script/backup/model_denmark_${TIMESTAMP}.py.bak"

# Using models that fits with the old app
# remove models.py if it exists
if [ -f "${PUBLICATION_ROOT}/models.py" ]; then
    rm ${PUBLICATION_ROOT}/models.py
    echo 'REMOVING models.py'
else
    echo "File does not exist. - no models.py to delete"
fi

# Copy models that look like old models
cp ${APP_ROOT}/management/datatransfer_script/models_that_looks_like_old_models.py ${PUBLICATION_ROOT}/models.py

source ${APP_ROOT}/venv/bin/activate

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
    
    # I started running the scripts in this order, maybe it does not matter

    # Run the script that migrate data from the old database to the new database
    
    # Echo in green text 'starting datatransfer_script.py', sleep for 1 second, then echo in green text 'finished datatransfer_script.py'
    echo -e "\e[32mstarting datatransfer_script.py\e[0m"
    sleep 1
    python ${APP_ROOT}/manage.py runscript management.datatransfer_script.datatransfer_script

    # Run the script that imports the spatial data
    # Echo in green text 'starting datatranser_feature_data.py', sleep for 1 second, then echo in green text 'finished datatranser_feature_data.py'
    echo -e "\e[32mstarting datatranser_feature_data.py\e[0m"
    python ${APP_ROOT}/manage.py runscript management.datatransfer_script.datatranser_feature_data
    # Import the spatial data via the json file
    # Create the association with the publications

    # Echo in green text deleting users, that are not author, editor or supervisor
    echo -e "\e[32mdeleting users, that are not author, editor or supervisor\e[0m"
    python ${APP_ROOT}/manage.py runscript management.datatransfer_script.delete_irrelevant_users



    # # Run the script that creates the association between the geo locations and the publications papers.
    # python ${APP_ROOT}/manage.py runscript publications.datatransfer_association
else
    echo "Skipping data transfer..."
fi

# Echo in green Problem 1 is solved
echo -e "\e[32mProblem 1 is solved\e[0m"
sleep 1
# ---------------- Migrate data ends here ---------------- #

# ---------------- # PROBLEM 1 ENDS HERE # ---------------- #




# Check if the prompt before problem 2 option was specified
if [[ $PROMPT_BEFORE_NEXT_PROBLEM -eq 1 ]]; then
  # Prompt the user before running problem 2
  read -p "Press [Enter] to run problem 2..."
fi


# ---------------- # PROBLEM 2 STARTS HERE # ---------------- #
# ---------------- Refactor models starts here ---------------- #

# in find_artek/publications/models.py
# replace "created_date = models.DateTimeField() # when done moving data use these parameters: auto_now_add=True" with "created_date = models.DateTimeField(auto_now_add=True)"
# replace "modified_date = models.DateTimeField() # when done moving data use these parameters: auto_now=True" with "modified_date = models.DateTimeField(auto_now=True)"
sed -i -e 's/created_date = models.DateTimeField() # when done moving data use these parameters: auto_now_add=True/created_date = models.DateTimeField(auto_now_add=True)/' -e 's/modified_date = models.DateTimeField() # when done moving data use these parameters: auto_now=True/modified_date = models.DateTimeField(auto_now=True)/' ${PUBLICATION_ROOT}/models.py


# Implement the refactored models
python ${APP_ROOT}/manage.py makemigrations publications && python ${APP_ROOT}/manage.py migrate publications


# Run unittest
# Echo in green text 'starting unittest', sleep for 1 second, then echo in green text 'finished unittest'
echo -e "\e[32mstarting unittest\e[0m"
sleep 1
python ${APP_ROOT}/manage.py test publications.tests
# ---------------- Refactor models ends here ---------------- #
# ---------------- # PROBLEM 2 ENDS HERE # ---------------- #