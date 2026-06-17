# Real ML Pipeline — Design (F5-TTS + LivePortrait + MuseTalk)

**Date:** 2026-06-17
**Status:** Approved for Phase 0
**Author:** Yashvant203 + Claude

## 1. Goal

Replace the AI Avatar platform's scaffolded-but-non-functional "real" ML backend
with a working pipeline that produces a **full animated talking head**:

- **Voice:** the user's voice cloned from their training video (F5-TTS)
- **Motion:** natural head movement + expression on the user's face (LivePortrait)
- **Lip-sync:** the mouth driven by the synthesized speech (MuseTalk)

Target runtime environment: **free Kaggle GPU notebooks** (T4×2 / P100, 16 GB,
9-hour ephemeral sessions). All testing happens remotely on Kaggle; there is no
local GPU.

## 2. Background: why the current "real" backend doesn't work

The repo ships a dual-mode backend (`stub` works end-to-end; `real` is
scaffolding). The `real` path is unfinished and wrong in three ways:

1. **Missing libraries.** `f5_tts`, `insightface`, `liveportrait`, and `musetalk`
   are never installed; `download_models.py` fetches only *weights*.
2. **Wrong APIs.** The code calls methods that don't exist, e.g.
   `F5TTS().encode_reference(...)` (no such method — confirmed).
3. **Unimplemented stages.** `get_liveportrait()`, generation `animate()`, and
   `lipsync()` all `raise NotImplementedError`.

Every real method is marked `# pragma: no cover - requires ML stack` — i.e. never
executed.

## 3. The dominant constraint: the three models cannot share one environment

Verified from each project's official repo (see §7 for full API facts):

| Model | Python | Torch / CUDA | Install | Notes |
|---|---|---|---|---|
| F5-TTS | 3.10+ | flexible | `pip install f5-tts` | use `--no-deps` on Kaggle |
| LivePortrait | 3.10 | **torch 2.3.0 / cu121** | git clone + requirements.txt | bundles insightface |
| MuseTalk | **3.10 only** | **torch 2.0.1 / cu118** | git clone + `mim` mmcv stack | no wheels on 3.11/3.12 |

LivePortrait needs torch **2.3**; MuseTalk hard-requires torch **2.0.1** + the
brittle `mmcv 2.0.1 / mmdet 3.1.0 / mmpose 1.1.0` stack on **Python 3.10**.
Kaggle's current default session is **Python 3.12**, where MuseTalk's mmcv has no
prebuilt wheels and will not compile.

**Therefore a single-process `RealBackend` importing all three is impossible.**

## 4. Architecture: isolated environments + subprocess orchestration

Each model runs in its own environment with its own pinned torch, invoked as a
**subprocess via the maintainers' official CLI** (the tested path; avoids fragile
internal Python APIs). The application orchestrates by passing files between them.

Two isolated environments (collapsing F5-TTS into the LivePortrait env since
F5-TTS is torch-flexible):

- **env-A** — Python 3.10, torch 2.3.0/cu121: **F5-TTS + LivePortrait** (+ insightface)
- **env-B** — Python 3.10, torch 2.0.1/cu118: **MuseTalk** (+ mmcv/mmdet/mmpose)

The FastAPI worker runs in Kaggle's base env and imports **no ML libraries** — it
only shells out to env-A / env-B runner scripts and moves files.

### Generation data flow

```
GENERATE: avatar_id + script text
  │
  ├─[env-A: F5-TTS]      reference.wav + transcript + script   ──► speech.wav (24kHz mono)
  ├─[env-A: LivePortrait] face.png + idle_motion.pkl (looped to speech len) ──► animated.mp4 (silent, 25fps)
  └─[env-B: MuseTalk]    animated.mp4 (25fps) + speech.wav (16kHz) ──► lipsynced.mp4
                                                                  ──► mux audio ──► output.mp4
```

### Avatar-creation data flow

```
CREATE: training video (2–5 min) + script
  ├─ ffmpeg            ──► source_audio.wav
  ├─ select reference ──► reference.wav (~10s clean mono) + transcript   (F5-TTS input)
  ├─ insightface       ──► face.png (512×512 best frontal crop) + thumbnail.png
  └─ assemble          ──► profile.json ; Avatar.status = ready
```

