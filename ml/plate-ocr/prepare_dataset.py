"""
Convert labelled plate crops into PaddleOCR training format.

Input:
    ml/plate-ocr/corrections/<id>.jpg + <id>.txt   (from collect_corrections.py)
    ml/benchmarks/nepali_plates_test/*.jpg          (optional synthetic crops)
    ml/benchmarks/nepali_gt.json                    (labels for synthetic crops)

Output:
    ml/plate-ocr/data/train/                        train images
    ml/plate-ocr/data/val/                          val images
    ml/plate-ocr/data/train_list.txt                PaddleOCR label list (80%)
    ml/plate-ocr/data/val_list.txt                  PaddleOCR label list (20%)

PaddleOCR label list format (one entry per line):
    <relative_image_path>\t<label_text>

Example:
    train/00001.jpg	BA1PA0001

Usage:
    uv run python ml/plate-ocr/prepare_dataset.py \
        --corrections  ml/plate-ocr/corrections/ \
        --synthetic    ml/benchmarks/nepali_plates_test/ \
        --synthetic-gt ml/benchmarks/nepali_gt.json \
        --out-dir      ml/plate-ocr/data/ \
        --val-split    0.20 \
        --seed         42
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import shutil


def _normalize(text: str) -> str:
    return text.upper().replace(" ", "").replace("-", "").strip()


def _load_corrections(corrections_dir: pathlib.Path) -> list[tuple[pathlib.Path, str]]:
    pairs: list[tuple[pathlib.Path, str]] = []
    if not corrections_dir.exists():
        return pairs
    for txt_file in sorted(corrections_dir.glob("*.txt")):
        if txt_file.name.startswith("."):
            continue
        label = _normalize(txt_file.read_text(encoding="utf-8"))
        if not label:
            continue
        jpg_file = txt_file.with_suffix(".jpg")
        if jpg_file.exists():
            pairs.append((jpg_file, label))
    return pairs


def _load_synthetic(
    synthetic_dir: pathlib.Path, gt_path: pathlib.Path
) -> list[tuple[pathlib.Path, str]]:
    if not synthetic_dir.exists() or not gt_path.exists():
        return []
    gt: dict[str, dict] = json.loads(gt_path.read_text(encoding="utf-8"))
    pairs: list[tuple[pathlib.Path, str]] = []
    for filename, meta in gt.items():
        img_path = synthetic_dir / filename
        if img_path.exists():
            label = _normalize(meta.get("plate_text", ""))
            if label:
                pairs.append((img_path, label))
    return pairs


def prepare(
    corrections_dir: pathlib.Path,
    out_dir: pathlib.Path,
    *,
    synthetic_dir: pathlib.Path | None = None,
    synthetic_gt: pathlib.Path | None = None,
    val_split: float = 0.20,
    seed: int = 42,
) -> None:
    pairs: list[tuple[pathlib.Path, str]] = []

    correction_pairs = _load_corrections(corrections_dir)
    print(f"Loaded {len(correction_pairs)} correction crops")
    pairs.extend(correction_pairs)

    if synthetic_dir and synthetic_gt:
        syn_pairs = _load_synthetic(synthetic_dir, synthetic_gt)
        print(f"Loaded {len(syn_pairs)} synthetic crops")
        pairs.extend(syn_pairs)

    if not pairs:
        raise SystemExit(
            "No training data found.\n"
            f"  Corrections dir: {corrections_dir} (need *.jpg + *.txt pairs)\n"
            "  Collect corrections first: make collect-corrections"
        )

    rng = random.Random(seed)
    rng.shuffle(pairs)

    split_idx = int(len(pairs) * (1 - val_split))
    train_pairs = pairs[:split_idx]
    val_pairs   = pairs[split_idx:]

    train_dir = out_dir / "train"
    val_dir   = out_dir / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    train_lines: list[str] = []
    val_lines:   list[str] = []

    for i, (src, label) in enumerate(train_pairs):
        dst = train_dir / f"{i:06d}{src.suffix}"
        shutil.copy2(src, dst)
        train_lines.append(f"train/{dst.name}\t{label}")

    for i, (src, label) in enumerate(val_pairs):
        dst = val_dir / f"{i:06d}{src.suffix}"
        shutil.copy2(src, dst)
        val_lines.append(f"val/{dst.name}\t{label}")

    (out_dir / "train_list.txt").write_text("\n".join(train_lines), encoding="utf-8")
    (out_dir / "val_list.txt").write_text("\n".join(val_lines), encoding="utf-8")

    print(f"\nDataset prepared:")
    print(f"  Train: {len(train_lines)} images → {out_dir / 'train_list.txt'}")
    print(f"  Val:   {len(val_lines)} images → {out_dir / 'val_list.txt'}")
    print(f"  Total: {len(pairs)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare PaddleOCR training dataset")
    parser.add_argument("--corrections",  default="ml/plate-ocr/corrections",            type=pathlib.Path)
    parser.add_argument("--synthetic",    default="ml/benchmarks/nepali_plates_test",    type=pathlib.Path)
    parser.add_argument("--synthetic-gt", default="ml/benchmarks/nepali_gt.json",        type=pathlib.Path)
    parser.add_argument("--out-dir",      default="ml/plate-ocr/data",                   type=pathlib.Path)
    parser.add_argument("--val-split",    default=0.20, type=float)
    parser.add_argument("--seed",         default=42,   type=int)
    args = parser.parse_args()

    prepare(
        args.corrections,
        args.out_dir,
        synthetic_dir=args.synthetic if args.synthetic.exists() else None,
        synthetic_gt=args.synthetic_gt if args.synthetic_gt.exists() else None,
        val_split=args.val_split,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
