# Phase 1: CPU pipeline using OpenCV + PaddleOCR.
# Phase 2: Replace base with nvcr.io/nvidia/deepstream:7.0-triton-multiarch

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgomp1 libgl1 libsm6 libxrender1 libxext6 \
    curl \
    python3-gi gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly gstreamer1.0-rtsp gstreamer1.0-libav \
    gstreamer1.0-tools libgstreamer1.0-0 \
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
