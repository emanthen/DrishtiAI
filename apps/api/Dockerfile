FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY packages/shared-python /app/packages/shared-python
COPY apps/api /app/apps/api
COPY pyproject.toml /app/pyproject.toml

RUN uv sync --package drishtiai-api --no-dev

WORKDIR /app/apps/api

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "drishtiai_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
