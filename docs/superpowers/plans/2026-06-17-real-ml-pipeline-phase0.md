# Real ML Pipeline — Phase 0 (Proof Notebook) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove F5-TTS → LivePortrait → MuseTalk runs end-to-end on free Kaggle GPU in two isolated conda environments and produces one good talking-head MP4, before touching the backend.

**Architecture:** Two isolated py3.10 conda envs (env-A: F5-TTS+LivePortrait/torch2.3-cu121; env-B: MuseTalk/torch2.0.1-cu118). Thin reusable runner scripts per stage, called from the notebook via `conda run -n <env>`. File-based handoff between stages. These scripts become the seeds of the Phase 1 backend runners.

**Tech Stack:** Kaggle Notebooks (T4 GPU), conda, bash, Python 3.10, ffmpeg, F5-TTS 1.1.x, LivePortrait (KwaiVGI), MuseTalk v1.5 (TMElyralab + mmcv 2.0.1/mmdet 3.1.0/mmpose 1.1.0), nbformat.

**Spec:** `docs/superpowers/specs/2026-06-17-real-ml-pipeline-design.md`

**Verification model:** Deliverables are GPU install/inference scripts that cannot run on this machine. Each task has a **local gate** (the author runs: `bash -n`/`ruff`/`py_compile`/nbformat validity) and a **Kaggle gate** (the user runs the cell; we confirm the named output file exists / cell succeeds). "Expected output" for Kaggle steps is observational.

**Spec deviation (intentional):** The spec said to commit sample assets under `ml_models/sample_assets/`. Instead the proof uses the **bundled example assets** that ship inside the LivePortrait and F5-TTS repos (a source face, a driving clip, a reference wav) — more reliable than fabricating media, and removes the need to commit binaries. A final notebook section documents swapping in the user's own face/voice. The spec's storage model is otherwise unchanged.

**Working directory on Kaggle:** all repos and envs live under `/kaggle/working`. Scripts accept a `ROOT` argument defaulting to `/kaggle/working`.

---

## File Structure

All new files under `ml_models/proof/`:

- `ml_models/proof/README.md` — what this is, prerequisites, run order, weight caching.
- `ml_models/proof/setup_env_a.sh` — create env-A; install torch 2.3/cu121, LivePortrait, F5-TTS, weights.
- `ml_models/proof/setup_env_b.sh` — create env-B; install torch 2.0.1/cu118, MuseTalk, mmcv stack, weights.
- `ml_models/proof/run_f5tts.py` — env-A: reference wav + text + gen text → speech.wav (24kHz).
- `ml_models/proof/run_liveportrait.sh` — env-A: source face + driving video → animated.mp4.
- `ml_models/proof/run_musetalk.py` — env-B: animated.mp4 (25fps) + speech (16kHz) → lipsynced.mp4.
- `ml_models/proof/build_notebook.py` — generates `proof_pipeline.ipynb` via nbformat (keeps JSON valid).
- `ml_models/proof/proof_pipeline.ipynb` — generated; the notebook the user uploads to Kaggle.

---

## Task 1: Scaffold `ml_models/proof/` with README

**Files:**
- Create: `ml_models/proof/README.md`

- [ ] **Step 1: Write the README**

````markdown
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
````

- [ ] **Step 2: Local gate — file exists and is non-empty**

Run: `test -s ml_models/proof/README.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ml_models/proof/README.md
git commit -m "docs(proof): add Phase 0 proof README"
```

---

## Task 2: env-A setup script (F5-TTS + LivePortrait)

