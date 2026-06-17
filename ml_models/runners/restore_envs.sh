#!/usr/bin/env bash
# Restore a previously snapshotted env tarball (from the ai-avatar-envs dataset)
# into the SAME paths it was built at, so this session skips the env build entirely.
#
# Usage: bash restore_envs.sh [TGZ]
#   TGZ defaults to auto-discovery under /kaggle/input/**/aiavatar_envs.tgz
# After this, skip the setup_env_* steps and go straight to install + launch.
set -euo pipefail

TGZ="${1:-}"
if [ -z "$TGZ" ]; then
  TGZ="$(find /kaggle/input -name 'aiavatar_envs.tgz' 2>/dev/null | head -n1)"
fi
if [ -z "$TGZ" ] || [ ! -f "$TGZ" ]; then
  echo "[restore] ERROR: aiavatar_envs.tgz not found. Add the 'ai-avatar-envs' dataset." >&2
  exit 1
fi

echo "[restore] extracting $TGZ -> / (a few minutes)…"
tar -C / -xzf "$TGZ"

echo "[restore] envs present:"
ls "/tmp/aiavatar/mamba/envs" 2>/dev/null || { echo "[restore] ERROR: envs missing after extract" >&2; exit 1; }
echo "[restore] done — skip setup_env_*; go to backend install + launch."
