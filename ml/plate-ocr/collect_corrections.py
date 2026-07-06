"""
Pull guard-reviewed corrections from the DrishtiAI review queue and store them
as labelled training crops in ml/plate-ocr/corrections/.

Each correction produces two files:
    corrections/<crop_id>.jpg   — plate crop image
    corrections/<crop_id>.txt   — corrected plate text

Usage:
    uv run python ml/plate-ocr/collect_corrections.py \
        --api-url http://localhost:8000 \
        --token   $ACCESS_TOKEN \
        --out-dir ml/plate-ocr/corrections/

    # Or export corrections stats without downloading:
    uv run python ml/plate-ocr/collect_corrections.py --stats-only

The script is idempotent — already-downloaded crops are skipped.
Progress is tracked in ml/plate-ocr/corrections/.state.json.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import datetime, timezone


STATE_FILE = pathlib.Path("ml/plate-ocr/corrections/.state.json")


def _load_state(state_path: pathlib.Path) -> dict:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {"downloaded": [], "last_run": None, "total_corrections": 0}


def _save_state(state_path: pathlib.Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def collect(
    api_url: str,
    token: str,
    out_dir: pathlib.Path,
    *,
    stats_only: bool = False,
    limit: int = 1000,
) -> int:
    try:
        import requests  # type: ignore[import]
    except ImportError:
        raise SystemExit("requests not installed — run: uv add requests")

    out_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state(STATE_FILE)
    already_downloaded: set[str] = set(state["downloaded"])

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"

    # Fetch all resolved review queue items (status=corrected)
    page = 1
    new_count = 0
    skipped = 0

    while True:
        resp = session.get(
            f"{api_url}/review-queue",
            params={"status": "corrected", "per_page": 100, "page": page},
            timeout=30,
        )
        if resp.status_code == 404:
            print(
                "WARNING: /review-queue endpoint not found. "
                "Ensure you're running against an API with the review queue feature.",
                file=sys.stderr,
            )
            break
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data

        if not items:
            break

        for item in items:
            crop_id = str(item.get("id", item.get("crop_id", "")))
            corrected_text = str(item.get("corrected_text", item.get("correction", ""))).strip()
            crop_url = item.get("crop_url", "")

            if not crop_id or not corrected_text:
                continue

            if crop_id in already_downloaded:
                skipped += 1
                continue

            if stats_only:
                new_count += 1
                continue

            # Download crop image
            if crop_url:
                img_resp = session.get(crop_url, timeout=30)
                if img_resp.status_code == 200:
                    img_path = out_dir / f"{crop_id}.jpg"
                    img_path.write_bytes(img_resp.content)
                else:
                    print(f"  WARN: could not download crop {crop_id} ({img_resp.status_code})", file=sys.stderr)
                    continue

            txt_path = out_dir / f"{crop_id}.txt"
            txt_path.write_text(corrected_text.upper(), encoding="utf-8")

            already_downloaded.add(crop_id)
            new_count += 1

            if new_count >= limit:
                print(f"  Hit limit of {limit} — use --limit to increase", file=sys.stderr)
                break

        if new_count >= limit or not data.get("next") if isinstance(data, dict) else len(items) < 100:
            break
        page += 1

    if not stats_only:
        state["downloaded"] = sorted(already_downloaded)
        state["last_run"] = datetime.now(tz=timezone.utc).isoformat()
        state["total_corrections"] = len(already_downloaded)
        _save_state(STATE_FILE, state)

    return new_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect OCR corrections from review queue")
    parser.add_argument("--api-url",    default=os.environ.get("DRISHTIAI_API_URL", "http://localhost:8000"))
    parser.add_argument("--token",      default=os.environ.get("ACCESS_TOKEN", ""))
    parser.add_argument("--out-dir",    default="ml/plate-ocr/corrections", type=pathlib.Path)
    parser.add_argument("--limit",      default=1000, type=int)
    parser.add_argument("--stats-only", action="store_true", help="Print stats only, no download")
    args = parser.parse_args()

    if not args.token and not args.stats_only:
        raise SystemExit(
            "No API token — set ACCESS_TOKEN env var or pass --token. "
            "Get a token with: curl -X POST http://localhost:8000/auth/login …"
        )

    state = _load_state(STATE_FILE)
    already_have = len(state["downloaded"])
    print(f"Already downloaded: {already_have} corrections")

    new_count = collect(
        args.api_url,
        args.token,
        args.out_dir,
        stats_only=args.stats_only,
        limit=args.limit,
    )

    total = already_have + new_count if args.stats_only else len(_load_state(STATE_FILE)["downloaded"])
    print(f"New corrections: {new_count}")
    print(f"Total corrections: {total}")

    TARGET = 500
    if total < TARGET:
        print(f"\nNeed {TARGET - total} more corrections before fine-tuning. Keep collecting.")
    else:
        print(f"\nReached {TARGET}+ corrections. Ready to run: make train-nepali-ocr")


if __name__ == "__main__":
    main()
