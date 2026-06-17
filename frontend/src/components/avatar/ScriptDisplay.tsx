import { Panel } from "@/components/ui/Panel";
import type { Script } from "@/lib/types";

export function ScriptDisplay({ script }: { script: Script }) {
  return (
    <Panel className="space-y-3">
      <div className="flex items-center justify-between font-mono text-xs font-bold uppercase text-ink/70">
        <span>Training script</span>
        <span>{script.word_count} words</span>
      </div>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap border-3 border-ink bg-paper rounded-brut p-4 font-mono text-sm leading-relaxed">
        {script.content}
      </pre>
      <p className="font-sans text-sm text-ink/70">
        Read this aloud at a natural pace while recording. Look at the camera and keep your head
        fairly still.
      </p>
    </Panel>
  );
}
