"use client";

import { useRouter } from "next/navigation";
import { useLayoutEffect, useState } from "react";

import { Alert, Button, ErrorState, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { CefrLevel, Scenario } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const LEVELS: CefrLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

function difficultyLabel(scenario: CefrLevel, learner: CefrLevel): string {
  const gap = LEVELS.indexOf(scenario) - LEVELS.indexOf(learner);
  if (gap <= -1) return "Easy for you";
  if (gap === 0) return "Your level";
  if (gap === 1) return "A stretch";
  return "Challenging";
}

export function ScenarioPicker({ learnerLevel }: { learnerLevel: CefrLevel }) {
  const router = useRouter();
  const [state, reload] = useAsync(() => api.scenarios().then((r) => r.scenarios));
  const [startingId, setStartingId] = useState<number | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  // Next.js keeps this page mounted but hidden after navigating away (React Activity).
  // Clear the "starting" state when it's hidden, so the buttons work again on return.
  useLayoutEffect(() => {
    return () => {
      setStartingId(null);
      setStartError(null);
    };
  }, []);

  async function start(scenario: Scenario) {
    setStartingId(scenario.id);
    setStartError(null);
    try {
      const session = await api.startSession(scenario.id);
      router.push(`/sessions/${session.id}`);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Could not start the conversation");
      setStartingId(null);
    }
  }

  if (state.status === "loading") return <Spinner label="Loading scenarios" />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={reload} />;
  if (state.data.length === 0) {
    return <p className="py-8 text-center text-stone-600">No scenarios are available yet.</p>;
  }

  return (
    <div className="space-y-4">
      {startError && <Alert>{startError}</Alert>}
      <ul className="grid gap-4 sm:grid-cols-2">
        {state.data.map((scenario) => (
          <li key={scenario.id}>
            <article className="flex h-full flex-col rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-lg font-semibold text-stone-900">{scenario.title}</h3>
                <span
                  className="shrink-0 rounded-md bg-stone-100 px-2 py-0.5 text-xs font-semibold text-stone-700"
                  title={`Scenario difficulty ${scenario.cefr_level}`}
                >
                  {scenario.cefr_level}
                </span>
              </div>
              <p className="mt-1 text-xs font-medium text-teal-800">
                {difficultyLabel(scenario.cefr_level, learnerLevel)}
              </p>
              <p className="mt-2 text-sm text-stone-700">{scenario.description}</p>
              <p className="mt-2 text-sm text-stone-600">
                <span className="font-medium text-stone-800">Goal:</span> {scenario.goal}
              </p>
              <Button
                className="mt-4 self-start"
                onClick={() => start(scenario)}
                disabled={startingId !== null}
                aria-label={`Start ${scenario.title}`}
              >
                {startingId === scenario.id ? "Starting…" : "Start"}
              </Button>
            </article>
          </li>
        ))}
      </ul>
    </div>
  );
}
