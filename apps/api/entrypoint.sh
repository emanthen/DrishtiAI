#!/bin/sh
set -e

echo "Running Alembic migrations..."
cd /app/packages/shared-python
uv run alembic upgrade head
cd /app/apps/api

echo "Starting API server..."
exec uv run uvicorn drishtiai_api.main:app --host 0.0.0.0 --port 8000
