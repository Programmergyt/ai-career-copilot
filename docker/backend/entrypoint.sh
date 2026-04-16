#!/bin/sh
set -e

python sql/init_db.py

exec uvicorn main:app --host "${FASTAPI_HOST:-0.0.0.0}" --port "${FASTAPI_PORT:-8000}"
