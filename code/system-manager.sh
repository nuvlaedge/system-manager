#!/bin/sh

set -xe

./check-requirements.py

gunicorn --bind=0.0.0.0:3636 --threads=2 --worker-class=gthread --workers=1 --reload wsgi:app --daemon

./run.py