**Files:**
- Create: `ml_models/proof/setup_env_a.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# env-A: Python 3.10, torch 2.3.0/cu121 — F5-TTS + LivePortrait.
# Usage: bash setup_env_a.sh [ROOT]   (ROOT defaults to /kaggle/working)
set -euo pipefail

ENV=envA
ROOT="${1:-/kaggle/working}"
cd "$ROOT"

echo "[env-A] creating conda env (python 3.10)…"
conda create -y -n "$ENV" python=3.10

echo "[env-A] installing torch 2.3.0 / cu121…"
conda run -n "$ENV" pip install --no-cache-dir \
  torch==2.3.0 torchvision==0.18.0 torchaudio==2.3.0 \
  --index-url https://download.pytorch.org/whl/cu121

echo "[env-A] cloning + installing LivePortrait…"
[ -d LivePortrait ] || git clone https://github.com/KwaiVGI/LivePortrait
conda run -n "$ENV" pip install --no-cache-dir -r LivePortrait/requirements.txt

echo "[env-A] downloading LivePortrait weights…"
conda run -n "$ENV" huggingface-cli download KwaiVGI/LivePortrait \
  --local-dir LivePortrait/pretrained_weights \
  --exclude "*.git*" "README.md" "docs"

echo "[env-A] installing F5-TTS (no-deps to protect torch) + its deps…"
conda run -n "$ENV" pip install --no-cache-dir f5-tts --no-deps
conda run -n "$ENV" pip install --no-cache-dir \
  cached_path vocos x-transformers torchdiffeq ema-pytorch \
  jieba pypinyin transformers accelerate datasets pydub soundfile librosa tomli click

echo "[env-A] verifying imports…"
conda run -n "$ENV" python -c "import torch, f5_tts; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); from f5_tts.api import F5TTS; print('f5_tts OK')"

echo "[env-A] READY"
```

- [ ] **Step 2: Local gate — bash syntax check**

Run: `bash -n ml_models/proof/setup_env_a.sh && echo SYNTAX_OK`
Expected: `SYNTAX_OK`

- [ ] **Step 3: Mark executable + commit**

```bash
chmod +x ml_models/proof/setup_env_a.sh
git add ml_models/proof/setup_env_a.sh
git commit -m "feat(proof): env-A setup (F5-TTS + LivePortrait)"
```

- [ ] **Step 4: Kaggle gate (deferred — run after notebook exists)**

Run on Kaggle: `bash /kaggle/working/Ai-Avatar/ml_models/proof/setup_env_a.sh`
Expected: ends with `[env-A] READY` and `torch 2.3.0 cuda True ... f5_tts OK`. If
torch shows `cuda False`, the cu121 wheel mismatched the driver — note and report.

---

## Task 3: env-B setup script (MuseTalk + mmcv stack)

**Files:**
- Create: `ml_models/proof/setup_env_b.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# env-B: Python 3.10, torch 2.0.1/cu118 — MuseTalk v1.5 + mmcv stack.
# Usage: bash setup_env_b.sh [ROOT]   (ROOT defaults to /kaggle/working)
# NOTE: mmcv is the highest-risk step. Order is non-negotiable: torch FIRST, then mim.
set -euo pipefail

ENV=envB
ROOT="${1:-/kaggle/working}"
cd "$ROOT"

echo "[env-B] creating conda env (python 3.10)…"
conda create -y -n "$ENV" python=3.10

echo "[env-B] installing torch 2.0.1 / cu118 (must precede mmcv)…"
conda run -n "$ENV" pip install --no-cache-dir \
  torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
  --index-url https://download.pytorch.org/whl/cu118

echo "[env-B] cloning + installing MuseTalk requirements…"
[ -d MuseTalk ] || git clone https://github.com/TMElyralab/MuseTalk
conda run -n "$ENV" pip install --no-cache-dir -r MuseTalk/requirements.txt

echo "[env-B] installing MMLab stack via mim (mmengine → mmcv → mmdet → mmpose)…"
conda run -n "$ENV" pip install --no-cache-dir -U openmim
conda run -n "$ENV" mim install mmengine
conda run -n "$ENV" mim install "mmcv==2.0.1"
conda run -n "$ENV" mim install "mmdet==3.1.0"
conda run -n "$ENV" mim install "mmpose==1.1.0"

echo "[env-B] downloading MuseTalk weights (force public HF endpoint)…"
cd "$ROOT/MuseTalk"
# download_weights.sh hardcodes the China mirror; switch it to the public endpoint.
sed -i 's#https://hf-mirror.com#https://huggingface.co#g' download_weights.sh || true
conda run -n "$ENV" bash download_weights.sh

echo "[env-B] verifying mmcv + musetalk weights…"
conda run -n "$ENV" python -c "import torch, mmcv; print('torch', torch.__version__, 'mmcv', mmcv.__version__)"
test -f "$ROOT/MuseTalk/models/musetalkV15/unet.pth" && echo "musetalk v15 weights OK"

echo "[env-B] READY"
```

