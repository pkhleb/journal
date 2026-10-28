#!/bin/sh
set -e
python dev_bootstrap.py
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
