# EchoMimic v2 Generation Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second, flag-selectable video-generation engine based on EchoMimic v2 that produces a half-body talking avatar with visible hand gestures, so it can be compared against the existing LivePortrait+MuseTalk head-only output.

**Architecture:** Same isolated-env + subprocess pattern as Phase 1. A new micromamba env `envEM` runs EchoMimic v2 via a thin runner that wraps the project's `infer.py`. F5-TTS voice clone is unchanged; a config flag `GENERATION_ENGINE` routes the generation orchestrator to either the existing animate→lipsync path (`liveportrait`) or a single `generate_video()` call (`echomimic`). Avatar creation gains a half-body reference still alongside the existing face crop.

**Tech Stack:** Python 3.10 / FastAPI backend (Kaggle base env), micromamba `envEM` (torch 2.5.1/cu121 + xformers + diffusers), EchoMimic v2 (`antgroup/echomimic_v2`), ffmpeg, pytest.

**Branch:** `echomimic-v2-backend` (already created; spec at `docs/superpowers/specs/2026-06-18-echomimic-v2-backend-design.md`).

---

## File Structure

**Create:**
- `ml_models/runners/setup_env_em.sh` — builds `envEM` + EchoMimic v2 repo + weights.
- `ml_models/runners/echomimic_generate.py` — runner wrapping `infer.py` (runs in `envEM`).
- `backend/app/tests/test_generation_echomimic.py` — stub-backend test for the echomimic engine.

**Modify:**
- `backend/app/core/config.py` — add `ENV_EM`, `GENERATION_ENGINE`, `ECHOMIMIC_*` settings.
- `backend/app/core/paths.py` — add `avatar_halfbody_path()`.
- `ml_models/runners/select_face.py` — also emit the full half-body frame.
- `backend/app/pipelines/avatar_creation/ml/backends.py` — `select_best_face()` gains `out_halfbody`.
- `backend/app/pipelines/avatar_creation/runner.py` — store `reference_halfbody.png`, add to profile.
- `backend/app/pipelines/generation/ml/backends.py` — add `generate_video()` to Protocol + both backends.
- `backend/app/pipelines/generation/orchestrator.py` — branch on `GENERATION_ENGINE`.
- `backend/app/tests/test_pipeline.py` — assert `reference_halfbody.png` exists.
- `ml_models/build_backend_notebook.py` — add the `envEM` build cell + set `GENERATION_ENGINE`.

**Environment for all backend tests:** run from `backend/` with the project venv:
`PIPELINE_BACKEND=stub .venv/bin/python -m pytest`

---

## Task 1: Config settings for EchoMimic

**Files:**
- Modify: `backend/app/core/config.py:66-68` (after the `ENV_MT` line)
- Test: `backend/app/tests/test_config_echomimic.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_config_echomimic.py`:

```python
"""EchoMimic v2 config defaults."""

from __future__ import annotations

from app.core.config import Settings


def test_echomimic_defaults() -> None:
    s = Settings()
    assert s.GENERATION_ENGINE == "liveportrait"  # default stays the existing path
    assert s.ENV_EM == "envEM"
    assert s.ECHOMIMIC_POSE_NAME == "01"
    assert s.ECHOMIMIC_WIDTH == 768
    assert s.ECHOMIMIC_HEIGHT == 768
    assert s.ECHOMIMIC_STEPS == 20
    assert s.ECHOMIMIC_CFG == 2.5


def test_generation_engine_overridable(monkeypatch) -> None:
    monkeypatch.setenv("GENERATION_ENGINE", "echomimic")
    s = Settings()
    assert s.GENERATION_ENGINE == "echomimic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest app/tests/test_config_echomimic.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'GENERATION_ENGINE'`

- [ ] **Step 3: Add the settings**

In `backend/app/core/config.py`, immediately after the line `ENV_MT: str = "envMT"`, add:

