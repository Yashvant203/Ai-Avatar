# Phase 0 — Real ML pipeline proof (Kaggle)

Proves F5-TTS → LivePortrait → MuseTalk end-to-end in two isolated conda envs and
produces one talking-head MP4. No backend/app code — just the model stack.

## Prerequisites (Kaggle)
- New Notebook → Settings → Accelerator **GPU T4 x2**, Internet **On**.
- This repo cloned at `/kaggle/working/Ai-Avatar`.

## Run order
1. `setup_env_a.sh` — env-A (F5-TTS + LivePortrait), ~10–15 min, ~6 GB.
2. `setup_env_b.sh` — env-B (MuseTalk + mmcv), ~15–25 min, the riskiest install.
3. `run_f5tts.py`        → `speech.wav`
4. `run_liveportrait.sh` → `animated.mp4`
5. `run_musetalk.py`     → `lipsynced.mp4`
6. mux speech → `output.mp4`

The easy path: upload `proof_pipeline.ipynb` to Kaggle and Run All — it calls the
scripts above in order.

## Environments
| Env | Python | Torch | Holds |
|-----|--------|-------|-------|
| envA | 3.10 | 2.3.0 / cu121 | F5-TTS, LivePortrait, insightface |
| envB | 3.10 | 2.0.1 / cu118 | MuseTalk, mmcv 2.0.1 / mmdet 3.1.0 / mmpose 1.1.0 |

Run a script inside an env with: `conda run -n envA python ...`.

## Weight caching (avoid re-downloading every session)
After a successful run, save `/kaggle/working` model dirs as a Kaggle **Dataset**
(`LivePortrait/pretrained_weights`, `MuseTalk/models`, and `~/.cache/huggingface`),
then mount it next session and skip the download steps. See the notebook's last cell.
