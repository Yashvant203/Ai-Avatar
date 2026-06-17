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
