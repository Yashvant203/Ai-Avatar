"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { getHealth } from "@/lib/api";

type State = { label: string; color: "green" | "red" | "yellow" };

export function BackendStatus() {
  const [state, setState] = useState<State>({ label: "checking…", color: "yellow" });

  useEffect(() => {
    let active = true;
    getHealth()
      .then((h) => active && setState({ label: `api ${h.version} · db ${h.db}`, color: "green" }))
      .catch(() => active && setState({ label: "api offline", color: "red" }));
    return () => {
      active = false;
    };
  }, []);

  return <Badge color={state.color}>{state.label}</Badge>;
}
