# Phase 1: CPU pipeline using OpenCV + PaddleOCR.
# Phase 2: Replace base with nvcr.io/nvidia/deepstream:7.0-triton-multiarch

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgomp1 libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY packages/shared-python /app/packages/shared-python
COPY apps/pipeline /app/apps/pipeline
COPY pyproject.toml /app/pyproject.toml

RUN uv sync --package drishtiai-pipeline --no-dev

# Pre-download PaddleOCR models so first-run doesn't require internet
# Models land in /root/.paddleocr/
RUN uv run python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en', show_log=False)" \
    || echo "Model download failed — will retry at runtime"

WORKDIR /app/apps/pipeline

CMD ["uv", "run", "python", "-m", "drishtiai_pipeline.main"]
