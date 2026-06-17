#!/usr/bin/env python3
"""Download MuseTalk v1.5 inference weights via the huggingface_hub Python API.

MuseTalk's own download_weights.sh shells out to `huggingface-cli`, which is a no-op
in huggingface_hub >= 1.0 (it just prints a deprecation hint and downloads nothing).
We fetch via the Python API instead — version-proof. Run from the MuseTalk repo root.
"""
import os
import urllib.request

from huggingface_hub import hf_hub_download

HF_JOBS = [
    ("TMElyralab/MuseTalk", "musetalkV15/musetalk.json", "models"),
    ("TMElyralab/MuseTalk", "musetalkV15/unet.pth", "models"),
    ("stabilityai/sd-vae-ft-mse", "config.json", "models/sd-vae"),
    ("stabilityai/sd-vae-ft-mse", "diffusion_pytorch_model.bin", "models/sd-vae"),
    ("openai/whisper-tiny", "config.json", "models/whisper"),
    ("openai/whisper-tiny", "pytorch_model.bin", "models/whisper"),
    ("openai/whisper-tiny", "preprocessor_config.json", "models/whisper"),
    ("yzd-v/DWPose", "dw-ll_ucoco_384.pth", "models/dwpose"),
]

for repo, fn, out in HF_JOBS:
    print("hf:", repo, fn)
    hf_hub_download(repo_id=repo, filename=fn, local_dir=out)

# face-parse BiSeNet (Google Drive) + its resnet18 backbone
os.makedirs("models/face-parse-bisent", exist_ok=True)
fp = "models/face-parse-bisent/79999_iter.pth"
if not os.path.exists(fp):
    import gdown

    gdown.download(id="154JgKpzCPW82qINcVieuPH3fZ2e0P812", output=fp, quiet=False)
rn = "models/face-parse-bisent/resnet18-5c106cde.pth"
if not os.path.exists(rn):
    urllib.request.urlretrieve(
        "https://download.pytorch.org/models/resnet18-5c106cde.pth", rn
    )

print("WEIGHTS DONE")
