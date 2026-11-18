"use client";

import { useState } from "react";

import type { VocabItem } from "@/lib/types";

interface Props {
  item: VocabItem;
  targetLang: string;
  nativeLang: string;
  onRemove: (item: VocabItem) => Promise<void>;
  /** Extra detail shown on the right, e.g. when the card is next due. */
  meta?: string;
}

export function VocabRow({ item, targetLang, nativeLang, onRemove, meta }: Props) {
  const [removing, setRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setRemoving(true);
    setError(null);
    try {
      await onRemove(item);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't remove this card");
      setRemoving(false);
    }
  }

  return (
    <li className="flex flex-wrap items-start gap-x-4 gap-y-2 rounded-xl border border-stone-200 bg-white p-4">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-baseline gap-x-2">
          <span lang={targetLang} className="text-lg font-semibold text-stone-900">
            {item.term}
          </span>
          <span lang={nativeLang} className="text-stone-700">
            {item.translation}
          </span>
          {item.source_correction_id !== null && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-900">
              From a mistake
            </span>
          )}
        </p>
        {item.example_sentence && (
          <p lang={targetLang} className="mt-1 text-sm text-stone-600 italic">
            {item.example_sentence}
          </p>
        )}
        {meta && <p className="mt-1 text-xs text-stone-500">{meta}</p>}
        {error && (
          <p role="alert" className="mt-1 text-sm text-red-800">
            {error}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={remove}
        disabled={removing}
        aria-label={`Remove ${item.term}`}
        className="min-h-11 rounded-lg px-3 text-sm font-medium text-stone-600 hover:bg-stone-100 hover:text-red-800 focus-visible:outline-2 focus-visible:outline-teal-700 disabled:opacity-50"
      >
        {removing ? "Removing…" : "Remove"}
      </button>
    </li>
  );
}
