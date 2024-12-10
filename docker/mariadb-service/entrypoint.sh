#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# # Define the database connection details
# DB_USER="root"
# DB_PASSWORD="$MYSQL_ROOT_PASSWORD"
# DB_HOST="localhost"
# DB_NAME="your_database_name"
# BACKUP_FILE="/path/to/backup.sql"

# # Wait for the MariaDB server to start
# until mysqladmin ping -h "$DB_HOST" --silent; do
#   echo "Waiting for MariaDB to be available..."
#   sleep 1
# done

# # Check if the database is empty
# DB_EMPTY=$(mysql -u"$DB_USER" -p"$DB_PASSWORD" -h "$DB_HOST" -e "SHOW TABLES IN $DB_NAME;" 2>/dev/null | wc -l)

# if [ "$DB_EMPTY" -eq 0 ]; then
#   echo "Database is empty. Loading backup file..."
#   mysql -u"$DB_USER" -p"$DB_PASSWORD" -h "$DB_HOST" "$DB_NAME" < "$BACKUP_FILE"
#   echo "Backup file loaded successfully."
# else
#   echo "Database is not empty. Skipping backup restoration."
# fi

# Start the MariaDB server normally
exec "$@"