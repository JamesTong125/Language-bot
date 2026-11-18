"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, ErrorState, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { VocabItem } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const RATINGS = [
  { value: 0, label: "Forgot", hint: "No idea", style: "border-rose-300 bg-rose-50 text-rose-900 hover:bg-rose-100" },
  { value: 1, label: "Wrong", hint: "Got it wrong", style: "border-rose-300 bg-rose-50 text-rose-900 hover:bg-rose-100" },
  { value: 2, label: "Almost", hint: "Wrong, but close", style: "border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100" },
  { value: 3, label: "Hard", hint: "Right, with effort", style: "border-sky-300 bg-sky-50 text-sky-900 hover:bg-sky-100" },
  { value: 4, label: "Good", hint: "Right", style: "border-emerald-300 bg-emerald-50 text-emerald-900 hover:bg-emerald-100" },
  { value: 5, label: "Easy", hint: "Instant", style: "border-emerald-300 bg-emerald-50 text-emerald-900 hover:bg-emerald-100" },
] as const;

function nextDue(item: VocabItem): string {
  const days = item.interval_days;
  if (days <= 1) return "tomorrow";
  if (days < 30) return `in ${days} days`;
  const months = Math.round(days / 30);
  return `in ${months} ${months === 1 ? "month" : "months"}`;
}

interface Props {
  targetLang: string;
  nativeLang: string;
}

export function ReviewFlow({ targetLang, nativeLang }: Props) {
  const [state, reload] = useAsync(() => api.reviewQueue(20));
  if (state.status === "loading") return <Spinner label="Loading cards" />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={reload} />;
  return (
    <Deck
      key={state.data.items.map((i) => i.id).join(",")}
      cards={state.data.items}
      dueCount={state.data.due_count}
      targetLang={targetLang}
      nativeLang={nativeLang}
      onMore={reload}
    />
  );
}

function Deck({
  cards,
  dueCount,
  targetLang,
  nativeLang,
  onMore,
}: {
  cards: VocabItem[];
  dueCount: number;
  targetLang: string;
  nativeLang: string;
  onMore: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const card = cards[index];

  const rate = useCallback(
    async (rating: number) => {
      if (!card || saving) return;
      setSaving(true);
      setError(null);
      try {
        const { item } = await api.review(card.id, rating);
        setLastResult(`“${card.term}” comes back ${nextDue(item)}.`);
        setIndex((i) => i + 1);
        setRevealed(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't save your rating");
      } finally {
        setSaving(false);
      }
    },
    [card, saving],
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (!revealed && (event.key === " " || event.key === "Enter")) {
        // Don't double-fire when a focused button handles Enter/Space itself.
        if (target?.tagName === "BUTTON") return;
        event.preventDefault();
        setRevealed(true);
      } else if (revealed && /^[0-5]$/.test(event.key)) {
        event.preventDefault();
        void rate(Number(event.key));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [revealed, rate]);

  if (cards.length === 0) {
    return (
      <div className="rounded-2xl border border-stone-200 bg-white p-8 text-center">
        <p className="text-lg font-semibold">Nothing to review right now</p>
        <p className="mt-1 text-stone-600">
          Cards come from your sessions. Finish a conversation to add new ones.
        </p>
        <div className="mt-4 flex justify-center gap-3">
          <Link href="/home" className="font-semibold text-teal-800 underline">
            Start a scenario
          </Link>
          <Link href="/vocab" className="font-semibold text-teal-800 underline">
            Browse your deck
          </Link>
        </div>
      </div>
    );
  }

  if (!card) {
    const remaining = Math.max(0, dueCount - cards.length);
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center" role="status">
        <p className="text-lg font-semibold text-emerald-900">
          Done! You reviewed {cards.length} {cards.length === 1 ? "card" : "cards"}.
        </p>
        {lastResult && <p className="mt-1 text-sm text-stone-700">{lastResult}</p>}
        {remaining > 0 ? (
          <Button className="mt-4" onClick={onMore}>
            Review {remaining} more
          </Button>
        ) : (
          <Link href="/home" className="mt-4 inline-block font-semibold text-teal-800 underline">
            Back to scenarios
          </Link>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm text-stone-600">
        <span>
          Card {index + 1} of {cards.length}
        </span>
        <span aria-live="polite">{lastResult}</span>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-stone-200"
        role="progressbar"
        aria-label="Review progress"
        aria-valuemin={0}
        aria-valuemax={cards.length}
        aria-valuenow={index}
      >
        <div className="h-full bg-teal-600 transition-all" style={{ width: `${(index / cards.length) * 100}%` }} />
      </div>

      <section
        aria-label="Flashcard"
        className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-stone-200 bg-white p-6 text-center shadow-sm"
      >
        <p lang={targetLang} className="text-3xl font-bold text-stone-900">
          {card.term}
        </p>
        {revealed ? (
          <div className="mt-4 space-y-2" aria-live="polite">
            <p lang={nativeLang} className="text-xl text-stone-800">
              {card.translation}
            </p>
            {card.example_sentence && (
              <p lang={targetLang} className="text-stone-600 italic">
                {card.example_sentence}
              </p>
            )}
          </div>
        ) : (
          <Button className="mt-6" onClick={() => setRevealed(true)} autoFocus>
            Show answer
            <kbd className="ml-2 rounded bg-white/20 px-1.5 text-xs">Space</kbd>
          </Button>
        )}
      </section>

      {error && <Alert>{error}</Alert>}

      {revealed && (
        <fieldset disabled={saving}>
          <legend className="mb-2 text-sm font-medium text-stone-700">How well did you know it?</legend>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {RATINGS.map((r, i) => (
              <button
                key={r.value}
                type="button"
                onClick={() => void rate(r.value)}
                autoFocus={i === 4}
                className={`flex min-h-14 flex-col items-center justify-center rounded-xl border px-2 py-1.5 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:opacity-50 ${r.style}`}
              >
                <span>
                  <kbd className="mr-1 font-mono text-xs opacity-70">{r.value}</kbd>
                  {r.label}
                </span>
                <span className="text-xs font-normal opacity-80">{r.hint}</span>
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-stone-500">
            Shortcuts: Space to show the answer, 0 to 5 to rate.
          </p>
        </fieldset>
      )}
    </div>
  );
}
