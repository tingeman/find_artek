#!/bin/bash

source /usr/src/venv/bin/activate && cd /usr/src/project/app-main && python manage.py runserver 0.0.0.0:8101 --settings find_artek.development_settings