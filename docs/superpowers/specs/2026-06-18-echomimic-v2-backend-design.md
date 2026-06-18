# EchoMimic v2 Generation Backend — Design

**Date:** 2026-06-18
**Status:** Approved (brainstorming)
**Author:** Yashvant203 + Claude
**Branch:** `echomimic-v2-backend`

## 1. Goal

Add a **second video-generation engine** based on **EchoMimic v2** so the platform
can produce a **half-body talking avatar with visible hand/arm gestures**, and so
the user can **compare it side-by-side** against the existing
LivePortrait + MuseTalk (head-only) output for the same script.

The user's **voice clone (F5-TTS) is unchanged** — only the *visual* half of
generation is replaced.

### Explicit non-goals (YAGNI)

- **Gestures matched to speech semantics** (HeyGen-style). EchoMimic v2 is
  *pose-template driven*: hands replay a fixed gesture sequence. This is accepted.
- **Pose extraction from the user's own upload** (DWPose). v1 uses bundled pose
  templates only. Per-avatar gesture extraction is a possible future phase.
- **Replacing the LivePortrait+MuseTalk path.** Both engines coexist behind a flag.

## 2. Expectations / honest constraints

- **EchoMimic v2 ≠ HeyGen.** It is open-source, pose-template driven, and replays
  fixed gestures — it does not invent gestures from the script.
- **Performance on Kaggle T4 (16 GB).** EchoMimic v2 is a heavy diffusion model.
  Expect **minutes per few seconds of output**. It may require reduced
  resolution / fewer denoising steps to fit in 16 GB, and may OOM — in which case
  the remedy is a larger GPU (e.g. A100), not a code change. The runner sets
  conservative defaults and surfaces clear OOM errors.
- **Reference framing requirement.** EchoMimic v2 animates a **half-body** image
  (head + torso + arm/hand region). Avatar training videos must be recorded
  **waist/chest up** (confirmed: the user records half-body). A face-only crop
  cannot produce hands.

## 3. What stays vs. what changes

| Stage | Current path | EchoMimic v2 path |
|---|---|---|
| Voice | F5-TTS → cloned audio (`envF5`) | **F5-TTS → cloned audio** (unchanged) |
| Visual | LivePortrait head motion (`envLP`) → MuseTalk lip-sync (`envMT`) | **EchoMimic v2** single diffusion pass (`envEM`): reference image + audio + pose template → half-body video with gestures + lip-sync |

EchoMimic v2 collapses *animate* + *lip-sync* into **one** model call.

## 4. Architecture

Follows the existing **isolated-env + subprocess** pattern (each model in its own
micromamba env, invoked via `ml_models/runners/mrun.sh`).

### 4.1 New isolated env `envEM`

- New setup script `ml_models/runners/setup_env_em.sh` (mirrors `setup_env_*.sh`).
- Installs EchoMimic v2's pinned deps (torch + diffusers stack) into
  `${AI_ROOT}/mamba/envs/envEM`, isolated from envF5/LP/MT.
- Clones the EchoMimic v2 repo under `${AI_ROOT}/EchoMimicV2`.
- Fetches model weights (`BadToBest/EchoMimicV2` on HuggingFace) honoring the
  existing `WEIGHTS_SRC` cache convention (`WEIGHTS_SRC/em_models` if present,
  else download). Weights participate in the env snapshot/restore tarball.

### 4.2 New runner `echomimic_generate.py`

Runs in `envEM`. Single entry point:

```
python echomimic_generate.py \
  --reference reference_halfbody.png \
  --audio speech.wav \
  --pose-dir <bundled pose template dir> \
  --out output.mp4 \
  [--steps N] [--width W] [--height H]
```

- Loops/truncates the pose template to the audio length.
- Calls EchoMimic v2's inference, writes the final muxed MP4.
- Conservative T4 defaults for steps/resolution; prints a clear message on CUDA OOM.
- Prints a final JSON line (`{"path": "...", "frames": N, ...}`) parsed by the backend.

### 4.3 Bundled pose templates

- Vendor **one or two** of EchoMimic v2's sample pose sequences into
  `ml_models/assets/pose/<name>/`.
- A config setting `ECHOMIMIC_POSE` selects the default template.

### 4.4 Half-body reference at avatar creation

- Current avatar creation stores a 512×512 **face crop** (`face.png`). Keep it.
- **Add** `reference_halfbody.png`: a good frontal half-body frame selected from
  the upload. Implementation: extend the existing face-selection step to also
  emit a wider half-body crop (or the full frame) of the chosen good frame.
- New path helper `avatar_halfbody_path(avatar_id)`
  (`avatars/{id}/reference_halfbody.png`).
- The face crop continues to feed the LivePortrait path; the half-body frame
  feeds EchoMimic. Avatar creation must not fail if half-body extraction
  degrades — fall back to the full chosen frame.

### 4.5 Engine selection flag

- New config setting `GENERATION_ENGINE: "liveportrait" | "echomimic"`
  (default `liveportrait`).
