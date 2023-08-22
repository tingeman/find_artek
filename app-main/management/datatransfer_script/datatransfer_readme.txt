For at køre datatransfer gaa ind i debugger og start datatransfer_script.sh

sæt eventuelt et break point under 


    # Echo in green text 'starting datatransfer_script.py', sleep for 1 second, then echo in green text 'finished datatransfer_script.py'
    echo -e "\e[32mstarting datatransfer_script.py\e[0m"
    sleep 1
    python ${APP_ROOT}/manage.py runscript publications.datatransfer_script

    # Run the script that imports the spatial data
    # Echo in green text 'starting datatranser_feature_data.py', sleep for 1 second, then echo in green text 'finished datatranser_feature_data.py'
    echo -e "\e[32mstarting datatranser_feature_data.py\e[0m"
    python ${APP_ROOT}/manage.py runscript publications.datatranser_feature_data
    # Import the spatial data via the json file
    # Create the association with the publications

    # Echo in green text deleting users, that are not author, editor or supervisor
    echo -e "\e[32mdeleting users, that are not author, editor or supervisor\e[0m"
    python ${APP_ROOT}/manage.py runscript publications.delete_irrelevant_users
