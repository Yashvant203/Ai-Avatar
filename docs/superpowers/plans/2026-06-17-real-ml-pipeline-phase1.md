# Real ML Pipeline — Phase 1 (Backend Integration) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the website's real "Create Avatar → Generate" flow produce a talking head in the user's own cloned voice + face, by wiring the proven F5-TTS / LivePortrait / MuseTalk runners into the backend's `RealBackend` via subprocess.

**Architecture:** The FastAPI app/worker run in Kaggle's base env (no ML imports) and orchestrate by shelling out to three isolated micromamba envs (envF5/envLP/envMT) through the runner scripts proven in Phase 0. File-based handoff between stages. StubBackend is kept for no-GPU dev.

**Tech Stack:** FastAPI, SQLAlchemy, micromamba, the Phase 0 proof scripts (`ml_models/proof/`), F5-TTS, LivePortrait, MuseTalk, cloudflared.

**Spec:** `docs/superpowers/specs/2026-06-17-real-ml-pipeline-design.md` (§4 architecture, §5 data model, §8 phase list).
**Phase 0 (done):** `docs/superpowers/plans/2026-06-17-real-ml-pipeline-phase0.md` — the runners + every fix (micromamba, MPLBACKEND=Agg, chumpy `--no-build-isolation`, huggingface_hub==0.30.2 pin, Python-API weight download, non-`_concat` LivePortrait output) all live in `ml_models/proof/` and are PROVEN. Reuse them; don't re-derive.

