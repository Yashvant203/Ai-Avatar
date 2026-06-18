#!/usr/bin/env python3
"""Generate a half-body talking video with EchoMimic v2 (runs in envEM).

Wraps the project's infer.py: stages our reference image + 16 kHz wav into the
dir/name layout infer.py expects, palindrome-loops the bundled pose .npy sequence
to cover the audio length, runs inference, and copies the output MP4 to --out.

Prints a single JSON object as the LAST stdout line: {"path": "...", "frames": N}.
On CUDA OOM (or any infer.py failure) it exits non-zero with a clear message so
the backend surfaces a PipelineError.

Usage (driven by RealBackend.generate_video):
  python echomimic_generate.py --reference ref.png --audio speech_16k.wav \
    --repo /tmp/aiavatar/EchoMimicV2 --pose-name 01 --out out.mp4 \
    --width 768 --height 768 --steps 20 --cfg 2.5 --fps 24 --seconds 6.0
"""
import argparse
import glob
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import wave


def _audio_seconds(path: str, fallback: float) -> float:
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:  # noqa: BLE001
        return fallback


def _build_looped_pose(src_pose_dir: str, dst_pose_dir: str, n_frames: int) -> int:
    """Palindrome-loop the source .npy pose files to >= n_frames; renumber 0..M-1."""
    import numpy as np

    srcs = sorted(
        glob.glob(os.path.join(src_pose_dir, "*.npy")),
        key=lambda p: int(os.path.splitext(os.path.basename(p))[0]),
    )
    if not srcs:
        raise SystemExit(f"[echomimic] no pose .npy files in {src_pose_dir}")
    # forward + reverse(without endpoints) = seamless palindrome cycle
    cycle = srcs + srcs[-2:0:-1] if len(srcs) > 2 else srcs
    os.makedirs(dst_pose_dir, exist_ok=True)
    count = max(n_frames, len(srcs))
    for i in range(count):
        data = np.load(cycle[i % len(cycle)], allow_pickle=True)
        np.save(os.path.join(dst_pose_dir, f"{i}.npy"), data)
    return count


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reference", required=True)
    p.add_argument("--audio", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--pose-name", default="01")
    p.add_argument("--out", required=True)
    p.add_argument("--width", type=int, default=768)
    p.add_argument("--height", type=int, default=768)
    p.add_argument("--steps", type=int, default=20)
    p.add_argument("--cfg", type=float, default=2.5)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--seconds", type=float, default=0.0)
    args = p.parse_args()

    # EchoMimic shells out to ffmpeg via FFMPEG_PATH (dir containing the binary).
    if "FFMPEG_PATH" not in os.environ:
        ff = shutil.which("ffmpeg")
        if ff:
            os.environ["FFMPEG_PATH"] = os.path.dirname(ff)

    seconds = args.seconds or _audio_seconds(args.audio, 6.0)
    n_frames = max(1, math.ceil(seconds * args.fps))

    src_pose_dir = os.path.join(args.repo, "assets", "halfbody_demo", "pose", args.pose_name)
    work = tempfile.mkdtemp(prefix="echomimic_")
    ref_dir = os.path.join(work, "ref")
    aud_dir = os.path.join(work, "aud")
    pose_root = os.path.join(work, "pose")
    # infer.py derives a flag via refimg_name.split('/')[-2], so the name MUST contain
    # a subdirectory (its demo default is "natural_bk_openhand/0035.png"). Stage our
    # inputs one level deep under a "clip/" subdir to satisfy that.
    os.makedirs(os.path.join(ref_dir, "clip"), exist_ok=True)
    os.makedirs(os.path.join(aud_dir, "clip"), exist_ok=True)
    shutil.copyfile(args.reference, os.path.join(ref_dir, "clip", "ref.png"))
    shutil.copyfile(args.audio, os.path.join(aud_dir, "clip", "aud.wav"))
    frames = _build_looped_pose(src_pose_dir, os.path.join(pose_root, "loop"), n_frames)

    out_root = os.path.join(args.repo, "outputs")
    before = set(glob.glob(os.path.join(out_root, "**", "*.mp4"), recursive=True))

    cmd = [
        sys.executable, "infer.py",
        "--config", "./configs/prompts/infer.yaml",
        "-W", str(args.width), "-H", str(args.height), "-L", str(frames),
        "--steps", str(args.steps), "--cfg", str(args.cfg), "--fps", str(args.fps),
        "--ref_images_dir", ref_dir, "--refimg_name", "clip/ref.png",
        "--audio_dir", aud_dir, "--audio_name", "clip/aud.wav",
        "--pose_dir", pose_root, "--pose_name", "loop",
    ]
    print("[echomimic] running:", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=args.repo, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-3000:]
        if "out of memory" in tail.lower() or "CUDA out of memory" in tail:
            print("[echomimic] CUDA OUT OF MEMORY — lower ECHOMIMIC_WIDTH/HEIGHT/STEPS "
                  "or use a larger GPU.", file=sys.stderr)
        print(tail, file=sys.stderr)
        raise SystemExit(f"infer.py failed (rc={proc.returncode})")

    after = set(glob.glob(os.path.join(out_root, "**", "*.mp4"), recursive=True))
    new = sorted(after - before, key=os.path.getmtime)
    produced = new[-1] if new else (sorted(after, key=os.path.getmtime)[-1] if after else None)
    if not produced:
        raise SystemExit(f"[echomimic] no output MP4 found under {out_root}")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    shutil.copyfile(produced, args.out)
    print(json.dumps({"path": args.out, "frames": frames, "seconds": round(seconds, 2)}))


if __name__ == "__main__":
    main()
