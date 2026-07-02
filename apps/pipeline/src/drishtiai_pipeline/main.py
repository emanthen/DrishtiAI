"""
Pipeline entry point.

Phase 0: stub that exits cleanly with a clear message.
Phase 1: single-camera GStreamer pipeline with plate detection + OCR.
Phase 2: DeepStream multi-stream pipeline.
"""
import sys


def main() -> None:
    print(
        "DrishtiAI pipeline — not yet implemented. "
        "This service will be implemented in Phase 1.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
