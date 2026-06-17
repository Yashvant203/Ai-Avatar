#!/usr/bin/env bash
# Verify ffmpeg is available; attempt install if missing. Fails loudly otherwise.
set -euo pipefail

MIN_MAJOR=4

if command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg found:"
  ffmpeg -version | head -n 1
  version_line="$(ffmpeg -version | head -n 1)"
  major="$(printf '%s\n' "$version_line" | grep -oE '[0-9]+' | head -n 1 || echo 0)"
  if [ "${major:-0}" -lt "$MIN_MAJOR" ]; then
    echo "WARNING: ffmpeg major version ${major} < ${MIN_MAJOR}. A static build is recommended." >&2
  fi
  exit 0
fi

echo "ffmpeg not found — attempting install..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y && sudo apt-get install -y ffmpeg
elif command -v conda >/dev/null 2>&1; then
  conda install -y -c conda-forge ffmpeg
else
  cat >&2 <<'EOF'
ERROR: could not install ffmpeg automatically (no apt-get or conda).
Install it manually, e.g. a static build from https://johnvansickle.com/ffmpeg/
and ensure `ffmpeg` is on PATH.
EOF
  exit 1
fi

echo "ffmpeg installed:"
ffmpeg -version | head -n 1
