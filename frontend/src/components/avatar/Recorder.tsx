"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/Feedback";

const ACCEPTED = ["video/mp4", "video/quicktime", "video/webm"];

/**
 * Webcam capture (getUserMedia + MediaRecorder) with a file-upload fallback.
 * Calls onReady(file) once the user has a recorded/selected clip to submit.
 */
export function Recorder({ onReady }: { onReady: (file: File | null) => void }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const [supported, setSupported] = useState(true);
  const [recording, setRecording] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSupported(
      typeof navigator !== "undefined" &&
        !!navigator.mediaDevices?.getUserMedia &&
        typeof MediaRecorder !== "undefined",
    );
    return () => stopStream();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!recording) return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [recording]);

  function stopStream() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }

  async function startRecording() {
    setError(null);
    setSeconds(0);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.muted = true;
        await videoRef.current.play();
      }
      chunks.current = [];
      const rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => e.data.size > 0 && chunks.current.push(e.data);
      rec.onstop = () => {
        const blob = new Blob(chunks.current, { type: "video/webm" });
        const file = new File([blob], "recording.webm", { type: "video/webm" });
        setPreviewUrl(URL.createObjectURL(blob));
        if (videoRef.current) videoRef.current.srcObject = null;
        stopStream();
        onReady(file);
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
    } catch {
      setError("Could not access camera/microphone. Use file upload instead.");
      setSupported(false);
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    setError(null);
    const file = e.target.files?.[0];
    if (!file) return;
    if (!ACCEPTED.includes(file.type)) {
      setError("Unsupported file type. Use MP4, MOV, or WebM.");
      onReady(null);
      return;
    }
    setPreviewUrl(URL.createObjectURL(file));
    onReady(file);
  }

  return (
    <div className="space-y-4">
      {error && <ErrorBanner message={error} />}

      <div className="aspect-video w-full overflow-hidden border-3 border-ink bg-ink rounded-brut shadow-brut">
        {previewUrl ? (
          <video src={previewUrl} controls className="h-full w-full" />
        ) : (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video ref={videoRef} className="h-full w-full object-cover" playsInline />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {supported &&
          (recording ? (
            <Button color="pink" onClick={stopRecording}>
              ⏹ Stop ({seconds}s)
            </Button>
          ) : (
            <Button color="blue" onClick={startRecording}>
              ● Record
            </Button>
          ))}

        <label className="cursor-pointer">
          <span className="inline-flex h-11 cursor-pointer items-center border-3 border-ink bg-paper px-5 font-mono text-sm font-bold uppercase tracking-wide text-ink rounded-brut shadow-brut transition-all hover:bg-brut-yellow active:translate-x-1 active:translate-y-1 active:shadow-brut-press">
            Upload file
          </span>
          <input type="file" accept={ACCEPTED.join(",")} className="hidden" onChange={onFile} />
        </label>
      </div>

      <p className="font-mono text-xs text-ink/70">
        Aim for a 2–5 minute clip. Webcam recording produces WebM; file upload accepts MP4/MOV/WebM.
      </p>
    </div>
  );
}
