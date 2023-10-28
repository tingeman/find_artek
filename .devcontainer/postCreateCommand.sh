#!/bin/bash


# cd ./app and remove venv if it exits, then rebuild venv, activate it, and install requirements
pwd && cd app-main && ls && rm -rf venv && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

git config --global user.email "victor.reipur@gmail.com"
git config --global user.name "Victor Reipur"
git config --global --add safe.directory /usr/src/project

apt-get update && apt-get install iputils-ping -y
