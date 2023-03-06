#!bin/bash

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
if [ -d "/usr/src/app/find_artek/publications/migrations" ]; then
    rm -rf /usr/src/app/find_artek/publications/migrations
    echo 'REMOVING MIGRATION FILES'
else
    echo "Directory does not exist. - no migrationfiles to delete"
fi


# Migrate basic django tables
python /usr/src/app/find_artek/manage.py migrate

# Migrate tables for the app
python /usr/src/app/find_artek/manage.py makemigrations publications && python /usr/src/app/find_artek/manage.py migrate publications


