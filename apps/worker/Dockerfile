FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY packages/shared-python /app/packages/shared-python
COPY apps/worker /app/apps/worker
COPY pyproject.toml /app/pyproject.toml

RUN uv sync --package drishtiai-worker --no-dev

WORKDIR /app/apps/worker

CMD ["uv", "run", "celery", "-A", "drishtiai_worker.celery_app", "worker", \
     "--loglevel=info", "--concurrency=4", "-Q", "celery,reports,retention,export"]
