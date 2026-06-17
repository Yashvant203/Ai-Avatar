import Link from "next/link";

import { BackendStatus } from "@/components/BackendStatus";
import { Nav } from "@/components/Nav";
import { Button } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Panel";

const STEPS = [
  { n: "1", t: "Record", d: "Read a short generated script into a 2–5 minute video." },
  { n: "2", t: "Train", d: "We analyze your face, voice, expressions and head motion." },
  { n: "3", t: "Generate", d: "Type any script and get a lip-synced video in your voice." },
];

const STACK = ["F5-TTS", "MuseTalk", "LivePortrait", "FastAPI", "Next.js", "SQLite"];

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-5 pb-16">
      <Nav />

      {/* Hero */}
      <section className="grid items-center gap-10 py-16 sm:py-24 md:grid-cols-2">
        <div>
          <div className="flex items-center gap-2 font-mono text-sm text-ink/70">
            <span className="inline-block h-2 w-2 rounded-full bg-ink" />
            Self-hosted · open-source models only
          </div>
          <h1 className="mt-5 text-5xl leading-[0.92] sm:text-7xl">
            Human face.
            <br />
            AI&nbsp;scale.
          </h1>
          <p className="mt-3 font-mono text-2xl text-ink/70">your voice, any script</p>
          <p className="mt-5 max-w-md font-sans text-base leading-relaxed text-ink/70">
            Build a reusable talking-head avatar from one short video, then turn text into video —
            with cloned voice and lip-sync. No HeyGen, Synthesia, or D-ID.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/signup">
              <Button color="blue" size="lg">
                Create an avatar
              </Button>
            </Link>
            <Link href="/login">
              <Button color="yellow" size="lg">
                Log in
              </Button>
            </Link>
          </div>
        </div>

        <Panel color="lilac" className="flex aspect-square items-center justify-center bg-stripes">
          <span className="text-center font-mono text-6xl font-bold uppercase leading-none text-ink sm:text-7xl">
            Talking
            <br />
            Head
          </span>
        </Panel>
      </section>

      {/* How it works */}
      <section className="grid gap-4 sm:grid-cols-3">
        {STEPS.map((s) => (
          <div key={s.n} className="border-3 border-ink bg-paper p-5 shadow-brut">
            <span className="grid h-9 w-9 place-items-center border-3 border-ink bg-brut-blue font-mono text-sm font-bold text-paper">
              {s.n}
            </span>
            <h3 className="mt-3 text-lg">{s.t}</h3>
            <p className="mt-1 font-sans text-sm text-ink/70">{s.d}</p>
          </div>
        ))}
      </section>

      {/* Stack + status */}
      <section className="mt-10 flex flex-wrap items-center justify-between gap-4 border-3 border-ink bg-paper px-5 py-5 font-mono text-sm text-ink/70 shadow-brut">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <span className="font-bold uppercase text-ink">Built with</span>
          {STACK.map((s) => (
            <span key={s}>{s}</span>
          ))}
        </div>
        <BackendStatus />
      </section>
    </main>
  );
}
