#!/usr/bin/env python3
"""Verify the runtime is ready for the AI pipeline.

Checks, in order:
  1. GPU available via torch CUDA (warns, does not fail, if torch is absent —
     the API itself runs CPU-only; the GPU is needed for the worker).
  2. ffmpeg present on PATH.
  3. All three model weight directories exist and are non-empty.

Exit code 0 = all hard checks pass; non-zero = something is missing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
EXPECTED = ["f5_tts", "musetalk", "liveportrait"]


def check_gpu() -> bool:
    try:
        import torch
    except ImportError:
        print("⚠  torch not installed — skipping GPU check (needed for the worker).")
        return True  # not a hard failure for API-only environments
    if torch.cuda.is_available():
        print(f"✓ CUDA GPU: {torch.cuda.get_device_name(0)}")
        return True
    print("⚠  torch present but no CUDA GPU detected — generation will be very slow.")
    return True


def check_ffmpeg() -> bool:
    if shutil.which("ffmpeg") is None:
        print("✗ ffmpeg not found on PATH. Run ml_models/setup_ffmpeg.sh")
        return False
    line = subprocess.run(
        ["ffmpeg", "-version"], capture_output=True, text=True, check=False
    ).stdout.splitlines()[0]
    print(f"✓ {line}")
    return True


def check_weights() -> bool:
    ok = True
    for name in EXPECTED:
        path = WEIGHTS_DIR / name
        populated = path.is_dir() and any(p for p in path.iterdir() if p.name != ".gitkeep")
        if populated:
            print(f"✓ weights present: {name}")
        else:
            print(f"✗ weights missing/empty: {name} (run download_models.py)")
            ok = False
    return ok


def main() -> int:
    print("== Environment verification ==")
    results = {
        "gpu": check_gpu(),
        "ffmpeg": check_ffmpeg(),
        "weights": check_weights(),
    }
    hard_ok = results["ffmpeg"] and results["weights"]
    print("\nResult:", "READY ✓" if hard_ok else "NOT READY ✗")
    return 0 if hard_ok else 1


if __name__ == "__main__":
    sys.exit(main())
