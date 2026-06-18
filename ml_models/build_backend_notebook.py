#!/usr/bin/env python3
"""Generate ml_models/backend_server.ipynb with only the standard library (no
nbformat dependency), mirroring the Phase 0 builder. Run: python build_backend_notebook.py

The notebook runs the REAL backend on Kaggle: restore cached weights → build the
three micromamba envs → install + migrate the FastAPI backend → launch worker +
uvicorn (PIPELINE_BACKEND=real) → expose a public URL with cloudflared. Point the
website's NEXT_PUBLIC_API_BASE_URL at that URL.

Heavy state (envs, weights, storage) lives under /tmp/aiavatar (big uncapped disk);
/kaggle/working (~20 GB cap) holds only the cloned repo.
"""
import json

cells = []  # (cell_type, source)


def md(text):
    cells.append(("markdown", text))


def code(text):
    cells.append(("code", text))


REPO = "/kaggle/working/Ai-Avatar"
RUNNERS = REPO + "/ml_models/runners"
BACKEND = REPO + "/backend"
WORK = "/tmp/aiavatar"  # big disk: envs + weights + storage + sqlite
STORAGE = WORK + "/storage"
DATASET = "/kaggle/input/ai-avatar-weights"

md(
    "# Phase 1 — Real backend server (Kaggle)\n"
    "Serves the **real** F5-TTS / LivePortrait / MuseTalk pipeline behind the FastAPI "
    "backend, exposed via a public cloudflared URL the website can call.\n\n"
    "**Settings → Accelerator: GPU T4 x2, Internet: ON.** "
    "**Add Data → `ai-avatar-weights`** (mounted under `/kaggle/input/…`; cell 2 finds it).\n\n"
    "Run cells top to bottom. With the cached weights dataset the env builds are mostly "
    "pip installs (~20-35 min); without it they also download weights (~slower, flakier)."
)

code(
    "# 1. Clone (or update) the repo.\n"
    "import os, subprocess\n"
    "os.chdir('/kaggle/working')\n"
    "if os.path.exists('Ai-Avatar'):\n"
    "    subprocess.run(['git','-C','Ai-Avatar','pull','--ff-only'], check=False)\n"
    "else:\n"
    "    subprocess.run(['git','clone','https://github.com/Yashvant203/Ai-Avatar.git'], check=True)\n"
    "print('repo ready')"
)

code(
    "# 2. Auto-locate the cached weights dataset and export WEIGHTS_SRC.\n"
    "#    The env-setup cells below inherit os.environ, so they pick this up and use\n"
    "#    the cache (lp_weights/mt_models/hf_cache) instead of re-downloading.\n"
    "#    Kaggle mounts datasets at varying paths, so we search rather than hardcode.\n"
    "import glob, os, subprocess\n"
    "hits = glob.glob('/kaggle/input/**/lp_weights', recursive=True)\n"
    "WEIGHTS_SRC = os.path.dirname(hits[0]) if hits else ''\n"
    "if WEIGHTS_SRC:\n"
    "    os.environ['WEIGHTS_SRC'] = WEIGHTS_SRC\n"
    "    print('WEIGHTS_SRC =', WEIGHTS_SRC)\n"
    "    subprocess.run(['ls','-la',WEIGHTS_SRC])\n"
    "else:\n"
    "    print('No cached weights found under /kaggle/input — env setup will DOWNLOAD weights.')\n"
    "    print('If you added the ai-avatar-weights dataset, check: !ls -R /kaggle/input | head')"
)

md(
    "### Fast path (optional): restore prebuilt envs\n"
    "If you saved an **`ai-avatar-envs`** snapshot in a previous session, add that dataset "
    "and run the cell below to restore the envs in ~3-5 min — then **SKIP cells 3-5** and go "
    "straight to cell 6. (First time through, skip this and build the envs normally.)"
)
code(
    "# Optional FAST PATH: restore prebuilt envs, then skip the three setup_env cells.\n"
    f"!bash {RUNNERS}/restore_envs.sh"
)

code(
    "# 3. Build envF5 (F5-TTS). Uses WEIGHTS_SRC/hf_cache if set; pip still installs. ~8-12 min.\n"
    f"!bash {RUNNERS}/setup_env_f5.sh {WORK}"
)
code(
    "# 4. (OPTIONAL — LivePortrait engine only) Build envLP (LivePortrait + insightface).\n"
    "#     SKIP for the EchoMimic-only setup: launch with USE_INSIGHTFACE=false (cell 7)\n"
    "#     so avatar creation picks the face frame with ffmpeg instead of insightface.\n"
    f"!bash {RUNNERS}/setup_env_lp.sh {WORK}"
)
code(
    "# 5. (OPTIONAL — LivePortrait engine only) Build envMT (MuseTalk + mmcv).\n"
    "#     SKIP for the EchoMimic-only setup (EchoMimic does its own lip-sync).\n"
    f"!bash {RUNNERS}/setup_env_mt.sh {WORK}"
)
code(
    "# 5b. Build envEM (EchoMimic v2 — half-body + hand gestures). Heavy; ~25-40 min,\n"
    "#     and inference is SLOW on a T4. Only needed for the EchoMimic comparison.\n"
    f"!bash {RUNNERS}/setup_env_em.sh {WORK}"
)