```python
    ENV_EM: str = "envEM"

    # --- EchoMimic v2 (alternative generation engine, half-body + hand gestures) ---
    # Which visual engine the generation orchestrator uses:
    #   "liveportrait" → LivePortrait head motion + MuseTalk lip-sync (default)
    #   "echomimic"    → EchoMimic v2 single diffusion pass (gestures + lip-sync)
    GENERATION_ENGINE: str = "liveportrait"  # liveportrait | echomimic
    # EchoMimic v2 ships bundled pose templates under its repo's
    # assets/halfbody_demo/pose/<NAME>; "01" is the default demo gesture sequence.
    ECHOMIMIC_POSE_NAME: str = "01"
    # Conservative T4 defaults: EchoMimic v2 is a heavy diffusion model. Smaller
    # frame size + fewer steps reduce VRAM/time; raise on bigger GPUs.
    ECHOMIMIC_WIDTH: int = 768
    ECHOMIMIC_HEIGHT: int = 768
    ECHOMIMIC_STEPS: int = 20
    ECHOMIMIC_CFG: float = 2.5
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest app/tests/test_config_echomimic.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/app/tests/test_config_echomimic.py
git commit -m "feat(echomimic): config settings + GENERATION_ENGINE flag"
```

---

## Task 2: `avatar_halfbody_path` storage helper

**Files:**
- Modify: `backend/app/core/paths.py:67` (after `avatar_driving_path`)
- Test: `backend/app/tests/test_paths_halfbody.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_paths_halfbody.py`:

```python
"""Half-body reference path helper stays inside the storage root."""

from __future__ import annotations

import app.core.paths as paths


def test_avatar_halfbody_path_under_storage() -> None:
    p = paths.avatar_halfbody_path(42)
    assert p.name == "reference_halfbody.png"
    assert p.parent.name == "42"
    assert paths.is_within_storage(p)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest app/tests/test_paths_halfbody.py -v`
Expected: FAIL with `AttributeError: module 'app.core.paths' has no attribute 'avatar_halfbody_path'`

- [ ] **Step 3: Add the helper**

In `backend/app/core/paths.py`, directly after the `avatar_driving_path` function (line 67), add:

```python
def avatar_halfbody_path(avatar_id: int) -> Path:
    """Half-body still (head+torso+arms) selected from the upload; feeds EchoMimic v2."""
    return _safe_join("avatars", avatar_id, "reference_halfbody.png")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest app/tests/test_paths_halfbody.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/paths.py backend/app/tests/test_paths_halfbody.py
git commit -m "feat(echomimic): avatar_halfbody_path storage helper"
```

---

## Task 3: Capture a half-body reference at avatar creation

The avatar-creation backend's `select_best_face` finds the best frame and crops a 512×512 face. We extend it to also emit the **full** chosen frame as `reference_halfbody.png` (the upload is half-body framed, so the full frame contains head+torso+arms).

**Files:**
- Modify: `ml_models/runners/select_face.py` (add `--out-halfbody`)
- Modify: `backend/app/pipelines/avatar_creation/ml/backends.py` (Protocol + both backends)
- Modify: `backend/app/pipelines/avatar_creation/runner.py` (pass halfbody path, add to profile)
- Modify: `backend/app/tests/test_pipeline.py` (assert the new artifact)

- [ ] **Step 1: Update the stub-path test to require the new artifact**

In `backend/app/tests/test_pipeline.py`, change the artifact loop (line 133) from:

```python
    for f in ("profile.json", "face.png", "thumbnail.png", "driving.mp4"):
```

to:

```python
    for f in ("profile.json", "face.png", "thumbnail.png", "driving.mp4", "reference_halfbody.png"):
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest app/tests/test_pipeline.py::test_pipeline_reaches_ready -v`
Expected: FAIL with `AssertionError: missing reference_halfbody.png`

- [ ] **Step 3: Extend the Protocol signature**

In `backend/app/pipelines/avatar_creation/ml/backends.py`, change the `AvatarBackend` Protocol method (line 45):

```python
    def select_best_face(
        self, frame_dir: Path, out_face: Path, out_thumb: Path, out_halfbody: Path
    ) -> dict: ...
```

- [ ] **Step 4: Update `StubBackend.select_best_face`**

In the same file, replace the `StubBackend.select_best_face` method (lines 100-113) with:

