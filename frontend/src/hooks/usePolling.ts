"use client";

import { useEffect, useRef, useState } from "react";

interface Options<T> {
  /** Async fetcher run on each tick. */
  fetcher: () => Promise<T>;
  /** Base interval in ms. */
  intervalMs?: number;
  /** Return true when the value is terminal — polling then stops. */
  isDone?: (value: T) => boolean;
  /** Set false to pause polling. */
  enabled?: boolean;
}

interface State<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  done: boolean;
}

/**
 * Generic interval poller with cleanup, light backoff on errors, and automatic
 * stop on a terminal value. Safe against unmount and overlapping ticks.
 */
export function usePolling<T>({
  fetcher,
  intervalMs = 2000,
  isDone,
  enabled = true,
}: Options<T>): State<T> & { refresh: () => void } {
  const [state, setState] = useState<State<T>>({
    data: null,
    error: null,
    loading: true,
    done: false,
  });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const active = useRef(true);
  const failures = useRef(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    active.current = true;
    if (!enabled) {
      setState((s) => ({ ...s, loading: false }));
      return;
    }

    const tick = async () => {
      try {
        const data = await fetcherRef.current();
        if (!active.current) return;
        failures.current = 0;
        const done = isDone ? isDone(data) : false;
        setState({ data, error: null, loading: false, done });
        if (!done) schedule(intervalMs);
      } catch (err) {
        if (!active.current) return;
        failures.current += 1;
        setState((s) => ({ ...s, error: err as Error, loading: false }));
        // Linear backoff capped at 5x the base interval.
        schedule(Math.min(intervalMs * (1 + failures.current), intervalMs * 5));
      }
    };

    const schedule = (ms: number) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(tick, ms);
    };

    tick();
    return () => {
      active.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalMs]);

  const refresh = () => {
    if (timer.current) clearTimeout(timer.current);
    setState((s) => ({ ...s, loading: true }));
    fetcherRef.current().then(
      (data) =>
        active.current &&
        setState({ data, error: null, loading: false, done: isDone ? isDone(data) : false }),
      (error) => active.current && setState((s) => ({ ...s, error, loading: false })),
    );
  };

  return { ...state, refresh };
}