- [ ] **Step 2: Local gate — bash syntax check**

Run: `bash -n ml_models/proof/setup_env_b.sh && echo SYNTAX_OK`
Expected: `SYNTAX_OK`

- [ ] **Step 3: Mark executable + commit**

```bash
chmod +x ml_models/proof/setup_env_b.sh
git add ml_models/proof/setup_env_b.sh
git commit -m "feat(proof): env-B setup (MuseTalk + mmcv stack)"
```

- [ ] **Step 4: Kaggle gate (deferred)**

Run on Kaggle: `bash /kaggle/working/Ai-Avatar/ml_models/proof/setup_env_b.sh`
Expected: ends with `mmcv 2.0.1`, `musetalk v15 weights OK`, `[env-B] READY`.
**If `mim install mmcv` fails to build:** report the full error — likely a torch/CUDA
mismatch; fallback is to confirm Kaggle's base torch and pin the matching mmcv wheel.
**If the gdown face-parse step fails (Drive quota):** report it; we'll add a mirror URL.

---

## Task 4: F5-TTS runner (env-A)

**Files:**
- Create: `ml_models/proof/run_f5tts.py`

- [ ] **Step 1: Write the runner**

```python
#!/usr/bin/env python3
"""F5-TTS voice clone + synthesis (runs in env-A).

Usage:
  python run_f5tts.py --ref REF.wav --ref-text "..." --gen-text "..." --out speech.wav
Pass --ref-text "" to auto-transcribe the reference via Whisper (slower; downloads a model).
"""
import argparse

import soundfile as sf
from f5_tts.api import F5TTS


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ref", required=True, help="reference wav (<=12s clean mono speech)")
    p.add_argument("--ref-text", default="", help="transcript of the reference; '' = auto-transcribe")
    p.add_argument("--gen-text", required=True, help="new text to speak in the cloned voice")
    p.add_argument("--out", required=True, help="output wav path")
    p.add_argument("--nfe", type=int, default=32, help="denoising steps (higher = better/slower)")
    p.add_argument("--model", default="F5TTS_v1_Base")
    args = p.parse_args()

    tts = F5TTS(model=args.model, device="cuda")
    wav, sr, _ = tts.infer(
        ref_file=args.ref,
        ref_text=args.ref_text,
        gen_text=args.gen_text,
        nfe_step=args.nfe,
        remove_silence=True,
    )
    sf.write(args.out, wav, sr)
    print(f"wrote {args.out} ({sr} Hz, {len(wav) / sr:.2f}s)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Local gate — byte-compile (catches syntax errors without torch)**

Run: `python -m py_compile ml_models/proof/run_f5tts.py && echo COMPILE_OK`
Expected: `COMPILE_OK`
(The `import f5_tts`/`soundfile` lines only resolve on Kaggle; py_compile checks syntax only.)

- [ ] **Step 3: Commit**

```bash
git add ml_models/proof/run_f5tts.py
git commit -m "feat(proof): F5-TTS runner"
```

- [ ] **Step 4: Kaggle gate (deferred)**

Run on Kaggle (env-A), using F5-TTS's bundled example reference:
```bash
cd /kaggle/working
REF=$(conda run -n envA python -c "from importlib.resources import files; print(files('f5_tts').joinpath('infer/examples/basic/basic_ref_en.wav'))")
conda run -n envA python Ai-Avatar/ml_models/proof/run_f5tts.py \
  --ref "$REF" --ref-text "" \
  --gen-text "Hello, this is a test of my cloned voice." \
  --out /kaggle/working/speech.wav