**Execution note:** Run this in a FRESH session (Phase 0's chat is near its context limit). Everything needed is in the repo + the `ai-avatar-weights` Kaggle dataset.

---

## Key facts carried from Phase 0 (the contract the backend must honor)

- **Envs** under `/tmp/aiavatar` (the big disk): `envF5` (F5-TTS), `envLP` (torch2.3/cu121 + LivePortrait + insightface), `envMT` (torch2.0.1/cu118 + MuseTalk + mmcv). Run a command in one via `bash ml_models/proof/mrun.sh <env> <cmd…>` (honors `PROOF_ROOT`, default `/tmp/aiavatar`).
- **F5-TTS** (envF5): `run_f5tts.py --ref REF.wav --ref-text "…" --gen-text "…" --out speech.wav` → 24 kHz wav. No reusable "voice model" — the artifact is `reference.wav` + transcript.
- **LivePortrait** (envLP): `run_liveportrait.sh SRC_IMG DRIVING_MP4 OUT_DIR` → animated mp4. Output is `<src>--<driving>.mp4` (the clean one — NOT `*_concat.mp4`). Driving must be looped to ≥ speech length.
- **MuseTalk** (envMT): `run_musetalk.py --video animated_25.mp4 --audio speech_16k.wav --result-dir DIR` (run with cwd = MuseTalk repo, via mrun). Needs 25 fps video + 16 kHz mono audio. Has `--bbox-shift`.
- **insightface** lives in envLP (bundled with LivePortrait's `pretrained_weights/insightface`) — use it for avatar-creation face selection.

---

## File Structure

**New:**
- `ml_models/runners/` — promote the proven `ml_models/proof/` scripts to a production home (copy: `mrun.sh`, `bootstrap_micromamba.sh`, `setup_env_f5.sh`, `setup_env_lp.sh`, `setup_env_mt.sh`, `run_f5tts.py`, `run_liveportrait.sh`, `run_musetalk.py`, `download_mt_weights.py`). Add `select_face.py` (insightface face crop, envLP) and `restore_weights.sh` (copy weights from the mounted Kaggle dataset into `/tmp/aiavatar`).
- `ml_models/assets/idle_motion.mp4` — a short, **frontal, camera-facing** idle-head driving clip (fixes the "eyes wander" problem from the proof's `d0.mp4`). Committed (a few hundred KB).
- `backend/app/pipelines/_subproc.py` — one small helper: `run_in_env(env, args, cwd=None) -> CompletedProcess`, wrapping `mrun.sh`.
- `ml_models/backend_server.ipynb` — Kaggle notebook: restore weights from dataset → build the 3 envs → launch API + worker (`PIPELINE_BACKEND=real`) + cloudflared.

**Rewrite:**
- `backend/app/pipelines/generation/ml/backends.py` — `RealBackend.synthesize_speech/animate/lipsync` → subprocess.
- `backend/app/pipelines/avatar_creation/ml/backends.py` — `RealBackend.select_reference/build_voice_model/select_best_face/prep_appearance` → subprocess.
- `backend/app/pipelines/avatar_creation/ml/loaders.py` — delete the in-process `get_liveportrait`/`get_face_analyzer`; keep `get_backend`.

**Edit:**
- `backend/app/pipelines/avatar_creation/runner.py` — voice stage stores `reference.wav` + `transcript.txt` (no `.pt`); motion stage becomes a no-op validation.
- `backend/app/pipelines/generation/orchestrator.py` — pass `face.png` + shared idle motion to `animate`.
- `backend/app/core/config.py` — add settings (below).
- `backend/app/core/paths.py` — add `voice_transcript_path`; the existing `voice_model_path`/`avatar_motion_template_path` become unused (leave or remove).

**Keep untouched:** app, auth, DB models, queue, worker, routers, StubBackend.

---

## Task 1: Config + subprocess helper + promote runners

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/pipelines/_subproc.py`
- Create: `ml_models/runners/` (copy of proof scripts) + `ml_models/runners/restore_weights.sh`

- [ ] **Step 1: Add settings** to `Settings` in `backend/app/core/config.py`:

```python
    # --- Real ML pipeline (subprocess runners) ---
    AI_ROOT: str = "/tmp/aiavatar"            # micromamba envs + model repos live here
    RUNNERS_DIR: str = "../ml_models/runners"  # relative to backend/ cwd
    IDLE_MOTION_PATH: str = "../ml_models/assets/idle_motion.mp4"
    MUSETALK_BBOX_SHIFT: int = 0               # tune per-face; range hint -20..18
    ENV_F5: str = "envF5"
    ENV_LP: str = "envLP"
    ENV_MT: str = "envMT"
```

- [ ] **Step 2: Write the subprocess helper** `backend/app/pipelines/_subproc.py`:

```python
"""Run a command inside one of the Phase-0 micromamba envs via mrun.sh."""
from __future__ import annotations

import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("pipeline.subproc")


def run_in_env(env: str, args: list[str], *, cwd: str | None = None) -> None:
    """Invoke `args` inside micromamba env `env`. Raises PipelineError-friendly on failure."""
    runners = Path(settings.RUNNERS_DIR).resolve()
    cmd = ["bash", str(runners / "mrun.sh"), env, *args]
    env_vars = {"PROOF_ROOT": settings.AI_ROOT}
    logger.info("run_in_env %s: %s", env, " ".join(args))
    proc = subprocess.run(
        cmd, cwd=cwd, env={**_os_environ(), **env_vars},
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        logger.error("env %s failed (%s): %s", env, proc.returncode, proc.stderr[-2000:])
        raise RuntimeError(f"{env} runner failed: {proc.stderr[-500:]}")


def _os_environ() -> dict:
    import os
    return dict(os.environ)
```

- [ ] **Step 3: Promote runners** — copy the proven scripts into `ml_models/runners/`:

```bash
mkdir -p ml_models/runners ml_models/assets
cp ml_models/proof/{mrun.sh,bootstrap_micromamba.sh,setup_env_f5.sh,setup_env_lp.sh,setup_env_mt.sh,run_f5tts.py,run_liveportrait.sh,run_musetalk.py,download_mt_weights.py} ml_models/runners/
chmod +x ml_models/runners/*.sh
```

- [ ] **Step 4: Write `ml_models/runners/restore_weights.sh`** (copy cached weights from the mounted Kaggle dataset, so setup skips downloads):

```bash
#!/usr/bin/env bash
# Restore weights from the mounted `ai-avatar-weights` Kaggle dataset into AI_ROOT.
# Usage: bash restore_weights.sh [DATASET_DIR] [ROOT]
set -euo pipefail
SRC="${1:-/kaggle/input/ai-avatar-weights/aa_cache}"
ROOT="${2:-/tmp/aiavatar}"
mkdir -p "$ROOT/LivePortrait" "$ROOT/MuseTalk" /root/.cache
unzip -q -o "$SRC/lp_weights.zip" -d "$ROOT/LivePortrait/" || cp -r "$SRC/lp_weights" "$ROOT/LivePortrait/pretrained_weights"
unzip -q -o "$SRC/mt_models.zip"  -d "$ROOT/MuseTalk/"     || cp -r "$SRC/mt_models"  "$ROOT/MuseTalk/models"
unzip -q -o "$SRC/hf_cache.zip"   -d /root/.cache/         || cp -r "$SRC/hf_cache"   /root/.cache/huggingface
echo "weights restored from $SRC"
```
(The dataset stored each folder as a zip via `--dir-mode zip`; adjust the unzip targets after first inspecting the dataset layout with `find /kaggle/input/ai-avatar-weights -maxdepth 2`.)

- [ ] **Step 5: Local gate + commit**

```bash
python -m py_compile backend/app/pipelines/_subproc.py && echo OK
bash -n ml_models/runners/restore_weights.sh && echo OK
git add backend/app/core/config.py backend/app/pipelines/_subproc.py ml_models/runners/
git commit -m "feat(phase1): config + subprocess env helper + promoted runners"
```

---

## Task 2: Rewrite the generation RealBackend (subprocess)

**Files:** Rewrite `backend/app/pipelines/generation/ml/backends.py` `RealBackend`.

- [ ] **Step 1: Replace the three methods.** The `Protocol`, `StubBackend`, and module constants stay. Replace `RealBackend` with:

```python
class RealBackend:
    name = "real"

    @staticmethod
    def is_available() -> bool:
        from pathlib import Path
        from app.core.config import settings
        return Path(settings.AI_ROOT, "mamba", "envs", settings.ENV_F5).exists()

    def synthesize_speech(self, out_speech, *, script_text, voice_ref, duration_s):
        from app.core.config import settings
        from app.pipelines._subproc import run_in_env
        runners = settings.RUNNERS_DIR
        transcript = voice_ref.with_suffix(".txt") if voice_ref else None
        ref_text = transcript.read_text().strip() if transcript and transcript.exists() else ""
        run_in_env(settings.ENV_F5, [
            "python", f"{runners}/run_f5tts.py",
            "--ref", str(voice_ref), "--ref-text", ref_text,
            "--gen-text", script_text, "--out", str(out_speech),
        ])
        import soundfile as sf  # base env has soundfile; or probe with ffprobe
        info = sf.info(str(out_speech))
        return info.frames / info.samplerate

    def animate(self, out_animated, *, face, duration_s, fps):
        from app.core.config import settings
        from app.pipelines._subproc import run_in_env
        from app.pipelines.avatar_creation.ml.ffmpeg import run_ffmpeg
        import glob, shutil
        # loop the camera-facing idle clip to >= speech duration
        looped = out_animated.parent / "driving_loop.mp4"
        run_ffmpeg(["-y", "-stream_loop", "-1", "-i", settings.IDLE_MOTION_PATH,
                    "-t", f"{duration_s:.2f}", "-r", str(fps), str(looped)])
        out_dir = out_animated.parent / "lp_out"
        run_in_env(settings.ENV_LP, [
            "bash", f"{settings.RUNNERS_DIR}/run_liveportrait.sh",
            str(face), str(looped), str(out_dir), settings.AI_ROOT,
        ])
        clean = [f for f in sorted(glob.glob(f"{out_dir}/*.mp4")) if "concat" not in f][-1]
        run_ffmpeg(["-y", "-i", clean, "-r", str(fps), str(out_animated)])  # normalize 25fps

    def lipsync(self, animated, speech, out_lipsync):
        from app.core.config import settings
        from app.pipelines._subproc import run_in_env
        from app.pipelines.avatar_creation.ml.ffmpeg import run_ffmpeg
        import glob, shutil
        speech16 = out_lipsync.parent / "speech_16k.wav"
        run_ffmpeg(["-y", "-i", str(speech), "-ar", "16000", "-ac", "1", str(speech16)])
        mt_out = out_lipsync.parent / "mt_out"
        run_in_env(settings.ENV_MT, [
            "python", f"{settings.RUNNERS_DIR}/run_musetalk.py",
            "--video", str(animated), "--audio", str(speech16),
            "--result-dir", str(mt_out), "--bbox-shift", str(settings.MUSETALK_BBOX_SHIFT),
        ], cwd=f"{settings.AI_ROOT}/MuseTalk")
        result = glob.glob(f"{mt_out}/**/*.mp4", recursive=True)[-1]
        shutil.copyfile(result, out_lipsync)
```

- [ ] **Step 2: Local gate + commit**

```bash
python -m py_compile backend/app/pipelines/generation/ml/backends.py && echo OK
git add backend/app/pipelines/generation/ml/backends.py
git commit -m "feat(phase1): generation RealBackend via subprocess runners"
```

---

## Task 3: Rewrite the avatar-creation RealBackend (subprocess)

**Files:** Rewrite `RealBackend` in `backend/app/pipelines/avatar_creation/ml/backends.py`; delete in-process loaders in `loaders.py`.

- [ ] **Step 1: `select_reference`** — pick a ~10 s clean segment with ffmpeg (loudness/silence trim, then cut), no torch needed:

```python
    def select_reference(self, src_audio, out_reference, *, script_text=None):
        from app.pipelines.avatar_creation.ml.ffmpeg import run_ffmpeg
        run_ffmpeg(["-y", "-i", str(src_audio), "-t", "10", "-ac", "1", "-ar", "24000", str(out_reference)])
        return {"reference_path": str(out_reference), "transcript": "", "qc": {}, "duration_s": 10.0}
```

- [ ] **Step 2: `build_voice_model`** — F5 is in-context; transcribe the reference once (envF5/Whisper) and store `transcript.txt`. No `.pt`:

```python
    def build_voice_model(self, reference, transcript, out_model, *, sample_rate):
        from app.core.config import settings
        from app.pipelines._subproc import run_in_env
        txt = reference.with_suffix(".txt")
        # transcribe reference with F5's bundled Whisper (ref_text="" path), write to txt
        run_in_env(settings.ENV_F5, ["python", f"{settings.RUNNERS_DIR}/transcribe.py",
                                     "--audio", str(reference), "--out", str(txt)])
        return {"model_path": str(txt), "model_version": "f5-incontext", "transcript_path": str(txt)}
```
(Add a tiny `ml_models/runners/transcribe.py` that loads `F5TTS().transcribe(audio)` or uses `transformers` whisper-tiny, writes text. Alternatively reuse `script_text` if you trust the user read it verbatim.)

- [ ] **Step 3: `select_best_face`** — run insightface in envLP via a new `ml_models/runners/select_face.py` that picks the sharpest frontal face, crops 512×512, writes `face.png` + `thumb.png`, prints bbox/pose JSON. The backend method shells out and parses that JSON.

- [ ] **Step 4: `prep_appearance`** — becomes validation only (no per-avatar template; the shared idle motion is used at generation time):

```python
    def prep_appearance(self, face, out_template):
        out_template.write_bytes(b"")  # placeholder; appearance is recomputed per-generation
        return {"path": str(out_template), "model": LIVEPORTRAIT_VERSION}
```

- [ ] **Step 5:** In `loaders.py`, delete `get_liveportrait` and `get_face_analyzer` (now subprocess). Keep `get_backend`.

- [ ] **Step 6: Local gate + commit**

```bash
python -m py_compile backend/app/pipelines/avatar_creation/ml/backends.py backend/app/pipelines/avatar_creation/ml/loaders.py && echo OK
git add backend/app/pipelines/avatar_creation/ml/ ml_models/runners/
git commit -m "feat(phase1): avatar-creation RealBackend via subprocess runners"
```

---

## Task 4: Adapt orchestration + data model + idle asset

**Files:** `runner.py`, `orchestrator.py`, `paths.py`, add `ml_models/assets/idle_motion.mp4`.

- [ ] **Step 1:** In `avatar_creation/runner.py`, the voice stage already calls `build_voice_model` → now it produces a transcript path; persist `reference.wav` + `transcript.txt` on the `VoiceModel` row (reuse existing columns; store transcript path where `model_path` went). Motion stage (`prep_appearance`) stays but is a no-op.
- [ ] **Step 2:** In `generation/orchestrator.py`, confirm `animate(out, face=<avatar face.png>, duration_s, fps=25)` and `lipsync(animated, speech, out)` are called with the avatar's `face.png` (already on the profile). No DB schema change required.
- [ ] **Step 3:** Add `ml_models/assets/idle_motion.mp4` — a 3–5 s frontal, eyes-on-camera, subtle idle-head clip (record one, or trim a CC clip). Commit it.
- [ ] **Step 4:** Run the backend test suite with the **stub** backend to confirm nothing regressed:

```bash
cd backend && PIPELINE_BACKEND=stub pytest -q
```
Expected: all green (stub path unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipelines/ backend/app/core/paths.py ml_models/assets/idle_motion.mp4
git commit -m "feat(phase1): adapt orchestration + data model for in-context voice + shared idle motion"
```

---

## Task 5: Kaggle backend-server notebook

**Files:** Create `ml_models/backend_server.ipynb` (via a `build_backend_notebook.py` generator, like Phase 0).

- [ ] **Step 1:** Cells:
  1. Clone repo + `Add Data → ai-avatar-weights` mounted at `/kaggle/input/ai-avatar-weights`.
  2. `bash ml_models/runners/restore_weights.sh` (skip downloads).
  3. `bash ml_models/runners/setup_env_f5.sh /tmp/aiavatar` (+ lp, mt) — fast now (weights restored; pip still installs).
  4. `pip install -e backend` (base env), `alembic upgrade head`.
  5. `os.environ["PIPELINE_BACKEND"]="real"`, `JWT_SECRET`, `CORS_ORIGINS="*"`; launch `python -m worker.main` + `uvicorn app.main:app --port 7860`.
  6. cloudflared tunnel → public API URL.
- [ ] **Step 2:** Local gate (notebook valid) + commit.

---

## Task 6: End-to-end verification THROUGH the frontend

- [ ] **Step 1:** Run `backend_server.ipynb` on Kaggle → copy the tunnel URL.
- [ ] **Step 2:** Set `frontend/.env.local` → `NEXT_PUBLIC_API_BASE_URL=<tunnel>`, `npm run dev`.
- [ ] **Step 3:** In the website: **sign up → Create Avatar → upload a 2–5 min video of yourself** → wait for "ready" (real face + voice extracted).
- [ ] **Step 4:** **Generate → type a script** → confirm the downloaded MP4 is *you* speaking, eyes on camera, lip-synced.
- [ ] **Step 5:** Tune `MUSETALK_BBOX_SHIFT` and the idle clip if mouth/gaze need polish; re-generate.

**Definition of done:** a non-technical user, entirely through the website, uploads their video and gets back a talking-head MP4 in their own voice and face.

---

## Self-Review Notes
- Spec coverage: §4 subprocess architecture → Tasks 1–3; §5 data model (drop `.pt` + per-avatar template) → Tasks 3–4; §8 Phase 1 scope → all tasks. Quality fixes (idle motion, bbox_shift) → Tasks 2/4/6.
- Reuses Phase 0 proven scripts verbatim (no re-derivation of the 6 hard-won fixes).
- StubBackend + full app/auth/queue untouched; `PIPELINE_BACKEND=stub pytest` is the regression gate (Task 4 Step 4).
- Open item to resolve at execution: exact dataset zip layout for `restore_weights.sh` (inspect `/kaggle/input/ai-avatar-weights` first); and choice of transcript source (Whisper vs trusting the training script text).
