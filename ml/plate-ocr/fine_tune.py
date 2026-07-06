"""
Fine-tune PaddleOCR on Nepali plate crops.

Wraps PaddlePaddle training so it can be driven from a single Makefile target.
Requires PaddleOCR and PaddlePaddle GPU (or CPU) installed in the environment.

Usage:
    # Embossed Latin plates
    uv run python ml/plate-ocr/fine_tune.py \
        --config ml/plate-ocr/configs/nepali_embossed.yml \
        --gpus   0

    # Devanagari plates
    uv run python ml/plate-ocr/fine_tune.py \
        --config ml/plate-ocr/configs/nepali_devanagari.yml \
        --gpus   0

    # CPU-only (slow, useful for smoke test)
    uv run python ml/plate-ocr/fine_tune.py \
        --config ml/plate-ocr/configs/nepali_embossed.yml \
        --cpu

Prerequisites:
    1. Dataset prepared: make train-nepali-ocr calls prepare_dataset.py first
    2. Base weights downloaded:
         mkdir -p ml/plate-ocr/pretrain/
         wget -q https://paddleocr.bj.bcebos.com/PP-OCRv4/english/en_PP-OCRv4_rec_train.tar
         tar xf en_PP-OCRv4_rec_train.tar -C ml/plate-ocr/pretrain/

Output:
    ml/plate-ocr/models/<config-stem>/best_accuracy   — best checkpoint
    ml/plate-ocr/models/<config-stem>/latest           — last checkpoint
"""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import textwrap


PRETRAIN_DIR = pathlib.Path("ml/plate-ocr/pretrain")
MODEL_DIR    = pathlib.Path("ml/plate-ocr/models")

PRETRAIN_URL = (
    "https://paddleocr.bj.bcebos.com/PP-OCRv4/english/en_PP-OCRv4_rec_train.tar"
)


def _ensure_pretrain() -> pathlib.Path:
    weights = PRETRAIN_DIR / "en_PP-OCRv4_rec_train" / "best_accuracy.pdparams"
    if weights.exists():
        return weights.parent

    PRETRAIN_DIR.mkdir(parents=True, exist_ok=True)
    tarball = PRETRAIN_DIR / "en_PP-OCRv4_rec_train.tar"
    if not tarball.exists():
        print(f"Downloading base weights from {PRETRAIN_URL} …")
        subprocess.run(
            ["wget", "-q", "-O", str(tarball), PRETRAIN_URL],
            check=True,
        )
    print("Extracting pretrained weights …")
    subprocess.run(
        ["tar", "xf", str(tarball), "-C", str(PRETRAIN_DIR)],
        check=True,
    )
    if not weights.exists():
        raise FileNotFoundError(
            f"Could not find pretrained weights at {weights} after extraction. "
            "Check that the tarball structure matches 'en_PP-OCRv4_rec_train/best_accuracy.pdparams'."
        )
    return weights.parent


def _check_dataset(config_path: pathlib.Path) -> None:
    """Warn loudly if training data is missing before starting a long job."""
    data_dir = pathlib.Path("ml/plate-ocr/data")
    train_list = data_dir / "train_list.txt"
    val_list   = data_dir / "val_list.txt"

    if not train_list.exists() or not val_list.exists():
        raise SystemExit(
            textwrap.dedent("""\
            Training data not found. Run first:
                make collect-corrections      # download guard corrections
                uv run python ml/plate-ocr/prepare_dataset.py   # build train/val split
            Or with synthetic data only:
                make generate-plate-crops
                uv run python ml/plate-ocr/prepare_dataset.py --no-corrections
            """)
        )

    n_train = sum(1 for _ in train_list.open(encoding="utf-8"))
    n_val   = sum(1 for _ in val_list.open(encoding="utf-8"))
    print(f"Dataset: {n_train} train, {n_val} val")
    if n_train < 100:
        print(
            f"WARNING: only {n_train} training samples — accuracy will be low. "
            "Collect more corrections before relying on this model in production.",
            file=sys.stderr,
        )


def run_training(config: pathlib.Path, *, use_gpu: bool, gpu_ids: str) -> None:
    _check_dataset(config)
    pretrain_dir = _ensure_pretrain()

    model_name = config.stem
    save_dir   = MODEL_DIR / model_name
    save_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    if use_gpu:
        env["CUDA_VISIBLE_DEVICES"] = gpu_ids

    cmd = [
        sys.executable, "-m", "paddle.distributed.launch",
        "--gpus", gpu_ids if use_gpu else "",
        "tools/train.py",
        "-c", str(config),
        "-o",
        f"Global.pretrained_model={pretrain_dir / 'best_accuracy'}",
        f"Global.save_model_dir={save_dir}",
        f"Global.use_gpu={'true' if use_gpu else 'false'}",
    ]
    # Filter empty args from --gpus ""
    cmd = [c for c in cmd if c]

    print(f"Starting PaddleOCR training: {config.name}")
    print(f"  Save dir: {save_dir}")
    print(f"  GPU: {'yes (' + gpu_ids + ')' if use_gpu else 'no (CPU)'}")
    print()

    # PaddleOCR training must run from the PaddleOCR root, which may be in
    # the site-packages or a local clone. Try to locate it.
    try:
        import paddleocr  # type: ignore[import]
        paddle_root = pathlib.Path(paddleocr.__file__).parent.parent
    except ImportError:
        raise SystemExit(
            "paddleocr not installed. Install with:\n"
            "  pip install paddleocr paddlepaddle-gpu  # GPU\n"
            "  pip install paddleocr paddlepaddle       # CPU"
        )

    # Override tools path if PaddleOCR is installed as a package (no tools/ dir)
    tools_train = paddle_root / "tools" / "train.py"
    if not tools_train.exists():
        # Use the module entrypoint instead
        cmd = [
            sys.executable, "-m", "paddle.distributed.launch",
            "--log_dir", str(save_dir / "dist_log"),
            *(["--gpus", gpu_ids] if use_gpu else []),
            "-m", "paddleocr.tools.train",
            "-c", str(config),
            "-o",
            f"Global.pretrained_model={pretrain_dir / 'best_accuracy'}",
            f"Global.save_model_dir={save_dir}",
            f"Global.use_gpu={'true' if use_gpu else 'false'}",
        ]
    else:
        cmd[cmd.index("tools/train.py")] = str(tools_train)

    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise SystemExit(f"Training failed with exit code {result.returncode}")

    print(f"\nTraining complete. Checkpoint: {save_dir / 'best_accuracy'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune PaddleOCR for Nepali plates")
    parser.add_argument("--config", required=True, type=pathlib.Path)
    parser.add_argument("--gpus",   default="0",   help="Comma-separated GPU IDs")
    parser.add_argument("--cpu",    action="store_true", help="Force CPU training")
    args = parser.parse_args()

    if not args.config.exists():
        raise SystemExit(f"Config not found: {args.config}")

    run_training(args.config, use_gpu=not args.cpu, gpu_ids=args.gpus)


if __name__ == "__main__":
    main()