LivePortrait/MuseTalk are NOT invoked during avatar creation — only at generate
time. Avatar creation just produces the reusable **reference.wav + transcript +
face.png**.

## 5. Data model / storage

An avatar is **DB rows + files**, unchanged in shape but simplified in content.

**Database** (unchanged tables): `Avatar`, `TrainingVideo`, `VoiceModel`,
`TrainingScript`, `GenerationJob`, `GeneratedVideo`.

**Files** under `storage/` (gitignored), keyed by id:

```
storage/uploads/{avatar_id}/   raw training clip
storage/voices/{avatar_id}/    source_audio.wav, reference.wav, transcript.txt
storage/avatars/{avatar_id}/   face.png, thumbnail.png, profile.json
storage/outputs/{job_id}/      output.mp4
ml_models/shared/idle_motion.pkl   ONE shared LivePortrait driving template (global)
```

Changes from the original design:

- **Drop `voice_model.pt`.** F5-TTS is in-context: the voice artifact is
  `reference.wav` + `transcript.txt`, fed to `infer()` each generation.
- **Drop per-avatar `motion_template.pkl`.** LivePortrait caches *driving* motion,
  not source appearance, so the reusable artifact is one global `idle_motion.pkl`;
  per-avatar we store only `face.png`.

A "ready" avatar = `Avatar` row + `face.png` + `reference.wav` + `transcript.txt`
+ `profile.json`.

## 6. Phase 0 — the proof notebook (first and only current deliverable)

A standalone Kaggle notebook (`ml_models/proof_pipeline.ipynb`), **no app code**,
that proves the environments and model APIs end-to-end before any backend changes.

**Inputs** — small sample assets committed under `ml_models/sample_assets/` (a few
MB, reproducible across sessions): one face photo, one ~10s reference wav + its
transcript, one short idle-head driving clip, one test sentence string.

**Cells:**

1. **env-A setup** — create a py3.10 **conda** env (conda is preinstalled on
   Kaggle; it is the path both repos document), install torch
   2.3.0/cu121, clone LivePortrait + `pip install -r requirements.txt`,
   `pip install f5-tts --no-deps` (+ its deps), download LivePortrait weights
   (`huggingface-cli download KwaiVGI/LivePortrait`) and let F5-TTS auto-download.
2. **env-B setup** — create a py3.10 conda env, install torch 2.0.1/cu118, clone MuseTalk,
   `mim install` mmcv 2.0.1 / mmdet 3.1.0 / mmpose 1.1.0 (in that order, torch
   first), run `download_weights.sh` with `HF_ENDPOINT=https://huggingface.co`.
3. **F5-TTS** — in env-A, `F5TTS().infer(ref_file, ref_text, gen_text)` → `speech.wav`.
4. **Idle motion** — in env-A, run LivePortrait once on the idle driving clip to
   emit `idle_motion.pkl`.
5. **LivePortrait** — in env-A, `inference.py -s face.png -d idle_motion.pkl -o out/`
   (driving looped/trimmed to speech length) → `animated.mp4`, resampled to 25fps.
6. **MuseTalk** — in env-B, write a job yaml (`video_path: animated.mp4`,
   `audio_path: speech_16k.wav`), run `python -m scripts.inference --version v15 ...`
   → `lipsynced.mp4`.
7. **Mux + inspect** — mux `speech.wav` onto `lipsynced.mp4` → `output.mp4`; display.

**Success criterion:** `output.mp4` shows the face speaking the test sentence in the
cloned voice with plausible head motion and lip-sync. Weights then cached to a
Kaggle Dataset so reruns skip downloads.

**Exit:** once proven, Phase 1 wraps these exact commands into per-env runner
scripts and rewires the backend `RealBackend` to call them via subprocess.

## 7. Verified model facts (code against these, not the scaffolding)

### F5-TTS (`f5-tts` 1.1.x, repo SWivid/F5-TTS)
- Install: `pip install f5-tts` (on Kaggle use `--no-deps` then install deps to
  avoid clobbering the platform torch).
