#!/bin/sh
set -e

echo "Running Django migrations..."
uv run python manage.py migrate --noinput

echo "Collecting static files..."
uv run python manage.py collectstatic --noinput --clear

echo "Starting admin server..."
exec uv run gunicorn drishtiai_admin.wsgi:application \
    --bind 0.0.0.0:8001 \
    --workers 2 \
    --timeout 120