- The generation orchestrator branches on it:
  - `liveportrait` → existing `animate()` + `lipsync()`.
  - `echomimic` → F5-TTS `synthesize_speech()` then a new
    `generate_video()` that calls `echomimic_generate.py`.
- On the `echomimic-v2-backend` branch the default is `echomimic`. Built as a
  flag (not a hard fork) so it stays mergeable.

## 5. Backend interface

Add to the generation `RealBackend` (and a `StubBackend` counterpart for tests):

```python
def generate_video(
    self, reference_image: Path, audio: Path, out_video: Path,
    *, pose_dir: Path, steps: int, width: int, height: int
) -> dict: ...
```

- **RealBackend**: shells into `envEM` via `run_in_env`, parses the JSON result.
- **StubBackend**: ffmpeg-only — produces a valid placeholder MP4 (still image +
  audio muxed to the right duration) so the pipeline, state machine, and tests
  run GPU-free, consistent with the existing stub philosophy.

## 6. Data flow (echomimic engine)

```
script text ─► F5-TTS (envF5) ─► speech.wav
                                     │
avatar reference_halfbody.png ───────┤
bundled pose template dir ───────────┤
                                     ▼
                          EchoMimic v2 (envEM)
                                     │
                                     ▼
                               output.mp4  (half-body, gestures, lip-synced)
```

## 7. Error handling

- **CUDA OOM** → runner exits non-zero with a clear "needs more VRAM / lower
  resolution" message; backend raises a `PipelineError` surfaced to the UI.
- **Missing half-body reference** (old avatars created before this feature) →
  `PipelineError` instructing the user to re-create the avatar, or fall back to
  the face crop with a logged warning (face crop will not show hands).
- **Env not built** (`envEM` absent) → `is_available()`-style guard;
  generation reports the engine is unavailable.
- **Pose/audio length mismatch** → runner loops/truncates the pose template;
  never a hard failure.

## 8. Testing

- Unit/integration tests run with `PIPELINE_BACKEND=stub` and
  `GENERATION_ENGINE=echomimic`, asserting the stub `generate_video()` produces a
  valid MP4 and the orchestrator routes to it.
- Existing LivePortrait+MuseTalk tests stay green (default engine unchanged).
- Real-path validation is manual on Kaggle (no local GPU), same as Phase 0/1.

## 9. Kaggle notebook

- Add an optional **cell 5b**: `setup_env_em.sh` (build `envEM` + EchoMimic
  weights).
- `GENERATION_ENGINE=echomimic` set in the launch cell's `srv_env` on this branch.
- `snapshot_envs.sh` already tars all of `${AI_ROOT}` → `envEM` + weights are
  captured automatically; no snapshot change needed (verify the EM weights path
  is under `${AI_ROOT}` or add it to the tar include list).

## 10. Open verification items (resolve during implementation)

- Confirm EchoMimic v2's **exact pinned torch/CUDA + Python** and whether it
  installs cleanly under micromamba on Kaggle (highest-risk install, like MuseTalk).
- Confirm the **inference entry point / CLI** and required input formats
  (reference image size, pose template directory structure, audio sample rate).
- Confirm **HuggingFace weight repo id + file layout** for the `WEIGHTS_SRC` cache.
- Confirm whether EchoMimic v2 weight download lands under `${AI_ROOT}` (for
  snapshot) or in `~/.cache/huggingface` (already in the snapshot include list).

### Resolved (during planning, from antgroup/echomimic_v2)

- **Env:** Python 3.10, `torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1
  xformers==0.0.28.post3` (cu121), `requirements.txt`, `facenet_pytorch==2.6.0 --no-deps`.
  `setup_env_em.sh` re-pins both torch AND xformers after `requirements.txt` to guard
  against a transitive bump (the Kaggle-dependency-stability concern).
- **Inference CLI:** `python infer.py --config ./configs/prompts/infer.yaml` with args
  `-W -H -L --steps --cfg --fps --ref_images_dir --refimg_name --audio_dir --audio_name
  --pose_dir --pose_name`. Pose templates are numbered `.npy` files under
  `assets/halfbody_demo/pose/<name>/`; output MP4 lands under `outputs/`. The runner
  `echomimic_generate.py` stages our inputs into that layout and copies the result out.
- **Weights:** `BadToBest/EchoMimicV2` → `pretrained_weights/` (denoising_unet.pth,
  reference_unet.pth, motion_module.pth, pose_encoder.pth, sd-vae-ft-mse/,
  audio_processor/tiny.pt); plus sd-image-variations-diffusers + wav2vec2-base-960h
  (fetched only if missing). Weights live under `${AI_ROOT}/EchoMimicV2`, so the
  existing `snapshot_envs.sh` (which tars all of `${AI_ROOT}`) captures them.
- **Output length is bounded by the pose template.** The runner palindrome-loops the
  pose `.npy` sequence to cover the audio length (mirrors the LivePortrait boomerang),
  so gestures repeat for long scripts rather than truncating.
- **Engine selection:** `GENERATION_ENGINE` (config) chosen as `ECHOMIMIC_POSE` →
  renamed `ECHOMIMIC_POSE_NAME`; pose templates are used in-place from the cloned repo
  (not vendored into this repo).