```
Expected: prints `wrote /kaggle/working/speech.wav (24000 Hz, ~Ns)` and the file exists.

---

## Task 5: LivePortrait runner (env-A)

**Files:**
- Create: `ml_models/proof/run_liveportrait.sh`

- [ ] **Step 1: Write the runner**

```bash
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
```

- [ ] **Step 2: Local gate — bash syntax check**

Run: `bash -n ml_models/proof/run_liveportrait.sh && echo SYNTAX_OK`
Expected: `SYNTAX_OK`

- [ ] **Step 3: Mark executable + commit**

```bash
chmod +x ml_models/proof/run_liveportrait.sh
git add ml_models/proof/run_liveportrait.sh
git commit -m "feat(proof): LivePortrait runner"
```

- [ ] **Step 4: Kaggle gate (deferred)**

Run on Kaggle (env-A), using LivePortrait's bundled example source + driving:
```bash
cd /kaggle/working/LivePortrait
bash /kaggle/working/Ai-Avatar/ml_models/proof/run_liveportrait.sh \
  assets/examples/source/s9.jpg \
  assets/examples/driving/d0.mp4 \
  /kaggle/working/lp_out
```
Expected: an `.mp4` appears in `/kaggle/working/lp_out`. (The driving `d0.mp4` length
sets the animation length; matching it to speech length is handled in the notebook.)

---

## Task 6: MuseTalk runner (env-B)

**Files:**
- Create: `ml_models/proof/run_musetalk.py`

- [ ] **Step 1: Write the runner**

```python
#!/usr/bin/env python3
"""MuseTalk v1.5 lip-sync (runs in env-B, invoked via conda run).

Writes a one-task inference YAML, calls `scripts.inference`, and prints the result
mp4 path. Must be invoked with CWD at the MuseTalk repo root (its imports are
repo-relative).

Usage (from MuseTalk repo root):
  python run_musetalk.py --video animated_25.mp4 --audio speech_16k.wav --result-dir results/job
"""
import argparse
import os
import subprocess
import sys


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True, help="animated head mp4 (25 fps)")
    p.add_argument("--audio", required=True, help="speech wav (16 kHz mono)")
    p.add_argument("--result-dir", default="results/job")
    p.add_argument("--bbox-shift", type=int, default=0)
    args = p.parse_args()

    os.makedirs("configs/inference", exist_ok=True)
    cfg_path = "configs/inference/proof_job.yaml"
    with open(cfg_path, "w") as fh:
        fh.write(
            "task_0:\n"
            f'  video_path: "{os.path.abspath(args.video)}"\n'
            f'  audio_path: "{os.path.abspath(args.audio)}"\n'
            f"  bbox_shift: {args.bbox_shift}\n"
        )
    print(f"wrote config {cfg_path}")

    cmd = [
        sys.executable, "-m", "scripts.inference",
        "--inference_config", cfg_path,
        "--result_dir", args.result_dir,
        "--unet_model_path", "models/musetalkV15/unet.pth",
        "--unet_config", "models/musetalkV15/musetalk.json",
        "--version", "v15",
        "--fps", "25",
        "--ffmpeg_path", "/usr/bin",
        "--use_float16",
    ]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"done — look for the output mp4 under {args.result_dir}/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Local gate — byte-compile**

Run: `python -m py_compile ml_models/proof/run_musetalk.py && echo COMPILE_OK`
Expected: `COMPILE_OK`

- [ ] **Step 3: Commit**

```bash
git add ml_models/proof/run_musetalk.py
git commit -m "feat(proof): MuseTalk runner"
```

- [ ] **Step 4: Kaggle gate (deferred — needs animated.mp4 + speech from earlier stages)**

Run on Kaggle (env-B), from the MuseTalk repo root:
```bash
cd /kaggle/working/MuseTalk
# 25fps video + 16kHz mono audio are prepared by the notebook (Task 7)
conda run -n envB python /kaggle/working/Ai-Avatar/ml_models/proof/run_musetalk.py \
  --video /kaggle/working/animated_25.mp4 \
  --audio /kaggle/working/speech_16k.wav \
  --result-dir /kaggle/working/mt_out
```
Expected: prints config + command, runs DWPose per frame, writes an mp4 under
`/kaggle/working/mt_out/`. **If it errors that a frame has no face**, the animated clip
turned too far — report it; we reduce driving motion.

---

## Task 7: Notebook generator + generated notebook

**Files:**
- Create: `ml_models/proof/build_notebook.py`
- Create (generated): `ml_models/proof/proof_pipeline.ipynb`

- [ ] **Step 1: Write the notebook generator**

