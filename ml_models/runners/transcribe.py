#!/usr/bin/env python3
"""Transcribe a reference wav to text (runs in envF5) — BEST EFFORT.

Captured once at avatar-creation time so each later F5-TTS generation can pass an
explicit --ref-text. This is an optimization, NOT a hard requirement: if every
transcription method fails we write an empty transcript and exit 0, and F5-TTS
auto-transcribes the reference at generation time instead. Avatar creation must
never fail just because transcription did.

Usage:
  python transcribe.py --audio reference.wav --out transcript.txt
"""
import argparse
import traceback


def _transcribe(audio: str) -> str:
    errors = []
    # 1) F5-TTS's bundled ASR (the same path its auto-transcribe uses).
    try:
        from f5_tts.infer.utils_infer import transcribe

        return (transcribe(audio) or "").strip()
    except Exception as e:  # noqa: BLE001
        errors.append(f"f5_tts.transcribe: {e}")
    # 2) faster-whisper, if available.
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel("base", device="cuda", compute_type="float16")
        segments, _ = model.transcribe(audio)
        return " ".join(seg.text for seg in segments).strip()
    except Exception as e:  # noqa: BLE001
        errors.append(f"faster_whisper: {e}")
    # 3) transformers whisper pipeline, if available.
    try:
        from transformers import pipeline

        asr = pipeline("automatic-speech-recognition", model="openai/whisper-base", device=0)
        return (asr(audio).get("text") or "").strip()
    except Exception as e:  # noqa: BLE001
        errors.append(f"transformers: {e}")
    raise RuntimeError("; ".join(errors))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    text = ""
    try:
        text = _transcribe(args.audio)
    except Exception:  # noqa: BLE001 - best effort; empty transcript is acceptable
        print("[transcribe] WARN: all methods failed; writing empty transcript "
              "(F5-TTS will auto-transcribe at generation time).")
        traceback.print_exc()
    with open(args.out, "w") as fh:
        fh.write(text or "")
    print(f"wrote {args.out}: {text[:80]!r}")


if __name__ == "__main__":
    main()
