import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://drishtiai:drishtiai@postgres:5432/drishtiai"
    redis_url: str = "redis://redis:6379/0"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "drishtiai"
    minio_secret_key: str = "change-me"
    minio_secure: bool = False
    minio_bucket_snapshots: str = "snapshots"

    # Which cameras to process (comma-separated UUIDs, or "all")
    pipeline_camera_ids: str = "all"

    # Frame sampling: process 1 out of every N frames
    pipeline_frame_sample: int = 5

    # Absolute floor — reads below this are discarded entirely
    pipeline_min_confidence: float = 0.40

    # Reads between min_confidence and this threshold go to the review queue
    pipeline_ocr_confidence_threshold: float = 0.70

    # Route low-confidence reads to review_queue table (the training data flywheel)
    pipeline_review_queue_enabled: bool = True

    # Deduplicate: suppress repeated reads of the same plate within N seconds
    pipeline_dedup_seconds: int = 5

    # Publish MJPEG frames to Redis for live view (every N processed frames)
    pipeline_mjpeg_every_n: int = 1

    # Multi-frame voter settings
    pipeline_voter_window_s: float = 4.0
    pipeline_voter_exit_gap_s: float = 1.5
    pipeline_voter_min_reads: int = 2

    # Capture backend: "gstreamer" (default, falls back to opencv) or "opencv"
    pipeline_capture_backend: str = "gstreamer"

    # OCR tuning
    pipeline_ocr_use_gpu: bool = False      # set True on CUDA hosts
    pipeline_ocr_two_stage: bool = True     # OpenCV candidate detection before full OCR
    pipeline_ocr_preprocess: bool = True    # CLAHE + unsharp-mask on crops

    log_level: str = "INFO"

    @field_validator("pipeline_camera_ids")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


settings = PipelineSettings()
