#!/usr/bin/env python3
"""Find the most frontal, stable window in a source video (runs in envLP).

Scans the uploaded video with insightface and scores each candidate window by
frontality (small |yaw|+|pitch|+|roll|) minus a variance penalty (avoid wild
swings), then prints the best [start, end] in seconds as JSON for the backend to
cut into the avatar's driving clip. On no face: {"error": "NO_FACE_DETECTED"}.

Usage:
  python extract_driving.py --video in.mp4 --window-seconds 6.0
"""
import argparse
import json

import cv2
import numpy as np
from insightface.app import FaceAnalysis


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--window-seconds", type=float, default=6.0)
    p.add_argument("--sample-fps", type=float, default=5.0)
    args = p.parse_args()

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total / fps if total else 0.0

    app = FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0, det_size=(640, 640))

    step = max(1, int(round(fps / args.sample_fps)))
    samples = []  # (t, frontality | None)
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            t = idx / fps
            faces = app.get(frame)
            if faces:
                f = max(faces, key=lambda g: (g.bbox[2] - g.bbox[0]) * (g.bbox[3] - g.bbox[1]))
                yaw, pitch, roll = (float(v) for v in f.pose)
                samples.append((t, -(abs(yaw) + abs(pitch) + abs(roll))))
            else:
                samples.append((t, None))
        idx += 1
    cap.release()

    if not any(s[1] is not None for s in samples):
        print(json.dumps({"error": "NO_FACE_DETECTED"}))
        return

    win = args.window_seconds
    if duration <= win:
        print(json.dumps({"start": 0.0, "end": round(duration or win, 2)}))
        return

    best_start, best_score = 0.0, -1e18
    for t0, _ in samples:
        if t0 + win > duration:
            break
        window = [fr for (t, fr) in samples if t0 <= t <= t0 + win]
        vals = [fr for fr in window if fr is not None]
        if len(vals) < max(2, int(0.6 * len(window))):  # face must be present in most of window
            continue
        score = float(np.mean(vals)) - 0.5 * float(np.var(vals))
        if score > best_score:
            best_score, best_start = score, t0

    print(json.dumps({"start": round(best_start, 2), "end": round(best_start + win, 2)}))


if __name__ == "__main__":
    main()
