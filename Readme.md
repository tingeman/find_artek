cd app-main && source venv/bin/activate && python manage.py runserver 0.0.0.0:80

docker run --rm -it --volume find-artek-httpd-server:/temp ubuntu /bin/bash


docker-compose up


python manage.py collectstatic