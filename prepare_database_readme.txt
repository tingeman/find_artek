# steps to prepare find_artek database:

spatialite find_artek.sqlite < init_spatialite-2.3.sql
spatialite find_artek.sqlite < init_google_spherical_projection_EPSG900913.sql

# make sure models.py is empty! (Could rename to BAK_models.py)

sudo python manage.py syncdb      

# Answered yes to greate superuser: thin, e-mail tin@byg.dtu.dk

# Now copy the correct models.py (or write it...) 



# START HERE if starting from find_artek.sqlite.empty_copy

# Finally, check that all rights are granted to the database file (chmod 0777)
# AS WELL AS THE PARENT DIRECTORY!!!

sudo python manage.py schemamigration publications --initial
sudo python manage.py migrate publications


# Updates to the schemas upon changes to models.py of the 'publications' app:

sudo python manage.py schemamigration publications --auto
sudo python manage.py migrate publications

# To prepopulate after db creation:

sudo python manage.py shell
>>>> from find_artek.publications import prepopulate
>>>> prepopulate.populate_db()


# To load data into a table:

sudo python manage.py shell
>>>> from find_artek.publications import load_old_road_db
>>>> load_old_road_db.import_reports()