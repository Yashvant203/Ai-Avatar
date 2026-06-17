#!/usr/bin/env python3
"""Generate proof_pipeline.ipynb using only the standard library (no nbformat
dependency), so it runs in any environment. Run: python build_notebook.py"""
import json

cells = []  # list of (cell_type, source) tuples


def md(text):
    cells.append(("markdown", text))


def code(text):
    cells.append(("code", text))


md("# Phase 0 — Real ML pipeline proof\n"
   "Runs F5-TTS → LivePortrait → MuseTalk in two isolated conda envs and produces "
   "one talking-head MP4.\n\n"
   "**Settings → Accelerator: GPU T4 x2, Internet: ON.** Run cells top to bottom.")

code("# 1. Clone the repo (gets the proof scripts)\n"
     "import os, subprocess\n"
     "os.chdir('/kaggle/working')\n"
     "if not os.path.exists('Ai-Avatar'):\n"
     "    subprocess.run(['git','clone','https://github.com/Yashvant203/Ai-Avatar.git'], check=True)\n"
     "print('repo ready')")

code("# 2. Build env-A (F5-TTS + LivePortrait). ~10-15 min.\n"
     "!bash /kaggle/working/Ai-Avatar/ml_models/proof/setup_env_a.sh")

code("# 3. Build env-B (MuseTalk + mmcv). ~15-25 min. The riskiest install.\n"
     "!bash /kaggle/working/Ai-Avatar/ml_models/proof/setup_env_b.sh")

code("# 4. F5-TTS: clone a voice from F5's bundled reference, synthesize a test line.\n"
     "import subprocess\n"
     "M = ['bash','Ai-Avatar/ml_models/proof/mrun.sh','envA']\n"
     "REF = subprocess.check_output(M + ['python','-c',\n"
     "    \"from importlib.resources import files; print(files('f5_tts').joinpath('infer/examples/basic/basic_ref_en.wav'))\"]).decode().strip()\n"
     "subprocess.run(M + ['python',\n"
     "    'Ai-Avatar/ml_models/proof/run_f5tts.py','--ref',REF,'--ref-text','',\n"
     "    '--gen-text','Hello, this is a test of my cloned voice on a free GPU.',\n"
     "    '--out','/kaggle/working/speech.wav'], check=True)\n"
     "print('speech.wav written')")

code("# 5. Make the driving clip match the speech length, then animate with LivePortrait.\n"
     "import subprocess\n"
     "dur = float(subprocess.check_output(['ffprobe','-v','error','-show_entries',\n"
     "    'format=duration','-of','default=noprint_wrappers=1:nokey=1',\n"
     "    '/kaggle/working/speech.wav']).decode().strip())\n"
     "print('speech duration', round(dur,2), 's')\n"
     "drv_src = '/kaggle/working/LivePortrait/assets/examples/driving/d0.mp4'\n"
     "# loop the idle driving clip to >= speech duration\n"
     "subprocess.run(['ffmpeg','-y','-stream_loop','-1','-i',drv_src,'-t',f'{dur:.2f}',\n"
     "    '-r','25','/kaggle/working/driving_loop.mp4'], check=True)\n"
     "subprocess.run(['bash','Ai-Avatar/ml_models/proof/run_liveportrait.sh',\n"
     "    '/kaggle/working/LivePortrait/assets/examples/source/s9.jpg',\n"
     "    '/kaggle/working/driving_loop.mp4','/kaggle/working/lp_out'], check=True)\n"
     "import glob; animated = sorted(glob.glob('/kaggle/working/lp_out/*.mp4'))[-1]; print('animated:', animated)")

code("# 6. Normalize to MuseTalk inputs: 25fps video + 16kHz mono audio.\n"
     "import glob, subprocess\n"
     "animated = sorted(glob.glob('/kaggle/working/lp_out/*.mp4'))[-1]\n"
     "subprocess.run(['ffmpeg','-y','-i',animated,'-r','25','/kaggle/working/animated_25.mp4'], check=True)\n"
     "subprocess.run(['ffmpeg','-y','-i','/kaggle/working/speech.wav','-ar','16000','-ac','1','/kaggle/working/speech_16k.wav'], check=True)\n"
     "print('normalized inputs ready')")

code("# 7. MuseTalk lip-sync (env-B), from the MuseTalk repo root.\n"
     "import subprocess\n"
     "subprocess.run(['bash','/kaggle/working/Ai-Avatar/ml_models/proof/mrun.sh','envB','python',\n"
     "    '/kaggle/working/Ai-Avatar/ml_models/proof/run_musetalk.py',\n"
     "    '--video','/kaggle/working/animated_25.mp4',\n"
     "    '--audio','/kaggle/working/speech_16k.wav',\n"
     "    '--result-dir','/kaggle/working/mt_out'], cwd='/kaggle/working/MuseTalk', check=True)\n"
     "import glob; print('musetalk out:', glob.glob('/kaggle/working/mt_out/**/*.mp4', recursive=True))")

code("# 8. Mux the cloned speech onto the lip-synced video → output.mp4, then display.\n"
     "import glob, subprocess\n"
     "lip = glob.glob('/kaggle/working/mt_out/**/*.mp4', recursive=True)[-1]\n"
     "subprocess.run(['ffmpeg','-y','-i',lip,'-i','/kaggle/working/speech.wav',\n"
     "    '-c:v','copy','-c:a','aac','-shortest','/kaggle/working/output.mp4'], check=True)\n"
     "from IPython.display import Video; Video('/kaggle/working/output.mp4', embed=True, width=512)")

md("## Done\n"
   "If `output.mp4` shows the face speaking with plausible motion + lip-sync, the "
   "stack is proven.\n\n"
   "### Use your own face + voice\n"
   "Replace the bundled assets: in cell 4 set `--ref` to a ~10s clean wav of you "
   "(and `--ref-text` to its transcript); in cell 5 set the source image to your "
   "face photo. Both can be extracted from your training clip with ffmpeg.\n\n"
   "### Cache weights\n"
   "Save `LivePortrait/pretrained_weights`, `MuseTalk/models`, and `~/.cache/huggingface` "
   "as a Kaggle Dataset, then mount it next session and skip cells 2–3's downloads.")


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
