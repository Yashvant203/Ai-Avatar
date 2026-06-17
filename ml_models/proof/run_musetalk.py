#!/usr/bin/env python3
"""MuseTalk v1.5 lip-sync (runs in env-B, invoked via conda run).

Writes a one-task inference YAML, calls `scripts.inference`, and prints the result
mp4 path. Must be invoked with CWD at the MuseTalk repo root (its imports are
repo-relative).

Usage (from MuseTalk repo root):
  python run_musetalk.py --video animated_25.mp4 --audio speech_16k.wav --result-dir results/job
"""
import argparse
import os
import subprocess
import sys


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True, help="animated head mp4 (25 fps)")
    p.add_argument("--audio", required=True, help="speech wav (16 kHz mono)")
    p.add_argument("--result-dir", default="results/job")
    p.add_argument("--bbox-shift", type=int, default=0)
    args = p.parse_args()

    os.makedirs("configs/inference", exist_ok=True)
    cfg_path = "configs/inference/proof_job.yaml"
    with open(cfg_path, "w") as fh:
        fh.write(
            "task_0:\n"
            f'  video_path: "{os.path.abspath(args.video)}"\n'
            f'  audio_path: "{os.path.abspath(args.audio)}"\n'
            f"  bbox_shift: {args.bbox_shift}\n"
        )
    print(f"wrote config {cfg_path}")

    cmd = [
        sys.executable, "-m", "scripts.inference",
        "--inference_config", cfg_path,
        "--result_dir", args.result_dir,
        "--unet_model_path", "models/musetalkV15/unet.pth",
        "--unet_config", "models/musetalkV15/musetalk.json",
        "--version", "v15",
        "--fps", "25",
        "--ffmpeg_path", "/usr/bin",
        "--use_float16",
    ]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"done — look for the output mp4 under {args.result_dir}/")


if __name__ == "__main__":
    main()
