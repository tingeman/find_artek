cd app-main && source venv/bin/activate && python manage.py runserver 0.0.0.0:8000

docker run --rm -it --volume find-artek-httpd-server:/temp ubuntu /bin/bash