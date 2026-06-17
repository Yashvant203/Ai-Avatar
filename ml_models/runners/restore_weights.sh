#!/usr/bin/env bash
# Restore cached model weights from the mounted `ai-avatar-weights` Kaggle dataset
# into AI_ROOT, so the env setup scripts skip the (flaky) downloads.
#
# Usage: bash restore_weights.sh [DATASET_DIR] [ROOT]
#
# NOTE: confirm the dataset layout first with:
#   find /kaggle/input/ai-avatar-weights -maxdepth 2
# The dataset stored each folder either as a zip (--dir-mode zip) or as a plain
# directory; this script handles both (zip first, plain-dir copy as fallback).
set -euo pipefail

SRC="${1:-/kaggle/input/ai-avatar-weights/aa_cache}"
ROOT="${2:-/tmp/aiavatar}"

mkdir -p "$ROOT/LivePortrait" "$ROOT/MuseTalk" /root/.cache

echo "[restore] source=$SRC root=$ROOT"

# LivePortrait pretrained_weights
if [ -f "$SRC/lp_weights.zip" ]; then
  unzip -q -o "$SRC/lp_weights.zip" -d "$ROOT/LivePortrait/"
elif [ -d "$SRC/lp_weights" ]; then
  cp -r "$SRC/lp_weights" "$ROOT/LivePortrait/pretrained_weights"
else
  echo "[restore] WARN: no LivePortrait weights found at $SRC (lp_weights[.zip])"
fi

# MuseTalk models
if [ -f "$SRC/mt_models.zip" ]; then
  unzip -q -o "$SRC/mt_models.zip" -d "$ROOT/MuseTalk/"
elif [ -d "$SRC/mt_models" ]; then
  cp -r "$SRC/mt_models" "$ROOT/MuseTalk/models"
else
  echo "[restore] WARN: no MuseTalk models found at $SRC (mt_models[.zip])"
fi

# HuggingFace cache (F5-TTS + any whisper/vocoder weights)
if [ -f "$SRC/hf_cache.zip" ]; then
  unzip -q -o "$SRC/hf_cache.zip" -d /root/.cache/
elif [ -d "$SRC/hf_cache" ]; then
  cp -r "$SRC/hf_cache" /root/.cache/huggingface
else
  echo "[restore] WARN: no HF cache found at $SRC (hf_cache[.zip])"
fi

echo "[restore] weights restored from $SRC"
