#!/usr/bin/env python3
"""Download open-source model weights into ml_models/weights/.

Idempotent and resumable: huggingface_hub.snapshot_download skips files already
present and resumes partial downloads. Set HF_TOKEN in the environment for gated
repos.

Usage:
    python ml_models/download_models.py
    python ml_models/download_models.py --only f5_tts liveportrait
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"

# key -> (env override var, default HF repo id, subdir)
MODELS: dict[str, tuple[str, str, str]] = {
    "f5_tts": ("F5_TTS_REPO", "SWivid/F5-TTS", "f5_tts"),
    "musetalk": ("MUSETALK_REPO", "TMElyralab/MuseTalk", "musetalk"),
    "liveportrait": ("LIVEPORTRAIT_REPO", "KwaiVGI/LivePortrait", "liveportrait"),
}


def _download_one(key: str) -> Path:
    from huggingface_hub import snapshot_download  # imported lazily

    env_var, default_repo, subdir = MODELS[key]
    repo_id = os.environ.get(env_var, default_repo)
    target = WEIGHTS_DIR / subdir
    target.mkdir(parents=True, exist_ok=True)

    print(f"[{key}] downloading {repo_id} -> {target}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target),
        local_dir_use_symlinks=False,
        resume_download=True,
        token=os.environ.get("HF_TOKEN"),
    )
    print(f"[{key}] done.")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download model weights.")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=sorted(MODELS),
        help="Download only the named models (default: all).",
    )
    args = parser.parse_args(argv)

    try:
        import huggingface_hub  # noqa: F401
    except ImportError:
        print(
            "ERROR: huggingface_hub is not installed.\n"
            "       Install it in your GPU/runtime env:  pip install huggingface_hub",
            file=sys.stderr,
        )
        return 2

    selected = args.only or list(MODELS)
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for key in selected:
        try:
            _download_one(key)
        except Exception as exc:  # noqa: BLE001
            print(f"[{key}] FAILED: {exc}", file=sys.stderr)
            failures.append(key)

    if failures:
        print(f"\nCompleted with failures: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nAll requested models downloaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