- API: `from f5_tts.api import F5TTS`; `F5TTS(model="F5TTS_v1_Base", device="cuda")`.
- `infer(ref_file, ref_text, gen_text, nfe_step=32, speed=1.0, seed=None,
  remove_silence=False, file_wave=None, ...) -> (wav, sr, spec)`; `sr == 24000`.
- **No `encode_reference`.** Pass `ref_file` + `ref_text` every call. Reference
  audio auto-resampled; **hard-capped at 12s** → use a clean 5–10s reference.
- Weights: HF `SWivid/F5-TTS`, auto-downloaded to HF cache (set `HF_HOME` to a
  persistent path on Kaggle).

### LivePortrait (repo KwaiVGI/LivePortrait)
- Not pip-installable: `git clone` + `pip install -r requirements.txt`; weights via
  `huggingface-cli download KwaiVGI/LivePortrait --local-dir pretrained_weights`.
- CLI: `python inference.py -s <source img> -d <driving mp4 or .pkl> -o <out dir>`.
- **Motion-only, no audio mode.** Driving is a video OR a cached `.pkl` motion
  template (auto-written next to the driving video on first run). Reuse the `.pkl`
  to skip motion re-extraction → our shared `idle_motion.pkl`.
- ffmpeg required (script aborts without it). Skip animals/X-Pose mode (build fails
  on Kaggle; not needed for human heads).

### MuseTalk v1.5 (repo TMElyralab/MuseTalk)
- Not pip-installable: `git clone` + `requirements.txt` + `mim install mmengine /
  mmcv==2.0.1 / mmdet==3.1.0 / mmpose==1.1.0`. **Torch 2.0.1/cu118, Python 3.10.**
  Install order: torch FIRST, then mmcv via `mim`.
- Weights via `download_weights.sh` (override `HF_ENDPOINT=https://huggingface.co`
  on Kaggle; the `gdown` face-parse step is fragile — keep a mirror).
- CLI: `python -m scripts.inference --inference_config <job.yaml> --result_dir <dir>
  --unet_model_path models/musetalkV15/unet.pth --unet_config models/musetalkV15/musetalk.json
  --version v15 --fps 25 --ffmpeg_path /usr/bin`.
- The job **YAML** carries `video_path` + `audio_path` (not CLI flags) — generate it
  per job. Input video should be **25fps**; audio is resampled to 16kHz mono.
- Runs DWPose face detection **per frame** → every frame must contain a detectable
  face (fine for our animated head).

## 8. Later phases (out of scope for this spec, listed for context)

- **Phase 1:** per-env runner scripts (`ml_models/runners/{f5_tts,liveportrait,musetalk}.py`)
  + rewrite backend `RealBackend` (avatar + generation) to call them via subprocess;
  drop `encode_reference`/`voice_model.pt`; collapse the per-avatar motion stage.
- **Phase 2:** Kaggle setup automation (build both envs + cache weights to a Dataset),
  updated `kaggle_runner.ipynb`, env-health checks.
- **Phase 3:** quality tuning (reference selection, idle motion naturalness, MuseTalk
  `bbox_shift`/parsing params), error mapping to the existing `PipelineError` codes.

Each later phase gets its own spec + plan.

## 9. Risks & open questions

- **MuseTalk mmcv install** is the highest-risk step; Phase 0 isolates it first.
- **Kaggle Python version:** sessions default to 3.12; we create explicit py3.10
  conda envs. Confirm conda env activation works cleanly from notebook cells in
  Phase 0 (may need `conda run -n <env> <cmd>` rather than `conda activate`).
- **9-hour sessions + ephemeral storage:** mandatory weight caching to a Kaggle
  Dataset; otherwise every session re-downloads ~10+ GB.
- **VRAM:** three models loaded sequentially (not simultaneously) on a 16 GB T4
  should fit; confirm in Phase 0. Use `--use_float16` for MuseTalk.
- **Driving clip length vs speech length:** loop/trim `idle_motion` to match speech
  duration; confirm LivePortrait handles a looped driving cleanly.
