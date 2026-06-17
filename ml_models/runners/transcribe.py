#!/usr/bin/env python3
"""Transcribe a reference wav to text (runs in envF5).

Captured once at avatar-creation time so every later F5-TTS generation can pass an
explicit --ref-text (faster and more stable than auto-transcribing each time).

Usage:
  python transcribe.py --audio reference.wav --out transcript.txt
"""
import argparse


def _transcribe(audio: str) -> str:
    # Prefer F5-TTS's bundled ASR (the same path its auto-transcribe uses).
    try:
        from f5_tts.infer.utils_infer import transcribe

        return (transcribe(audio) or "").strip()
    except Exception:
        pass
    # Fallback: faster-whisper (a common F5-TTS dependency).
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cuda", compute_type="float16")
    segments, _ = model.transcribe(audio)
    return " ".join(seg.text for seg in segments).strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    text = _transcribe(args.audio)
    with open(args.out, "w") as fh:
        fh.write(text)
    print(f"wrote {args.out}: {text[:80]!r}")


if __name__ == "__main__":
    main()
