"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button, ErrorState, Spinner, inputClass } from "@/components/ui";
import { VocabRow } from "@/components/vocab/VocabRow";
import { api } from "@/lib/api";
import type { VocabFilter, VocabItem, VocabPage } from "@/lib/types";

const FILTERS: { value: VocabFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "due", label: "Due now" },
  { value: "new", label: "New" },
  { value: "learning", label: "Learning" },
  { value: "mistakes", label: "From mistakes" },
];

const PAGE_SIZE = 20;

function dueLabel(item: VocabItem): string {
  const ms = new Date(item.due_at).getTime() - Date.now();
  if (ms <= 0) return "Due now";
  const days = Math.ceil(ms / 86_400_000);
  return days === 1 ? "Due tomorrow" : `Due in ${days} days`;
}

type State = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: VocabPage };

export function DeckView({ targetLang, nativeLang }: { targetLang: string; nativeLang: string }) {
  const [filter, setFilter] = useState<VocabFilter>("all");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  // Debounce typing in the search box.
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    api.vocab({ filter, q: search, page, pageSize: PAGE_SIZE }).then(
      (data) => {
        if (!cancelled) setState({ status: "ready", data });
      },
      (err: unknown) => {
        if (!cancelled) {
          setState({ status: "error", message: err instanceof Error ? err.message : "Couldn't load your deck" });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [filter, search, page, attempt]);

  async function remove(item: VocabItem) {
    await api.deleteVocab(item.id);
    setAttempt((n) => n + 1);
  }

  const pages = state.status === "ready" ? Math.max(1, Math.ceil(state.data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="block flex-1 text-sm font-medium text-stone-700">
          Search
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Word or translation"
            maxLength={100}
            className={inputClass}
          />
        </label>
        {state.status === "ready" && state.data.due_count > 0 && (
          <Link
            href="/review"
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
          >
            Review {state.data.due_count} due
          </Link>
        )}
      </div>

      <div role="radiogroup" aria-label="Filter cards" className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            role="radio"
            aria-checked={filter === f.value}
            onClick={() => {
              setFilter(f.value);
              setPage(1);
            }}
            className="min-h-9 rounded-full border border-stone-300 bg-white px-3 text-sm text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-teal-700 aria-checked:border-teal-700 aria-checked:bg-teal-50 aria-checked:font-semibold aria-checked:text-teal-900"
          >
            {f.label}
          </button>
        ))}
      </div>

      {state.status === "loading" && <Spinner label="Loading your deck" />}
      {state.status === "error" && (
        <ErrorState message={state.message} onRetry={() => setAttempt((n) => n + 1)} />
      )}
      {state.status === "ready" && state.data.items.length === 0 && (
        <p className="rounded-xl bg-stone-100 p-6 text-center text-stone-700">
          {search || filter !== "all"
            ? "No cards match."
            : "Your deck is empty. Finish a conversation and the words you should study appear here."}
        </p>
      )}
      {state.status === "ready" && state.data.items.length > 0 && (
        <>
          <p className="text-sm text-stone-600">
            {state.data.total} {state.data.total === 1 ? "card" : "cards"}
          </p>
          <ul className="space-y-2">
            {state.data.items.map((item) => (
              <VocabRow
                key={item.id}
                item={item}
                targetLang={targetLang}
                nativeLang={nativeLang}
                onRemove={remove}
                meta={dueLabel(item)}
              />
            ))}
          </ul>
          {pages > 1 && (
            <nav aria-label="Pages" className="flex items-center justify-center gap-3">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <span className="text-sm text-stone-600">
                Page {page} of {pages}
              </span>
              <Button variant="secondary" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
