FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY packages/shared-python /app/packages/shared-python
COPY apps/admin /app/apps/admin
COPY pyproject.toml /app/pyproject.toml

RUN uv sync --package drishtiai-admin --no-dev

WORKDIR /app/apps/admin

EXPOSE 8001

CMD ["uv", "run", "python", "-m", "gunicorn", "drishtiai_admin.wsgi:application", \
     "--bind", "0.0.0.0:8001", "--workers", "2", "--timeout", "120"]
