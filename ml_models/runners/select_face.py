#!/usr/bin/env python3
"""Pick the sharpest frontal face from sampled frames, crop to 512x512 (runs in envLP).

insightface ships with LivePortrait's envLP. Writes face.png + thumb.png + the full
half-body frame (reference_halfbody.png, for EchoMimic v2) and prints a single JSON
object as the LAST stdout line (bbox, crop_size, quality_score, pose_samples) for the
backend to parse. On no face, the JSON is {"error": "NO_FACE_DETECTED"} (still exit 0
so the backend, not the shell, decides).

Usage:
  python select_face.py --frames FRAME_DIR --out-face face.png --out-thumb thumb.png \
    --out-halfbody reference_halfbody.png
"""
import argparse
import glob
import json
import os

import cv2
from insightface.app import FaceAnalysis


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--frames", required=True)
    p.add_argument("--out-face", required=True)
    p.add_argument("--out-thumb", required=True)
    p.add_argument("--out-halfbody", required=True)
    args = p.parse_args()

    app = FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0, det_size=(640, 640))

    best, best_score, pose_samples = None, -1.0, []
    for fp in sorted(glob.glob(os.path.join(args.frames, "*.jpg"))):
        img = cv2.imread(fp)
        if img is None:
            continue
        faces = app.get(img)
        if not faces:
            continue
        if len(faces) > 1:
            faces = [
                max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            ]
        f = faces[0]
        pose_samples.append([float(v) for v in f.pose])
        score = float(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        if score > best_score:
            best, best_score = (img, f), score

    if best is None:
        print(json.dumps({"error": "NO_FACE_DETECTED"}))
        return

    img, face = best
    x1, y1, x2, y2 = (int(v) for v in face.bbox)
    pad = int(0.35 * (y2 - y1))
    h, w = img.shape[:2]
    crop = img[max(0, y1 - pad) : min(h, y2 + pad), max(0, x1 - pad) : min(w, x2 + pad)]
    cv2.imwrite(args.out_face, cv2.resize(crop, (512, 512)))
    cv2.imwrite(args.out_thumb, cv2.resize(crop, (256, 256)))
    # Half-body reference = the full chosen frame (head+torso+arms), for EchoMimic v2.
    cv2.imwrite(args.out_halfbody, img)
    print(
        json.dumps(
            {
                "bbox": [x1, y1, x2, y2],
                "crop_size": [512, 512],
                "quality_score": min(best_score / 500.0, 1.0),
                "pose_samples": pose_samples,
            }
        )
    )


if __name__ == "__main__":
    main()
