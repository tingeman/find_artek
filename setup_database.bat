@set basepath=c:\thin\www\apps\find_artek
@set path=%path%;c:\spatialite-tools

@echo off

REM Remove previous migrations
echo. 
echo --------------------------------------
echo Removing previous migrations...
echo --------------------------------------
echo. 
cd %basepath%\find_artek\publications\migrations
del *.*
echo. 
echo --------------------------------------
echo Removing database...
echo --------------------------------------
echo. 
cd %basepath%
del find_artek.sqlite

echo. 
echo --------------------------------------
echo Creating new database... and setting pedelissions...
echo --------------------------------------
echo. 
cd %basepath%
spatialite find_artek.sqlite < init_spatialite-2.3.sql
spatialite find_artek.sqlite < init_google_spherical_projection_EPSG900913.sql
REM chmod 0777 find_artek.sqlite
cd ..
REM chmod 0777 find_artek

pause

echo. 
echo --------------------------------------
echo Renaming models.py to bak_models.py and deleting models.pyc
echo --------------------------------------
echo. 
cd %basepath%\find_artek\publications\
del *.pyc
rename models.py bak_models.py

echo. 
echo --------------------------------------
echo Running syncdb...
echo --------------------------------------
echo. 
cd %basepath%
python manage.py syncdb

echo. 
echo --------------------------------------
echo Renaming bak_models.py to models.py
echo --------------------------------------
echo. 
cd %basepath%\find_artek\publications\
rename bak_models.py models.py

echo. 
echo --------------------------------------
echo Now run initial migration...
echo --------------------------------------
echo. 

cd %basepath%
python manage.py schemamigration publications --initial
python manage.py migrate publications

