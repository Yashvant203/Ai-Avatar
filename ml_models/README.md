# Model weights

This directory holds the open-source model weights the platform depends on.
**Nothing here is committed** — `download_models.py` fetches everything into
`weights/` (git-ignored). No commercial APIs are used anywhere.

## Required models

| Model        | Role                          | Default HF repo (override via env)        | Target path                  |
|--------------|-------------------------------|-------------------------------------------|------------------------------|
| F5-TTS       | Voice cloning / TTS           | `SWivid/F5-TTS`                           | `weights/f5_tts/`            |
| MuseTalk     | Lip-sync (mouth region)       | `TMElyralab/MuseTalk`                     | `weights/musetalk/`          |
| LivePortrait | Head / expression animation   | `KwaiVGI/LivePortrait`                    | `weights/liveportrait/`      |

Repo IDs can be overridden with environment variables
`F5_TTS_REPO`, `MUSETALK_REPO`, `LIVEPORTRAIT_REPO` if upstream paths change.

## Licenses — read before use

Each model carries its own license; review them before any deployment,
especially commercial use or cloning a third party's likeness/voice:

- F5-TTS, MuseTalk, LivePortrait — check the model card on Hugging Face for the
  current license and acceptable-use terms. Some weights are research-only.

The platform also requires **explicit subject consent** before cloning a face or
voice (see `docs/PRODUCT_REQUIREMENTS.md`).

## Usage

```bash
# 1. Verify / install ffmpeg
bash ml_models/setup_ffmpeg.sh

# 2. Download weights (idempotent, resumable). Set HF_TOKEN if a repo is gated.
python ml_models/download_models.py
#   or only some:  python ml_models/download_models.py --only f5_tts musetalk

# 3. Verify the full environment (GPU + ffmpeg + weights present)
python ml_models/verify_env.py
```

Downloads require the `huggingface_hub` package (installed in the GPU/runtime
environment, e.g. on Kaggle). It is intentionally *not* a backend dependency so
the API can run without the ML stack during early development.
