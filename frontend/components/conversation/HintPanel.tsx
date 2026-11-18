"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

interface Props {
  sessionId: number;
  /** The partner turn to suggest a response to. Null while waiting for a reply. */
  partnerTurnId: number | null;
  lang: string;
  onPick: (text: string) => void;
}

type HintState =
  | { status: "loading"; forTurn: number }
  | { status: "error"; forTurn: number; message: string }
  | { status: "ready"; forTurn: number; suggestions: string[] };

/** Suggestions for what to say next. Fetches once per partner message. */
export function HintPanel({ sessionId, partnerTurnId, lang, onPick }: Props) {
  const [state, setState] = useState<HintState | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (partnerTurnId === null) return;
    let cancelled = false;
    api.hint(sessionId).then(
      (hint) => {
        if (!cancelled) setState({ status: "ready", forTurn: partnerTurnId, suggestions: hint.suggestions });
      },
      (err: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            forTurn: partnerTurnId,
            message: err instanceof Error ? err.message : "Couldn't get a hint",
          });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [sessionId, partnerTurnId, attempt]);

  let body;
  if (partnerTurnId === null) {
    body = <p className="text-sm text-stone-600">Hints appear after your partner replies.</p>;
  } else if (!state || state.forTurn !== partnerTurnId || state.status === "loading") {
    body = <p className="text-sm text-stone-600">Thinking of something to say…</p>;
  } else if (state.status === "error") {
    body = (
      <p className="text-sm text-red-800">
        {state.message}{" "}
        <button type="button" className="font-semibold underline" onClick={() => {
            setState({ status: "loading", forTurn: partnerTurnId });
            setAttempt((n) => n + 1);
          }}>
          Try again
        </button>
      </p>
    );
  } else {
    body = (
      <ul className="flex flex-wrap gap-2">
        {state.suggestions.map((suggestion) => (
          <li key={suggestion}>
            <button
              type="button"
              lang={lang}
              onClick={() => onPick(suggestion)}
              className="min-h-11 rounded-full border border-amber-300 bg-white px-3 py-1.5 text-left text-sm text-stone-800 hover:bg-amber-100 focus-visible:outline-2 focus-visible:outline-teal-700"
            >
              {suggestion}
            </button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <section aria-label="Hint" aria-live="polite" className="rounded-xl border border-amber-200 bg-amber-50 p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-900">
        You could say
      </h2>
      {body}
    </section>
  );
}
