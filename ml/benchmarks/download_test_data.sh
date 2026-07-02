#!/usr/bin/env bash
# Download a CC-licensed test video with visible licence plates.
# Updates deploy/compose/test-media/test.mp4 and ml/benchmarks/phase1.mp4
#
# Usage: bash ml/benchmarks/download_test_data.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MEDIA_DIR="$REPO_ROOT/deploy/compose/test-media"
BENCH_DIR="$SCRIPT_DIR"

echo "Downloading Phase 1 test video..."

# Option A: Use a short CC0 dashcam clip from Wikimedia Commons
# Replace this URL with an actual CC-licensed dashcam video containing plates.
VIDEO_URL="${PHASE1_VIDEO_URL:-}"

if [ -z "$VIDEO_URL" ]; then
  echo "ERROR: Set PHASE1_VIDEO_URL to a URL pointing to a CC-licensed dashcam video."
  echo "       The video must contain clearly visible English/Latin licence plates."
  echo ""
  echo "       Example:"
  echo "         export PHASE1_VIDEO_URL='https://example.com/dashcam.mp4'"
  echo "         bash ml/benchmarks/download_test_data.sh"
  exit 1
fi

mkdir -p "$MEDIA_DIR"
curl -L "$VIDEO_URL" -o "$MEDIA_DIR/test.mp4"
cp "$MEDIA_DIR/test.mp4" "$BENCH_DIR/phase1.mp4"

echo "Done. Videos saved to:"
echo "  $MEDIA_DIR/test.mp4    (used by mediamtx RTSP server)"
echo "  $BENCH_DIR/phase1.mp4  (used by eval scripts)"
echo ""
echo "Next: update ml/benchmarks/phase1_gt.json with the correct ground-truth plates."