```python
#!/usr/bin/env python3
"""Generate proof_pipeline.ipynb. Keeping the notebook generated from code keeps the
JSON valid and easy to edit. Run: python build_notebook.py"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))


def code(text):
    cells.append(nbf.v4.new_code_cell(text))


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
     "REF = subprocess.check_output(['conda','run','-n','envA','python','-c',\n"
     "    \"from importlib.resources import files; print(files('f5_tts').joinpath('infer/examples/basic/basic_ref_en.wav'))\"]).decode().strip()\n"
     "subprocess.run(['conda','run','-n','envA','python',\n"
     "    'Ai-Avatar/ml_models/proof/run_f5tts.py','--ref',REF,'--ref-text','',\n"
     "    '--gen-text','Hello, this is a test of my cloned voice on a free GPU.',\n"
     "    '--out','/kaggle/working/speech.wav'], check=True)\n"
     "import soundfile as sf; w,sr = sf.read('/kaggle/working/speech.wav'); print('speech', len(w)/sr,'s')")

code("# 5. Make the driving clip match the speech length, then animate with LivePortrait.\n"
     "import soundfile as sf, math, subprocess\n"
     "w, sr = sf.read('/kaggle/working/speech.wav'); dur = len(w)/sr\n"
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
     "subprocess.run(['conda','run','-n','envB','python',\n"
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

nb["cells"] = cells
with open("ml_models/proof/proof_pipeline.ipynb", "w") as fh:
    nbf.write(nb, fh)
print("wrote ml_models/proof/proof_pipeline.ipynb")
```

- [ ] **Step 2: Local gate — generate the notebook**

Run: `cd /home/groovy/AI-AVATAR && python ml_models/proof/build_notebook.py`
Expected: `wrote ml_models/proof/proof_pipeline.ipynb`
(If `nbformat` is missing: `pip install nbformat` first.)

- [ ] **Step 3: Local gate — notebook is valid nbformat**

Run: `python -c "import nbformat; nbformat.read('ml_models/proof/proof_pipeline.ipynb', as_version=4); print('NB_VALID')"`
Expected: `NB_VALID`

- [ ] **Step 4: Commit**

```bash
git add ml_models/proof/build_notebook.py ml_models/proof/proof_pipeline.ipynb
git commit -m "feat(proof): notebook generator + generated proof_pipeline.ipynb"
```

- [ ] **Step 5: Kaggle gate — the full proof (the real milestone)**

On Kaggle: **File → Import Notebook**, upload `ml_models/proof/proof_pipeline.ipynb`,
set GPU T4 + Internet On, **Run All**.
Expected: cell 8 renders `output.mp4` — the example face speaking the test sentence
with head motion + lip-sync. Report any failing cell's full output; we iterate on that
stage only (envs are isolated, so a fix to one doesn't disturb the others).

---

## Task 8: Final commit + push the proof bundle

- [ ] **Step 1: Verify all proof files are present and committed**

Run: `git status --short ml_models/proof/ && ls -1 ml_models/proof/`
Expected: clean working tree; lists README.md, setup_env_a.sh, setup_env_b.sh,
run_f5tts.py, run_liveportrait.sh, run_musetalk.py, build_notebook.py, proof_pipeline.ipynb.

- [ ] **Step 2: Push (so Kaggle's clone gets the scripts)**

```bash
git push
```
Expected: local `main` matches `origin/main`. (These are not workflow files, so a
normal token works.)

---

## Self-Review Notes

- **Spec coverage:** §6 Phase-0 cells → Tasks 2–7; §5 storage model is not exercised
  in Phase 0 (no app code) by design; §7 verified APIs are encoded directly in the
  runners (F5 `infer()` 3-tuple, LivePortrait CLI `-s/-d/-o`, MuseTalk yaml + v15 flags).
- **Deviation logged:** bundled example assets instead of committed `sample_assets/`
  (header note); the user-asset swap is documented in the notebook's final markdown.
- **Naming consistency:** env names `envA`/`envB`, output files `speech.wav` →
  `animated.mp4` → `animated_25.mp4` + `speech_16k.wav` → MuseTalk → `output.mp4` are
  used identically across Tasks 4–7 and the notebook cells.
- **No local pytest:** intentional — GPU install/inference can't run on the author
  machine; local gates are syntax/compile/nbformat validity, real gates are Kaggle runs.
```
