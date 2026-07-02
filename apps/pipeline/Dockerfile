# Phase 0: minimal stub image.
# Phase 1: this will be replaced with a DeepStream base image.
# Base: nvcr.io/nvidia/deepstream:7.0-triton-multiarch (Phase 1+)
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY packages/shared-python /app/packages/shared-python
COPY apps/pipeline /app/apps/pipeline
COPY pyproject.toml /app/pyproject.toml

RUN uv sync --package drishtiai-pipeline --no-dev

WORKDIR /app/apps/pipeline

CMD ["uv", "run", "python", "-m", "drishtiai_pipeline.main"]
