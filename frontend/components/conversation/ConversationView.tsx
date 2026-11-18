"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";

import { CorrectionChips } from "@/components/conversation/CorrectionChips";
import { HintPanel } from "@/components/conversation/HintPanel";
import { MessageBubble, TypingIndicator } from "@/components/conversation/MessageBubble";
import { Alert, Button, ErrorState, Spinner } from "@/components/ui";
import { api, ApiError, streamTurn } from "@/lib/api";
import type { PracticeSession, Turn } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const MAX_CHARS = 1000;

export function ConversationView({ sessionId }: { sessionId: number }) {
  const [state, reload] = useAsync(() => api.getSession(sessionId));

  if (state.status === "loading") return <Spinner label="Loading conversation" />;
  if (state.status === "error") {
    if (state.error instanceof ApiError && state.error.status === 404) {
      return (
        <div className="py-12 text-center">
          <p className="text-stone-700">This conversation doesn&apos;t exist.</p>
          <Link href="/home" className="mt-4 inline-block font-semibold text-teal-800 underline">
            Back to scenarios
          </Link>
        </div>
      );
    }
    return <ErrorState message={state.error.message} onRetry={reload} />;
  }
  return <Conversation key={state.data.id} initial={state.data} />;
}

function Conversation({ initial }: { initial: PracticeSession }) {
  const router = useRouter();
  const [ending, setEnding] = useState(false);
  const [turns, setTurns] = useState<Turn[]>(initial.turns);
  const [draft, setDraft] = useState("");
  const [pendingText, setPendingText] = useState<string | null>(null);
  const [streamText, setStreamText] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHints, setShowHints] = useState(false);
  const [checking, setChecking] = useState<ReadonlySet<number>>(new Set());
  const logEnd = useRef<HTMLLIElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const lang = initial.target_language;
  const nativeLang = initial.native_language;
  const ended = initial.ended_at !== null;
  const lastTurn = turns.at(-1);
  const awaitingReply = !sending && lastTurn?.role === "learner";
  const hintTurnId = !sending && lastTurn?.role === "partner" ? lastTurn.id : null;
  const hasLearnerTurn = turns.some((t) => t.role === "learner");

  async function endSession() {
    if (
      !hasLearnerTurn &&
      !window.confirm("You haven't sent a message yet. End this session anyway?")
    ) {
      return;
    }
    setEnding(true);
    setError(null);
    try {
      const result = await api.endSession(initial.id);
      // Pages stay mounted after navigation, so reset before leaving.
      setEnding(false);
      // The skipped count is only known now, so pass it along in the URL.
      const skipped = result.skipped_duplicates ? `?skipped=${result.skipped_duplicates}` : "";
      router.push(`/sessions/${initial.id}/summary${skipped}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't end the session");
      setEnding(false);
    }
  }

  useEffect(() => {
    logEnd.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns.length, streamText, pendingText, error]);

  function setChecked(turnId: number, isChecking: boolean) {
    setChecking((prev) => {
      const next = new Set(prev);
      if (isChecking) next.add(turnId);
      else next.delete(turnId);
      return next;
    });
  }

  function resync() {
    // Show exactly what the server saved, including corrections that arrived late.
    api.getSession(initial.id).then((fresh) => setTurns(fresh.turns), () => undefined);
  }

  async function run(body: { text: string } | { retry: true }) {
    setSending(true);
    setError(null);
    setStreamText(null);
    let learnerSaved = "retry" in body;
    let learnerTurnId: number | null = null;
    const finishReply = () => {
      setStreamText(null);
      setSending(false);
      inputRef.current?.focus();
    };
    try {
      await streamTurn(initial.id, body, {
        onLearnerTurn: (turn) => {
          learnerSaved = true;
          learnerTurnId = turn.id;
          setPendingText(null);
          setTurns((prev) => [...prev, turn]);
          setChecked(turn.id, true);
        },
        onToken: (text) => setStreamText((prev) => (prev ?? "") + text),
        onDone: (turn) => {
          setTurns((prev) => [...prev, turn]);
          finishReply();
        },
        onReplyError: (message) => {
          setError(message);
          finishReply();
        },
        onCorrections: ({ turn_id, corrections }) => {
          setTurns((prev) => prev.map((t) => (t.id === turn_id ? { ...t, corrections } : t)));
          setChecked(turn_id, false);
        },
      });
    } catch (err) {
      setPendingText(null);
      setError(err instanceof Error ? err.message : "Something went wrong");
      // If the server never saved the message, give the text back so nothing is lost.
      if (!learnerSaved && "text" in body) setDraft((current) => current || body.text);
      finishReply();
      resync();
    } finally {
      // The stream is over. Stop "checking"; anything late appears on the next load.
      if (learnerTurnId !== null) setChecked(learnerTurnId, false);
    }
  }
  function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    setPendingText(text);
    void run({ text });
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex min-h-[calc(100dvh-10rem)] flex-col gap-4">
      <header>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/home" className="text-sm font-medium text-teal-800 underline">
            ← Scenarios
          </Link>
          {ended ? (
            <Link
              href={`/sessions/${initial.id}/summary`}
              className="text-sm font-semibold text-teal-800 underline"
            >
              View summary
            </Link>
          ) : (
            <Button variant="secondary" onClick={endSession} disabled={ending || sending}>
              {ending ? "Writing your summary…" : "End session"}
            </Button>
          )}
        </div>
        <h1 className="mt-2 text-2xl font-bold">{initial.scenario.title}</h1>
        <p className="text-sm text-stone-600">
          <span className="font-medium text-stone-800">Goal:</span> {initial.scenario.goal}
        </p>
      </header>

      <ol
        aria-label="Conversation"
        aria-live="polite"
        aria-busy={sending}
        className="flex flex-1 flex-col gap-3 rounded-2xl bg-stone-100 p-3 sm:p-4"
      >
        {turns.map((turn) => (
          <MessageBubble key={turn.id} role={turn.role} text={turn.text} lang={lang}>
            {turn.role === "learner" && (
              <CorrectionChips
                corrections={turn.corrections}
                checking={checking.has(turn.id)}
                targetLang={lang}
                nativeLang={nativeLang}
              />
            )}
          </MessageBubble>
        ))}
        {pendingText !== null && (
          <MessageBubble role="learner" text={pendingText} lang={lang} pending />
        )}
        {sending && streamText === null && <TypingIndicator />}
        {streamText !== null && (
          <MessageBubble role="partner" text={streamText} lang={lang} streaming />
        )}
        <li ref={logEnd} aria-hidden className="h-0" />
      </ol>

      {error && (
        <Alert>
          <span>{error}</span>
          {awaitingReply && (
            <Button variant="secondary" className="ml-3 min-h-9 py-1" onClick={() => void run({ retry: true })}>
              Retry
            </Button>
          )}
        </Alert>
      )}
      {!error && awaitingReply && (
        <Alert>
          <span>Your partner hasn&apos;t replied to your last message.</span>
          <Button variant="secondary" className="ml-3 min-h-9 py-1" onClick={() => void run({ retry: true })}>
            Get reply
          </Button>
        </Alert>
      )}

      {ended ? (
        <p className="rounded-xl bg-stone-100 p-4 text-center text-stone-700">
          This session has ended.{" "}
          <Link href={`/sessions/${initial.id}/summary`} className="font-semibold text-teal-800 underline">
            View the summary
          </Link>
        </p>
      ) : (
        <div className="sticky bottom-0 space-y-3 bg-stone-50 pb-2">
          {showHints && (
            <HintPanel
              sessionId={initial.id}
              partnerTurnId={hintTurnId}
              lang={lang}
              onPick={(text) => {
                setDraft(text);
                inputRef.current?.focus();
              }}
            />
          )}
          <form onSubmit={submit} className="flex items-end gap-2">
            <label htmlFor="message" className="sr-only">
              Your message
            </label>
            <textarea
              id="message"
              ref={inputRef}
              lang={lang}
              rows={2}
              maxLength={MAX_CHARS}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Type your reply… (Enter to send, Shift+Enter for a new line)"
              className="min-h-11 flex-1 resize-none rounded-xl border border-stone-300 bg-white px-3 py-2 text-base focus:border-teal-700 focus:outline-2 focus:outline-teal-700/30"
            />
            <Button type="submit" disabled={sending || ending || !draft.trim()}>
              {sending ? "Sending…" : "Send"}
            </Button>
          </form>
          <label className="flex w-fit cursor-pointer items-center gap-2 text-sm text-stone-700">
            <input
              type="checkbox"
              role="switch"
              aria-checked={showHints}
              checked={showHints}
              onChange={(e) => setShowHints(e.target.checked)}
              className="size-4 accent-teal-700"
            />
            Show hints for what to say next
          </label>
        </div>
      )}
    </div>
  );
}
