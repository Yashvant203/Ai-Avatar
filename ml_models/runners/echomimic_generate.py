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

# Reference framing: EchoMimic squashes the reference to W×H and warps it toward a
# fixed half-body pose skeleton. We frame the avatar head→waist and pad to square
# so the face fills the canvas (identity) and lines up with the pose (no neck seam).
_REF_SCALE = 5.0  # square side as a multiple of detected face height (head→waist)
_REF_HEADROOM = 0.6  # space above the head, as a fraction of face height


def _halfbody_crop_box(img_w, img_h, face_box, *, headroom_frac=_REF_HEADROOM, scale=_REF_SCALE):
    """Square crop framing a person head-to-waist from a detected face box.

    Returns (left, top, right, bottom); coords may fall outside [0, img] so the
    caller pads (EchoMimic's pose template sits on a neutral canvas, so black
    padding is fine). The box is always exactly square so the size resize keeps
    facial proportions — squashing a non-square frame is what warped the jawline.
    """
    fx1, fy1, fx2, fy2 = face_box
    fh = fy2 - fy1
    cx = (fx1 + fx2) / 2.0
    side = int(scale * fh)
    top = int(fy1 - headroom_frac * fh)
    left = int(cx - side / 2.0)
    return (left, top, left + side, top + side)


def _pad_square_box(img_w, img_h):
    """Centered square covering the whole frame (fallback when no face is found).

    Side = max dimension, so nothing is cropped out — the short axis is padded.
    Preserves proportions without guessing where the person is.
    """
    side = max(img_w, img_h)
    left = (img_w - side) // 2
    top = (img_h - side) // 2
    return (left, top, left + side, top + side)


def _prepare_reference(ref_path, out_path, size):  # pragma: no cover - needs torch/PIL
    """Crop the avatar reference to a person-centered, proportion-preserving square.

    Handing EchoMimic a raw full-frame photo distorts the face (non-square squash)
    and misaligns head/torso against the pose skeleton (the neck/collar seam).
    Detect the face (MTCNN, already in envEM via facenet_pytorch), frame head→waist,
    pad to square, then resize — so the face fills more of the 768 canvas and sits
    where the pose template expects it.
    """
    from PIL import Image

    img = Image.open(ref_path).convert("RGB")
    W, H = img.size
    box = None
    try:
        import torch
        from facenet_pytorch import MTCNN

        device = "cuda" if torch.cuda.is_available() else "cpu"
        boxes, _ = MTCNN(keep_all=True, device=device).detect(img)
        if boxes is not None and len(boxes):
            biggest = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
            box = _halfbody_crop_box(W, H, tuple(float(v) for v in biggest))
            print(f"[echomimic] face-framed reference crop {box} from {W}x{H}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[echomimic] face detect failed ({exc}); padding full frame", flush=True)
    if box is None:
        box = _pad_square_box(W, H)
        print(f"[echomimic] no face detected; padded square {box} from {W}x{H}", flush=True)

    left, top, right, bottom = box
    side = right - left
    canvas = Image.new("RGB", (side, side), (0, 0, 0))
    sx1, sy1 = max(0, left), max(0, top)
    sx2, sy2 = min(W, right), min(H, bottom)
    canvas.paste(img.crop((sx1, sy1, sx2, sy2)), (sx1 - left, sy1 - top))
    canvas.resize((size, size), Image.LANCZOS).save(out_path)


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
    # Match the AUDIO length: if the template is longer, take only the first n_frames
    # (don't render extra silent seconds); if shorter, the palindrome cycle loops it.
    count = n_frames
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

    # The bundled EchoMimic pose templates are rendered on a fixed 768x768 canvas;
    # infer.py builds the frame buffer at W×H and assigns the 768 pose mask into it,
    # so any W/H != 768 raises a broadcast error. Force 768 (tune speed via --steps).
    if args.width != 768 or args.height != 768:
        print(f"[echomimic] forcing {args.width}x{args.height} -> 768x768 "
              "(bundled pose template canvas); use --steps to trade speed/quality.")
        args.width = 768
        args.height = 768

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
    # Frame the reference head→waist, square, before infer.py squashes it to W×H
    # (raw full-frame photos cause identity drift + the neck/collar seam).
    _prepare_reference(args.reference, os.path.join(ref_dir, "clip", "ref.png"), args.width)
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
    # Stream infer.py's output to a tailable log beside the output video so progress
    # (tqdm step bars) is visible live — the calling backend captures THIS script's
    # stdout, so without a side log the diffusion looks frozen until it finishes.
    log_path = os.path.join(os.path.dirname(os.path.abspath(args.out)), "echomimic_infer.log")
    print(f"[echomimic] running (live log: {log_path}):", " ".join(cmd), flush=True)
    with open(log_path, "w") as lf:
        proc = subprocess.run(cmd, cwd=args.repo, stdout=lf, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        try:
            tail = open(log_path).read()[-3000:]
        except OSError:
            tail = ""
        if "out of memory" in tail.lower():
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
