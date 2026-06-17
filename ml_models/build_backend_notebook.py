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
    "**Add Data → `ai-avatar-weights`** (mounted at `/kaggle/input/ai-avatar-weights`).\n\n"
    "Run cells top to bottom. Env builds take ~30-50 min the first time."
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
    "# 2. Inspect the mounted weights dataset, then restore into /tmp/aiavatar.\n"
    "# Confirm the layout matches restore_weights.sh; adjust SRC if the dataset nests differently.\n"
    "import subprocess\n"
    f"subprocess.run(['find','{DATASET}','-maxdepth','2'], check=False)\n"
    f"subprocess.run(['bash','{RUNNERS}/restore_weights.sh','{DATASET}/aa_cache','{WORK}'], check=False)"
)

code(
    "# 3. Build envF5 (F5-TTS). Weights restored above, but pip still installs. ~8-12 min.\n"
    f"!bash {RUNNERS}/setup_env_f5.sh {WORK}"
)
code(
    "# 4. Build envLP (LivePortrait + insightface). ~8-12 min.\n"
    f"!bash {RUNNERS}/setup_env_lp.sh {WORK}"
)
code(
    "# 5. Build envMT (MuseTalk + mmcv). The riskiest install. ~15-25 min.\n"
    f"!bash {RUNNERS}/setup_env_mt.sh {WORK}"
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
    "(env var) if the mouth needs alignment. Keep this kernel running while you use the site."
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
