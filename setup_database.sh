echo which python

# Remove previous migrations
echo " "
echo "--------------------------------------"
echo "Removing previous migrations..."
echo "--------------------------------------"
echo " "
cd /home/bitnami/apps/find_artek/find_artek/publications/migrations
rm *

echo " "
echo "--------------------------------------"
echo "Removing database..."
echo "--------------------------------------"
echo " "
cd /home/bitnami/apps/find_artek
rm find_artek.sqlite

echo " "
echo "--------------------------------------"
echo "Creating new database... and setting permissions..."
echo "--------------------------------------"
echo " "
cd /home/bitnami/apps/find_artek
spatialite find_artek.sqlite < init_google_spherical_projection_EPSG900913.sql
chmod 0777 find_artek.sqlite
cd ..
chmod 0777 find_artek

echo " "
echo "--------------------------------------"
echo "Renaming models.py --> bak_models.py and deleting models.pyc"
echo "--------------------------------------"
echo " "
cd /home/bitnami/apps/find_artek/find_artek/publications/
rm ./models.pyc
mv models.py bak_models.py

echo " "
echo "--------------------------------------"
echo "Running syncdb..."
echo "--------------------------------------"
echo " "
cd /home/bitnami/apps/find_artek/
python manage.py syncdb

echo " "
echo "--------------------------------------"
echo "Renaming bak_models.py --> models.py"
echo "--------------------------------------"
echo " "
cd /home/bitnami/apps/find_artek/find_artek/publications/
mv bak_models.py models.py

echo " "
echo "--------------------------------------"
echo "Now run initial migration..."
echo "--------------------------------------"
echo " "

cd /home/bitnami/apps/find_artek/
sudo python manage.py schemamigration publications --initial
sudo python manage.py migrate publications