md(
    "### Save a snapshot (run ONCE, after the envs finish building)\n"
    "Creates `aiavatar_envs.tgz`. Then: **Output panel -> aiavatar_envs.tgz -> New Dataset** "
    "(name it `ai-avatar-envs`). Next session, add that dataset and use the restore cell above "
    "to skip the ~25-min build. Skip this cell on restored/fast-path runs."
)
code(
    "# Optional: snapshot the built envs to a tarball for reuse next session.\n"
    f"!bash {RUNNERS}/snapshot_envs.sh"
)

code(
    "# 6. Install the FastAPI backend into the base env + run DB migrations.\n"
    "import os, subprocess\n"
    f"os.makedirs('{STORAGE}', exist_ok=True)\n"
    f"subprocess.run(['pip','install','-e','{BACKEND}'], check=True)\n"
    f"subprocess.run(['alembic','upgrade','head'], cwd='{BACKEND}', check=True)\n"
    "print('backend installed + migrated')"
)

code(
    "# 7. Launch the worker + API (PIPELINE_BACKEND=real), both with cwd=backend.\n"
    "import os, secrets, subprocess, time\n"
    "srv_env = {**os.environ,\n"
    "    'PIPELINE_BACKEND': 'real',\n"
    "    'GENERATION_ENGINE': 'echomimic',\n"
    "    'USE_INSIGHTFACE': 'false',  # EchoMimic-only: ffmpeg face selection, no envLP\n"
    "    'JWT_SECRET': secrets.token_urlsafe(48),\n"
    "    'CORS_ORIGINS': '*',\n"
    f"    'STORAGE_DIR': '{STORAGE}',\n"
    f"    'AI_ROOT': '{WORK}',\n"
    "}\n"
    f"wlog = open('{WORK}/worker.log','w'); alog = open('{WORK}/api.log','w')\n"
    "worker = subprocess.Popen(['python','-m','worker.main'],\n"
    f"    cwd='{BACKEND}', env=srv_env, stdout=wlog, stderr=subprocess.STDOUT)\n"
    "api = subprocess.Popen(['uvicorn','app.main:app','--host','0.0.0.0','--port','7860'],\n"
    f"    cwd='{BACKEND}', env=srv_env, stdout=alog, stderr=subprocess.STDOUT)\n"
    "time.sleep(8)\n"
    "import urllib.request\n"
    "try:\n"
    "    print('health:', urllib.request.urlopen('http://127.0.0.1:7860/healthcheck', timeout=5).read())\n"
    "except Exception as e:\n"
    f"    print('health check failed:', e); print(open('{WORK}/api.log').read()[-2000:])"
)

code(
    "# 8. Public URL via cloudflared. Copy the https://*.trycloudflare.com line into\n"
    "#    frontend/.env.local as NEXT_PUBLIC_API_BASE_URL, then `npm run dev`.\n"
    "import os, re, subprocess, time\n"
    "if not os.path.exists('/usr/local/bin/cloudflared'):\n"
    "    subprocess.run(['wget','-q',\n"
    "        'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64',\n"
    "        '-O','/usr/local/bin/cloudflared'], check=True)\n"
    "    subprocess.run(['chmod','+x','/usr/local/bin/cloudflared'], check=True)\n"
    f"tlog = open('{WORK}/tunnel.log','w')\n"
    "tunnel = subprocess.Popen(['cloudflared','tunnel','--no-autoupdate','--url','http://localhost:7860'],\n"
    "    stdout=tlog, stderr=subprocess.STDOUT)\n"
    "url = None\n"
    "for _ in range(30):\n"
    "    time.sleep(2)\n"
    f"    m = re.search(r'https://[-a-z0-9]+\\.trycloudflare\\.com', open('{WORK}/tunnel.log').read())\n"
    "    if m:\n"
    "        url = m.group(0); break\n"
    "print('PUBLIC API URL:', url or 'not found — check tunnel.log')"
)

md(
    "## Use it from the website\n"
    "1. `frontend/.env.local` → `NEXT_PUBLIC_API_BASE_URL=<the trycloudflare URL>`\n"
    "2. `cd frontend && npm run dev`\n"
    "3. Sign up → **Create Avatar** → upload a 20-30 s video of yourself → wait for *ready*.\n"
    "4. **Generate** → type a script → download the MP4 (your face + voice, lip-synced).\n\n"
    "Logs: `/tmp/aiavatar/{api,worker,tunnel}.log`. Tune `MUSETALK_BBOX_SHIFT` "
    "(env var) if the mouth needs alignment. Keep this kernel running while you use the site.\n\n"
    "This branch defaults to the EchoMimic v2 engine (half-body + gestures); "
    "set `GENERATION_ENGINE=liveportrait` in cell 7 to compare against the head-only path."
)


def _cell(idx, cell_type, source):
    cell = {"cell_type": cell_type, "metadata": {}, "source": source, "id": f"cell{idx}"}
    if cell_type == "code":
        cell["outputs"] = []
        cell["execution_count"] = None
    return cell


nb = {
    "cells": [_cell(i, t, s) for i, (t, s) in enumerate(cells)],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open("ml_models/backend_server.ipynb", "w") as fh:
    json.dump(nb, fh, indent=1)
print(f"wrote ml_models/backend_server.ipynb ({len(nb['cells'])} cells)")
