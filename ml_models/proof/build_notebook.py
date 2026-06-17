#!/usr/bin/env python3
"""Generate proof_pipeline.ipynb using only the standard library (no nbformat
dependency), so it runs in any environment. Run: python build_notebook.py

Heavy installs go under /tmp/aiavatar (big uncapped disk); only the final
output.mp4 is written to /kaggle/working (the ~20GB-capped output dir)."""
import json

cells = []  # list of (cell_type, source) tuples


def md(text):
    cells.append(("markdown", text))


def code(text):
    cells.append(("code", text))


REPO = "/kaggle/working/Ai-Avatar"
PROOF = REPO + "/ml_models/proof"
WORK = "/tmp/aiavatar"  # big disk; envs + weights + intermediates live here

md("# Phase 0 — Real ML pipeline proof\n"
   "F5-TTS → LivePortrait → MuseTalk in three isolated micromamba envs, producing "
   "one talking-head MP4.\n\n"
   "Heavy stuff installs under `/tmp/aiavatar` (big disk). Only `output.mp4` lands "
   "in `/kaggle/working`.\n\n"
   "**Settings → Accelerator: GPU T4 x2, Internet: ON.** Run cells top to bottom.")

code("# 1. Clone (or update) the repo to get the proof scripts.\n"
     "import os, subprocess\n"
     "os.chdir('/kaggle/working')\n"
     "if os.path.exists('Ai-Avatar'):\n"
     "    subprocess.run(['git','-C','Ai-Avatar','pull','--ff-only'], check=False)\n"
     "else:\n"
     "    subprocess.run(['git','clone','https://github.com/Yashvant203/Ai-Avatar.git'], check=True)\n"
     "print('repo ready')")

code("# 2. Build envF5 (F5-TTS). ~8-12 min.\n"
     f"!bash {PROOF}/setup_env_f5.sh {WORK}")

code("# 3. Build envLP (LivePortrait). ~8-12 min.\n"
     f"!bash {PROOF}/setup_env_lp.sh {WORK}")

code("# 4. Build envMT (MuseTalk + mmcv). ~15-25 min. The riskiest install.\n"
     f"!bash {PROOF}/setup_env_mt.sh {WORK}")

code("# 5. F5-TTS: clone a voice from F5's bundled reference, synthesize a test line.\n"
     "import subprocess\n"
     f"M = ['bash','{PROOF}/mrun.sh','envF5']\n"
     "REF = subprocess.check_output(M + ['python','-c',\n"
     "    \"from importlib.resources import files; print(files('f5_tts').joinpath('infer/examples/basic/basic_ref_en.wav'))\"]).decode().strip()\n"
     f"subprocess.run(M + ['python','{PROOF}/run_f5tts.py','--ref',REF,'--ref-text','',\n"
     "    '--gen-text','Hello, this is a test of my cloned voice on a free GPU.',\n"
     f"    '--out','{WORK}/speech.wav'], check=True)\n"
     "print('speech.wav written')")

code("# 6. Loop the driving clip to the speech length, then animate with LivePortrait.\n"
     "import subprocess\n"
     f"dur = float(subprocess.check_output(['ffprobe','-v','error','-show_entries',\n"
     "    'format=duration','-of','default=noprint_wrappers=1:nokey=1',\n"
     f"    '{WORK}/speech.wav']).decode().strip())\n"
     "print('speech duration', round(dur,2), 's')\n"
     f"drv_src = '{WORK}/LivePortrait/assets/examples/driving/d0.mp4'\n"
     f"subprocess.run(['ffmpeg','-y','-stream_loop','-1','-i',drv_src,'-t',f'{{dur:.2f}}',\n"
     f"    '-r','25','{WORK}/driving_loop.mp4'], check=True)\n"
     f"subprocess.run(['bash','{PROOF}/run_liveportrait.sh',\n"
     f"    '{WORK}/LivePortrait/assets/examples/source/s9.jpg',\n"
     f"    '{WORK}/driving_loop.mp4','{WORK}/lp_out','{WORK}'], check=True)\n"
     f"import glob; animated = sorted(glob.glob('{WORK}/lp_out/*.mp4'))[-1]; print('animated:', animated)")

code("# 7. Normalize to MuseTalk inputs: 25fps video + 16kHz mono audio.\n"
     "import glob, subprocess\n"
     f"animated = sorted(glob.glob('{WORK}/lp_out/*.mp4'))[-1]\n"
     f"subprocess.run(['ffmpeg','-y','-i',animated,'-r','25','{WORK}/animated_25.mp4'], check=True)\n"
     f"subprocess.run(['ffmpeg','-y','-i','{WORK}/speech.wav','-ar','16000','-ac','1','{WORK}/speech_16k.wav'], check=True)\n"
     "print('normalized inputs ready')")

code("# 8. MuseTalk lip-sync (envMT), from the MuseTalk repo root.\n"
     "import subprocess\n"
     f"subprocess.run(['bash','{PROOF}/mrun.sh','envMT','python',\n"
     f"    '{PROOF}/run_musetalk.py',\n"
     f"    '--video','{WORK}/animated_25.mp4',\n"
     f"    '--audio','{WORK}/speech_16k.wav',\n"
     f"    '--result-dir','{WORK}/mt_out'], cwd='{WORK}/MuseTalk', check=True)\n"
     f"import glob; print('musetalk out:', glob.glob('{WORK}/mt_out/**/*.mp4', recursive=True))")

code("# 9. Mux cloned speech onto the lip-synced video → /kaggle/working/output.mp4.\n"
     "import glob, subprocess\n"
     f"lip = glob.glob('{WORK}/mt_out/**/*.mp4', recursive=True)[-1]\n"
     f"subprocess.run(['ffmpeg','-y','-i',lip,'-i','{WORK}/speech.wav',\n"
     "    '-c:v','copy','-c:a','aac','-shortest','/kaggle/working/output.mp4'], check=True)\n"
     "from IPython.display import Video; Video('/kaggle/working/output.mp4', embed=True, width=512)")

md("## Done\n"
   "If `output.mp4` shows the face speaking with plausible motion + lip-sync, the "
   "stack is proven.\n\n"
   "### Use your own face + voice\n"
   "In cell 5 set `--ref` to a ~10s clean wav of you (and `--ref-text` to its "
   "transcript); in cell 6 set the source image to your face photo.\n\n"
   "### Cache weights\n"
   "Save `/tmp/aiavatar/LivePortrait/pretrained_weights`, `/tmp/aiavatar/MuseTalk/models`, "
   "and the F5-TTS HF cache as a Kaggle Dataset, then mount it next session and skip "
   "the download steps.")


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

with open("ml_models/proof/proof_pipeline.ipynb", "w") as fh:
    json.dump(nb, fh, indent=1)
print(f"wrote ml_models/proof/proof_pipeline.ipynb ({len(nb['cells'])} cells)")
