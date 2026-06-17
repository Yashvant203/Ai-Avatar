# Phase 0 — Real ML pipeline proof (Kaggle)

Proves F5-TTS → LivePortrait → MuseTalk end-to-end in **three isolated micromamba
envs** and produces one talking-head MP4. No backend/app code — just the model stack.

## Prerequisites (Kaggle)
- New Notebook → Settings → Accelerator **GPU T4 x2**, Internet **On**.

## Disk
`/kaggle/working` is capped at ~20 GB, but `/tmp` is on a multi-TB disk. So heavy
installs (envs + weights, ~30–40 GB) go under **`/tmp/aiavatar`**; only the final
`output.mp4` is written to `/kaggle/working`.

## Environments
Kaggle images don't ship `conda`, so the setup scripts bootstrap **micromamba** (one
static binary at `/tmp/aiavatar/bin/micromamba`) and create the envs under
`/tmp/aiavatar/mamba`. Each model gets its own env so their torch pins can't clash.

| Env | Python | Torch | Holds |
|-----|--------|-------|-------|
| envF5 | 3.10 | (f5-tts default) | F5-TTS (plain `pip install f5-tts`) |
| envLP | 3.10 | 2.3.0 / cu121 | LivePortrait, insightface |
| envMT | 3.10 | 2.0.1 / cu118 | MuseTalk, mmcv 2.0.1 / mmdet 3.1.0 / mmpose 1.1.0 |

Run a command inside an env: `bash mrun.sh envF5 python ...`.

## Run order (the notebook does this for you)
1. `setup_env_f5.sh` — envF5 (F5-TTS), ~8–12 min.
2. `setup_env_lp.sh` — envLP (LivePortrait), ~8–12 min.
3. `setup_env_mt.sh` — envMT (MuseTalk + mmcv), ~15–25 min, the riskiest install.
4. `run_f5tts.py`        → `speech.wav`
5. `run_liveportrait.sh` → `animated.mp4`
6. `run_musetalk.py`     → lip-synced mp4
7. mux speech → `/kaggle/working/output.mp4`

The easy path: upload `proof_pipeline.ipynb` to Kaggle and **Run All**.

## Weight caching (avoid re-downloading every session)
After a successful run, save `/tmp/aiavatar/LivePortrait/pretrained_weights`,
`/tmp/aiavatar/MuseTalk/models`, and the F5-TTS HF cache as a Kaggle **Dataset**,
then mount it next session and skip the download steps.
