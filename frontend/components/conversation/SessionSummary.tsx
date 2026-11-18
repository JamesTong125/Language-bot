"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ErrorState, Spinner } from "@/components/ui";
import { VocabRow } from "@/components/vocab/VocabRow";
import { api, ApiError } from "@/lib/api";
import type { PracticeSession, VocabItem, WrapUpResult } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

async function load(sessionId: number): Promise<{ session: PracticeSession; result: WrapUpResult }> {
  const [session, result] = await Promise.all([api.getSession(sessionId), api.getSummary(sessionId)]);
  return { session, result };
}

export function SessionSummaryScreen({ sessionId }: { sessionId: number }) {
  return <AppShell>{() => <SummaryLoader sessionId={sessionId} />}</AppShell>;
}

function SummaryLoader({ sessionId }: { sessionId: number }) {
  const [state, reload] = useAsync(() => load(sessionId));
  if (state.status === "loading") return <Spinner label="Loading summary" />;
  if (state.status === "error") {
    const status = state.error instanceof ApiError ? state.error.status : 0;
    if (status === 404 || status === 409) {
      return (
        <div className="py-12 text-center">
          <p className="text-stone-700">
            {status === 409 ? "This session hasn't ended yet." : "This session doesn't exist."}
          </p>
          <Link
            href={status === 409 ? `/sessions/${sessionId}` : "/home"}
            className="mt-4 inline-block font-semibold text-teal-800 underline"
          >
            {status === 409 ? "Back to the conversation" : "Back to scenarios"}
          </Link>
        </div>
      );
    }
    return <ErrorState message={state.error.message} onRetry={reload} />;
  }
  return <Summary key={state.data.result.session_id} {...state.data} />;
}

function Summary({ session, result }: { session: PracticeSession; result: WrapUpResult }) {
  const [vocab, setVocab] = useState<VocabItem[]>(result.new_vocab);
  // Set by the conversation page right after ending; absent when revisiting later.
  const skipped = Number(useSearchParams().get("skipped")) || 0;
  const summary = result.summary;
  const lang = session.target_language;
  const nativeLang = session.native_language;
  const learnerMessages = session.turns.filter((t) => t.role === "learner").length;

  async function remove(item: VocabItem) {
    await api.deleteVocab(item.id);
    setVocab((prev) => prev.filter((v) => v.id !== item.id));
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="text-sm font-semibold uppercase tracking-wide text-stone-500">Session summary</p>
        <h1 className="mt-1 text-2xl font-bold">{session.scenario.title}</h1>
        <p className="mt-1 text-sm text-stone-600">
          {learnerMessages} {learnerMessages === 1 ? "message" : "messages"} sent
          {result.error_rate !== null &&
            ` · ${Math.round((1 - result.error_rate) * 100)}% without mistakes`}
        </p>
      </header>

      {summary ? (
        <div lang={nativeLang} className="grid gap-4 sm:grid-cols-2">
          <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 sm:col-span-2">
            <h2 className="font-semibold text-emerald-900">What went well</h2>
            <p className="mt-2 text-stone-800">{summary.went_well}</p>
          </section>
          <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
            <h2 className="font-semibold text-amber-900">Recurring mistakes</h2>
            {summary.recurring_mistakes.length ? (
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-stone-800">
                {summary.recurring_mistakes.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ol>
            ) : (
              <p className="mt-2 text-stone-800">No recurring mistakes. Nice work!</p>
            )}
          </section>
          <section className="rounded-2xl border border-sky-200 bg-sky-50 p-5">
            <h2 className="font-semibold text-sky-900">Things to practise</h2>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-stone-800">
              {summary.practice.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ol>
          </section>
        </div>
      ) : (
        <p className="rounded-xl bg-stone-100 p-4 text-stone-700">
          You ended this session before sending a message, so there&apos;s nothing to review.
        </p>
      )}

      <section aria-labelledby="new-vocab-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="new-vocab-heading" className="text-xl font-bold">
            New cards
          </h2>
          {skipped > 0 && (
            <p className="text-sm text-stone-600">
              {skipped} {skipped === 1 ? "word was" : "words were"} already in your deck, so not
              added again.
            </p>
          )}
        </div>
        {vocab.length ? (
          <>
            <p className="mt-1 mb-3 text-sm text-stone-600">
              These are in your deck and due for review now. Remove any you don&apos;t want.
            </p>
            <ul className="space-y-2">
              {vocab.map((item) => (
                <VocabRow
                  key={item.id}
                  item={item}
                  targetLang={lang}
                  nativeLang={nativeLang}
                  onRemove={remove}
                />
              ))}
            </ul>
          </>
        ) : (
          <p className="mt-2 text-stone-600">No new cards from this session.</p>
        )}
      </section>

      <div className="flex flex-wrap gap-3">
        {vocab.length > 0 && (
          <Link
            href="/review"
            className="inline-flex min-h-11 items-center rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
          >
            Review now
          </Link>
        )}
        <Link
          href="/home"
          className="inline-flex min-h-11 items-center rounded-lg border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-800 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
        >
          New scenario
        </Link>
        <Link
          href={`/sessions/${session.id}`}
          className="inline-flex min-h-11 items-center px-2 text-sm font-semibold text-teal-800 underline"
        >
          View transcript
        </Link>
      </div>
    </div>
  );
}
