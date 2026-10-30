#!/bin/sh
set -e
alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --proxy-headers --forwarded-allow-ips 172.18.0.0/16 --port 8000