```python
    def select_best_face(
        self, frame_dir: Path, out_face: Path, out_thumb: Path, out_halfbody: Path
    ) -> dict:
        frames = sorted(frame_dir.glob("*.jpg"))
        if not frames:
            raise PipelineError("NO_FACE_DETECTED", "no frames sampled from video")
        # Use the middle frame; scale to the documented sizes via ffmpeg.
        chosen = frames[len(frames) // 2]
        run_ffmpeg(["-y", "-i", str(chosen), "-vf", "scale=512:512", str(out_face)])
        run_ffmpeg(["-y", "-i", str(chosen), "-vf", "scale=256:256", str(out_thumb)])
        # Half-body reference: the full chosen frame scaled to EchoMimic's frame size.
        run_ffmpeg(["-y", "-i", str(chosen), "-vf", "scale=768:768", str(out_halfbody)])
        return {
            "bbox": [0, 0, 512, 512],
            "crop_size": [512, 512],
            "quality_score": 0.5,
            "pose_samples": [],
        }
```

- [ ] **Step 5: Update `RealBackend.select_best_face`**

In the same file, replace the `RealBackend.select_best_face` method (lines 219-244) with:

```python
    def select_best_face(
        self, frame_dir: Path, out_face: Path, out_thumb: Path, out_halfbody: Path
    ) -> dict:  # pragma: no cover - requires ML stack
        from app.core.config import settings
        from app.pipelines._subproc import run_in_env

        out_face.parent.mkdir(parents=True, exist_ok=True)
        stdout = run_in_env(
            settings.ENV_LP,
            [
                "python",
                f"{Path(settings.RUNNERS_DIR).resolve()}/select_face.py",
                "--frames",
                str(frame_dir),
                "--out-face",
                str(out_face),
                "--out-thumb",
                str(out_thumb),
                "--out-halfbody",
                str(out_halfbody),
            ],
        )
        result = _parse_last_json(stdout)
        if result is None:
            raise PipelineError("NO_FACE_DETECTED", "select_face.py produced no JSON result")
        if result.get("error"):
            raise PipelineError("NO_FACE_DETECTED", "no face found in sampled frames")
        return result
```

- [ ] **Step 6: Update the `select_face.py` runner to emit the half-body frame**

In `ml_models/runners/select_face.py`, add the argument (after line 26, the `--out-thumb` arg):

```python
    p.add_argument("--out-halfbody", required=True)
```

Then, in the same file, replace the two `cv2.imwrite` lines for face/thumb (lines 58-59) with:

```python
    cv2.imwrite(args.out_face, cv2.resize(crop, (512, 512)))
    cv2.imwrite(args.out_thumb, cv2.resize(crop, (256, 256)))
    # Half-body reference = the full chosen frame (head+torso+arms), for EchoMimic v2.
    cv2.imwrite(args.out_halfbody, img)
```

- [ ] **Step 7: Update the avatar-creation runner**

In `backend/app/pipelines/avatar_creation/runner.py`, add the import (in the `app.core.paths` import block, after `avatar_face_path` on line 21):

```python
    avatar_halfbody_path,
```

Replace the Stage 5 block (lines 127-131) with:

```python
            # Stage 5 — frames + best face + half-body reference
            extract_face.sample_frames(video.file_path, frame_dir)
            face_png = avatar_face_path(avatar_id)
            thumb_png = avatar_thumbnail_path(avatar_id)
            halfbody_png = avatar_halfbody_path(avatar_id)
            face_meta = backend.select_best_face(frame_dir, face_png, thumb_png, halfbody_png)
```

Then add the half-body entries to `artifact_paths` (inside the dict at lines 143-154), after the `"thumbnail"` line:

```python
                "reference_halfbody": relpath(halfbody_png),
                "_halfbody_abs": str(halfbody_png),
```

