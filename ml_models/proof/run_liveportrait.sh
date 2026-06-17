#!/usr/bin/env bash
# LivePortrait animate: source face + driving video -> animated mp4 (runs in env-A).
# Usage: bash run_liveportrait.sh SOURCE_IMG DRIVING_MP4 OUT_DIR [ROOT]
set -euo pipefail

SRC="$1"
DRV="$2"
OUTDIR="$3"
ROOT="${4:-/kaggle/working}"

mkdir -p "$OUTDIR"
cd "$ROOT/LivePortrait"

echo "[lp] animating $SRC with driving $DRV → $OUTDIR"
conda run -n envA python inference.py -s "$SRC" -d "$DRV" -o "$OUTDIR"

echo "[lp] outputs in $OUTDIR:"
ls -1 "$OUTDIR"/*.mp4