- [ ] **Step 8: Run the pipeline test to verify it passes**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest app/tests/test_pipeline.py -v`
Expected: PASS (both tests). The half-body artifact now exists.

- [ ] **Step 9: Commit**

```bash
git add ml_models/runners/select_face.py backend/app/pipelines/avatar_creation/ml/backends.py backend/app/pipelines/avatar_creation/runner.py backend/app/tests/test_pipeline.py
git commit -m "feat(echomimic): capture half-body reference at avatar creation"
```

---

## Task 4: `generate_video` stub backend + orchestrator routing

Add `generate_video()` to the generation Protocol and `StubBackend`, then route the orchestrator on `GENERATION_ENGINE`. The echomimic path replaces stages 2+3 (animate+lipsync) with one call that writes to the existing `lipsync` path; the shared stage-4 mux/thumbnail/finalize is unchanged.

**Files:**
- Modify: `backend/app/pipelines/generation/ml/backends.py` (Protocol + StubBackend)
- Modify: `backend/app/pipelines/generation/orchestrator.py` (branch)
- Test: `backend/app/tests/test_generation_echomimic.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/app/tests/test_generation_echomimic.py`:

```python
"""StubBackend.generate_video produces a real, playable MP4 (echomimic engine path)."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from app.pipelines.avatar_creation.ml.ffmpeg import ffprobe_metadata
from app.pipelines.generation.ml.backends import StubBackend

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe required",
)


def _make_audio(path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=220:duration=2:sample_rate=24000", "-ac", "1", str(path)],
        check=True,
    )


def _make_image(path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "color=c=blue:s=320x320:d=1", "-frames:v", "1", str(path)],
        check=True,
    )


def test_stub_generate_video_makes_playable_mp4(tmp_path) -> None:
    audio = tmp_path / "speech.wav"
    ref = tmp_path / "ref.png"
    out = tmp_path / "out.mp4"
    _make_audio(audio)
    _make_image(ref)

    StubBackend().generate_video(
        reference_image=ref, audio=audio, out_video=out, duration_s=2.0, fps=25
    )

    assert out.exists() and out.stat().st_size > 0
    meta = ffprobe_metadata(out)
    assert meta.get("duration_seconds") and meta["duration_seconds"] > 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest app/tests/test_generation_echomimic.py -v`
Expected: FAIL with `AttributeError: 'StubBackend' object has no attribute 'generate_video'`

- [ ] **Step 3: Add `generate_video` to the Protocol**

In `backend/app/pipelines/generation/ml/backends.py`, add to the `GenerationBackend` Protocol after the `lipsync` method (line 45):

```python
    def generate_video(
        self,
        out_video: Path,
        *,
        reference_image: Path | None,
        audio: Path,
        duration_s: float,
        fps: int,
    ) -> None: ...
```

- [ ] **Step 4: Implement `StubBackend.generate_video`**

In the same file, add this method to `StubBackend` after `lipsync` (after line 121):

```python
    def generate_video(
        self,
        out_video: Path,
        *,
        reference_image: Path | None,
        audio: Path,
        duration_s: float,
        fps: int,
    ) -> None:
        # No diffusion model in the stub: loop the still half-body image and mux
        # the synthesized audio, producing a real, playable MP4.
        out_video.parent.mkdir(parents=True, exist_ok=True)
        if reference_image is not None and Path(reference_image).exists():
            run_ffmpeg(
                [
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(reference_image),
                    "-i",
                    str(audio),
                    "-t",
                    f"{duration_s:.3f}",
                    "-r",
                    str(fps),
                    "-vf",
                    "scale=512:512",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-shortest",
                    str(out_video),
                ]
            )
        else:
            run_ffmpeg(
                [
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc=duration={duration_s:.3f}:size=512x512:rate={fps}",
                    "-i",
                    str(audio),
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-shortest",
                    str(out_video),
                ]
            )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest app/tests/test_generation_echomimic.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Route the orchestrator on `GENERATION_ENGINE`**

In `backend/app/pipelines/generation/orchestrator.py`, add `avatar_halfbody_path` to the `app.core.paths` import block (after `avatar_face_path` on line 19):

```python
    avatar_halfbody_path,
```

Then replace Stage 2 + Stage 3 (lines 106-126) with this branch:

```python
        # Stages 2–3 — visual. Either LivePortrait+MuseTalk (head) or EchoMimic v2
        # (half-body + gestures). Both write the pre-mux clip to the lipsync path.
        lipsync = output_lipsync_path(job.id)
        if settings.GENERATION_ENGINE.lower() == "echomimic":
            db_queue.set_progress(db, job, progress.band_start("liveportrait"))
            halfbody = avatar_halfbody_path(job.avatar_id)
            backend.generate_video(
                lipsync,
                reference_image=halfbody if halfbody.exists() else None,
                audio=speech,
                duration_s=duration,
                fps=fps,
            )
            db_queue.set_progress(db, job, progress.band_end("musetalk"))
            _guard_cancel(db, job)
        else:
            # Stage 2 — LivePortrait animation
            db_queue.set_progress(db, job, progress.band_start("liveportrait"))
            face = avatar_face_path(job.avatar_id)
            driving = avatar_driving_path(job.avatar_id)
            animated = output_animated_path(job.id)
            backend.animate(
                animated,
                face=face if face.exists() else None,
                driving=driving if driving.exists() else None,
                duration_s=duration,
                fps=fps,
            )
            db_queue.set_progress(db, job, progress.band_end("liveportrait"))
            _guard_cancel(db, job)

            # Stage 3 — MuseTalk lip-sync
            db_queue.set_progress(db, job, progress.band_start("musetalk"))
            backend.lipsync(animated, speech, lipsync)
            db_queue.set_progress(db, job, progress.band_end("musetalk"))
            _guard_cancel(db, job)
```

Note: the `lipsync` local that Stage 4 uses (line 123 originally `lipsync = output_lipsync_path(job.id)`) is now defined once at the top of this block, so remove the now-duplicate assignment inside the old Stage 3 (it is already removed in the replacement above). Stage 4 (`steps.mux_output(lipsync, speech, final, ...)`) is unchanged.

- [ ] **Step 7: Run the full suite to confirm no regression**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest`
Expected: PASS (all prior tests + the new ones; default engine is still `liveportrait`, so existing behavior is untouched).

- [ ] **Step 8: Commit**

```bash
git add backend/app/pipelines/generation/ml/backends.py backend/app/pipelines/generation/orchestrator.py backend/app/tests/test_generation_echomimic.py
git commit -m "feat(echomimic): generate_video stub + GENERATION_ENGINE orchestrator routing"
```

---

## Task 5: `RealBackend.generate_video` (subprocess into envEM)

No local unit test (requires GPU); validated by `py_compile` and on Kaggle. Mirrors the existing `RealBackend.lipsync` subprocess pattern.

**Files:**
- Modify: `backend/app/pipelines/generation/ml/backends.py` (add method to `RealBackend`)

- [ ] **Step 1: Add `generate_video` to `RealBackend`**

In `backend/app/pipelines/generation/ml/backends.py`, add this method to `RealBackend` after `lipsync` (after line 276). Also add the version constant near the top constants (after line 25, `MUSETALK_VERSION = "musetalk-v1"`): `ECHOMIMIC_VERSION = "echomimic-v2"`.

```python
    def generate_video(
        self,
        out_video: Path,
        *,
        reference_image: Path | None,
        audio: Path,
        duration_s: float,
        fps: int,
    ) -> None:  # pragma: no cover - requires ML stack
        from app.core.config import settings
        from app.pipelines._subproc import run_in_env

        out_video.parent.mkdir(parents=True, exist_ok=True)
        runners = str(Path(settings.RUNNERS_DIR).resolve())
        if reference_image is None or not Path(reference_image).exists():
            raise RuntimeError(
                "EchoMimic requires a half-body reference image; recreate the avatar "
                "on this branch so reference_halfbody.png is generated."
            )
        # EchoMimic v2 expects 16 kHz mono audio (whisper-based audio encoder).
        audio16 = out_video.parent / "speech_16k.wav"
        run_ffmpeg(["-y", "-i", str(audio), "-ar", "16000", "-ac", "1", str(audio16)])
        repo = f"{settings.AI_ROOT}/EchoMimicV2"
        run_in_env(
            settings.ENV_EM,
            [
                "python",
                f"{runners}/echomimic_generate.py",
                "--reference",
                str(reference_image),
                "--audio",
                str(audio16),
                "--repo",
                repo,
                "--pose-name",
                settings.ECHOMIMIC_POSE_NAME,
                "--out",
                str(out_video),
                "--width",
                str(settings.ECHOMIMIC_WIDTH),
                "--height",
                str(settings.ECHOMIMIC_HEIGHT),
                "--steps",
                str(settings.ECHOMIMIC_STEPS),
                "--cfg",
                str(settings.ECHOMIMIC_CFG),
                "--fps",
                str(fps),
                "--seconds",
                f"{duration_s:.3f}",
            ],
            cwd=repo,
        )
        if not out_video.exists() or out_video.stat().st_size == 0:
            raise RuntimeError("EchoMimic produced no output video")
```

- [ ] **Step 2: Verify it compiles**

Run: `cd backend && .venv/bin/python -m py_compile app/pipelines/generation/ml/backends.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Confirm the stub suite still passes (RealBackend not exercised locally)**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipelines/generation/ml/backends.py
git commit -m "feat(echomimic): RealBackend.generate_video subprocess into envEM"
```

---

## Task 6: `echomimic_generate.py` runner (wraps infer.py)

Runs **inside `envEM`** with `cwd` = the EchoMimic v2 repo. It stages our inputs into the directory/name layout that `infer.py` expects (verified args: `-W -H -L --steps --cfg --fps --ref_images_dir --refimg_name --audio_dir --audio_name --pose_dir --pose_name`), palindrome-loops the bundled pose `.npy` sequence to cover the audio length, invokes `infer.py`, and copies the resulting MP4 to `--out`.

**Files:**
- Create: `ml_models/runners/echomimic_generate.py`

- [ ] **Step 1: Create the runner**

Create `ml_models/runners/echomimic_generate.py`:

```python
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
    os.makedirs(ref_dir, exist_ok=True)
    os.makedirs(aud_dir, exist_ok=True)
    shutil.copyfile(args.reference, os.path.join(ref_dir, "ref.png"))
    shutil.copyfile(args.audio, os.path.join(aud_dir, "aud.wav"))
    frames = _build_looped_pose(src_pose_dir, os.path.join(pose_root, "loop"), n_frames)

    out_root = os.path.join(args.repo, "outputs")
    before = set(glob.glob(os.path.join(out_root, "**", "*.mp4"), recursive=True))

    cmd = [
        sys.executable, "infer.py",
        "--config", "./configs/prompts/infer.yaml",
        "-W", str(args.width), "-H", str(args.height), "-L", str(frames),
        "--steps", str(args.steps), "--cfg", str(args.cfg), "--fps", str(args.fps),
        "--ref_images_dir", ref_dir, "--refimg_name", "ref.png",
        "--audio_dir", aud_dir, "--audio_name", "aud.wav",
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python -m py_compile ml_models/runners/echomimic_generate.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ml_models/runners/echomimic_generate.py
git commit -m "feat(echomimic): echomimic_generate.py runner wrapping infer.py"
```

---

## Task 7: `setup_env_em.sh` env builder

Mirrors `setup_env_lp.sh`. EchoMimic v2 (verified from its README): Python 3.10, torch 2.5.1/cu121 + xformers 0.0.28.post3, `requirements.txt`, `facenet_pytorch==2.6.0 --no-deps`; weights from `BadToBest/EchoMimicV2` → `pretrained_weights/`.

**Files:**
- Create: `ml_models/runners/setup_env_em.sh`

- [ ] **Step 1: Create the setup script**

Create `ml_models/runners/setup_env_em.sh`:

```bash
#!/usr/bin/env bash
# envEM: EchoMimic v2 (torch 2.5.1/cu121 + xformers), isolated env.
# Usage: bash setup_env_em.sh [ROOT]   (ROOT defaults to /tmp/aiavatar)
set -euo pipefail

ENV=envEM
ROOT="${1:-/tmp/aiavatar}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAMBA="$ROOT/bin/micromamba"
export MAMBA_ROOT_PREFIX="$ROOT/mamba"
export MPLBACKEND=Agg
cd "$ROOT"

bash "$SCRIPT_DIR/bootstrap_micromamba.sh" "$ROOT"

echo "[envEM] creating env (python 3.10)…"
[ -d "$ROOT/mamba/envs/$ENV" ] || "$MAMBA" create -y -n "$ENV" -c conda-forge python=3.10 pip

echo "[envEM] cloning EchoMimic v2…"
REPO="$ROOT/EchoMimicV2"
[ -d "$REPO" ] || git clone https://github.com/antgroup/echomimic_v2 "$REPO"

echo "[envEM] installing torch 2.5.1 / cu121 + xformers…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir \
  torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
  --index-url https://download.pytorch.org/whl/cu121
"$MAMBA" run -n "$ENV" pip install --no-cache-dir xformers==0.0.28.post3 \
  --index-url https://download.pytorch.org/whl/cu121

echo "[envEM] installing EchoMimic requirements…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir -r "$REPO/requirements.txt"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir --no-deps facenet_pytorch==2.6.0

echo "[envEM] pinning torch back to 2.5.1/cu121 (in case requirements bumped it)…"
"$MAMBA" run -n "$ENV" pip install --no-cache-dir --force-reinstall --no-deps \
  torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
  --index-url https://download.pytorch.org/whl/cu121

# Weights: cached dataset (WEIGHTS_SRC/em_weights) if provided, else download.
WTS="$REPO/pretrained_weights"
if [ -n "${WEIGHTS_SRC:-}" ] && [ -d "$WEIGHTS_SRC/em_weights" ]; then
  echo "[envEM] restoring EchoMimic weights from cache: $WEIGHTS_SRC/em_weights"
  mkdir -p "$WTS"
  cp -rn "$WEIGHTS_SRC/em_weights/." "$WTS/"
else
  echo "[envEM] downloading EchoMimic v2 weights (BadToBest/EchoMimicV2)…"
  "$MAMBA" run -n "$ENV" huggingface-cli download BadToBest/EchoMimicV2 \
    --local-dir "$WTS" --exclude "*.git*" "README.md"
fi

# Some infer.yaml paths reference external base models; fetch only if missing.
[ -d "$WTS/sd-image-variations-diffusers" ] || \
  "$MAMBA" run -n "$ENV" huggingface-cli download lambdalabs/sd-image-variations-diffusers \
    --local-dir "$WTS/sd-image-variations-diffusers" --exclude "*.git*" || true
[ -d "$WTS/wav2vec2-base-960h" ] || \
  "$MAMBA" run -n "$ENV" huggingface-cli download facebook/wav2vec2-base-960h \
    --local-dir "$WTS/wav2vec2-base-960h" --exclude "*.git*" || true

echo "[envEM] verifying torch + key weights…"
"$MAMBA" run -n "$ENV" python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
for f in denoising_unet.pth reference_unet.pth motion_module.pth pose_encoder.pth; do
  [ -f "$WTS/$f" ] && echo "[envEM] ok: $f" || echo "[envEM] WARN missing: $WTS/$f"
done

echo "[envEM] READY"
```

- [ ] **Step 2: Verify the script parses**

Run: `bash -n ml_models/runners/setup_env_em.sh && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ml_models/runners/setup_env_em.sh
git commit -m "feat(echomimic): setup_env_em.sh builds envEM + EchoMimic v2 weights"
```

---

## Task 8: Wire EchoMimic into the Kaggle notebook generator

Add an optional `envEM` build cell and set `GENERATION_ENGINE=echomimic` in the launch cell on this branch.

**Files:**
- Modify: `ml_models/build_backend_notebook.py`

- [ ] **Step 1: Add the envEM build cell**

In `ml_models/build_backend_notebook.py`, after the cell 5 `code(...)` block (the `setup_env_mt.sh` one ending at line 93), add:

```python
code(
    "# 5b. Build envEM (EchoMimic v2 — half-body + hand gestures). Heavy; ~25-40 min,\n"
    "#     and inference is SLOW on a T4. Only needed for the EchoMimic comparison.\n"
    f"!bash {RUNNERS}/setup_env_em.sh {WORK}"
)
```

- [ ] **Step 2: Set GENERATION_ENGINE in the launch cell**

In the same file, in the cell-7 `srv_env` dict (the launch cell, lines 118-124), add the engine line after the `'PIPELINE_BACKEND': 'real',` entry:

```python
    "    'GENERATION_ENGINE': 'echomimic',\n"
```

- [ ] **Step 3: Update the intro markdown to mention the engine choice**

In the same file, in the final `md(...)` "Use it from the website" block (lines 159-167), append a sentence before the closing `"`:

```python
    " This branch defaults to the **EchoMimic v2** engine (half-body + gestures); "
    "set `GENERATION_ENGINE=liveportrait` in cell 7 to compare against the head-only path."
```

- [ ] **Step 4: Regenerate the notebook and validate JSON**

Run:
```bash
cd ml_models && python build_backend_notebook.py && python -c "import json; n=json.load(open('backend_server.ipynb')); print('cells', len(n['cells'])); assert all('cell_type' in c for c in n['cells'])"
```
Expected: prints the new cell count (one more than before) and no assertion error.

- [ ] **Step 5: Commit**

```bash
git add ml_models/build_backend_notebook.py ml_models/backend_server.ipynb
git commit -m "feat(echomimic): notebook builds envEM + defaults to echomimic engine"
```

---

## Task 9: Update the spec's open items + final verification

**Files:**
- Modify: `docs/superpowers/specs/2026-06-18-echomimic-v2-backend-design.md` (resolve §10)

- [ ] **Step 1: Mark resolved verification items**

In the spec's §10, append the now-known facts (from the EchoMimic v2 repo):

```markdown

### Resolved (during planning, from antgroup/echomimic_v2)

- **Env:** Python 3.10, `torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1
  xformers==0.0.28.post3` (cu121), `requirements.txt`, `facenet_pytorch==2.6.0 --no-deps`.
- **Inference CLI:** `python infer.py --config ./configs/prompts/infer.yaml` with args
  `-W -H -L --steps --cfg --fps --ref_images_dir --refimg_name --audio_dir --audio_name
  --pose_dir --pose_name`. Pose templates are numbered `.npy` files under
  `assets/halfbody_demo/pose/<name>/`; output MP4 lands under `outputs/`.
- **Weights:** `BadToBest/EchoMimicV2` → `pretrained_weights/` (denoising_unet.pth,
  reference_unet.pth, motion_module.pth, pose_encoder.pth, sd-vae-ft-mse/,
  audio_processor/tiny.pt); plus sd-image-variations-diffusers + wav2vec2-base-960h.
- **Output length is bounded by the pose template.** The runner palindrome-loops the
  pose `.npy` sequence to cover the audio length (mirrors the LivePortrait boomerang),
  so gestures repeat for long scripts.
```

- [ ] **Step 2: Run the full backend test suite one final time**

Run: `cd backend && PIPELINE_BACKEND=stub .venv/bin/python -m pytest -q`
Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-18-echomimic-v2-backend-design.md
git commit -m "docs(echomimic): resolve spec open items from repo research"
```

---

## Kaggle validation (manual, after merge of these tasks to the branch)

Not a code task — the real-GPU smoke test the user runs:

1. On Kaggle: `git -C /kaggle/working/Ai-Avatar fetch && git -C /kaggle/working/Ai-Avatar checkout echomimic-v2-backend && git -C /kaggle/working/Ai-Avatar pull`.
2. Run notebook cells through 5b (`setup_env_em.sh`) — builds `envEM` (slow).
3. Launch (cell 7 now sets `GENERATION_ENGINE=echomimic`), expose URL (cell 8).
4. In the website: **re-create the avatar** (so `reference_halfbody.png` exists) with a half-body video, then generate a short script.
5. Compare against a `main`-branch (LivePortrait+MuseTalk) run of the same script.
6. If OOM: lower `ECHOMIMIC_WIDTH`/`ECHOMIMIC_HEIGHT` (e.g. 512) and `ECHOMIMIC_STEPS` (e.g. 12) via the launch-cell `srv_env`, or move to a bigger GPU.
7. Once `envEM` builds, run `snapshot_envs.sh` to capture it into the `ai-avatar-envs` tarball (it already tars all of `${AI_ROOT}`).
