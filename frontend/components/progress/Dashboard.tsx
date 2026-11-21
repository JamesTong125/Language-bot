"use client";

import Link from "next/link";

import { LevelSuggestion } from "@/components/progress/LevelSuggestion";
import { Card, ErrorState, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { CefrLevel, ErrorType, LevelProgress, ProfileResponse, Stats } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const LEVELS: CefrLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

const ERROR_LABELS: Record<ErrorType, string> = {
  grammar: "Grammar",
  vocabulary: "Vocabulary",
  spelling: "Spelling",
  word_order: "Word order",
  conjugation: "Conjugation",
  register: "Tone",
};

/** "2026-11-16" as a local date, without a time zone shift. */
function parseDay(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

const shortDate = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

export function Dashboard({ profile, onProfileChanged }: { profile: ProfileResponse; onProfileChanged: () => void }) {
  const [state, reload] = useAsync(() => api.stats());
  if (state.status === "loading") return <Spinner label="Loading your progress" />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={reload} />;
  const stats = state.data;
  const empty = stats.totals.sessions_completed === 0 && stats.totals.reviews === 0;

  return (
    <div className="space-y-6">
      <LevelSuggestion level={stats.level} profile={profile} onChanged={onProfileChanged} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat
          label="Day streak"
          value={stats.streak.days}
          note={
            stats.streak.days === 0
              ? "Practise today to start one"
              : stats.streak.practised_today
                ? "You practised today"
                : "Practise today to keep it"
          }
        />
        <Stat label="Sessions completed" value={stats.totals.sessions_completed} />
        <Stat label="Messages sent" value={stats.totals.learner_messages} />
        <Stat
          label="Cards in deck"
          value={stats.totals.vocab_items}
          note={stats.totals.vocab_due ? `${stats.totals.vocab_due} due now` : "None due"}
        />
      </div>

      <LevelCard level={stats.level} />

      {empty ? (
        <Card>
          <p className="text-stone-700">
            Finish a session to see your mistake trends and the kinds of mistakes you make most.
          </p>
          <Link href="/home" className="mt-3 inline-block font-semibold text-teal-800 underline">
            Pick a scenario
          </Link>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <WeeklySessions weeks={stats.sessions_per_week} />
          <ErrorTypes counts={stats.error_types} />
          <div className="lg:col-span-2">
            <Trend points={stats.error_rate_trend} />
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-4">
      <p className="text-sm text-stone-600">{label}</p>
      <p className="mt-1 text-3xl font-bold text-stone-900">{value}</p>
      {note && <p className="mt-1 text-xs text-stone-500">{note}</p>}
    </div>
  );
}

function LevelCard({ level }: { level: LevelProgress }) {
  const current = LEVELS.indexOf(level.current_level);
  const avg = level.average_error_rate;
  const percent = avg === null ? null : Math.round(avg * 100);
  const needed = level.sessions_needed - level.sessions_counted;

  return (
    <Card>
      <h2 className="text-lg font-semibold">Your level</h2>
      <ol aria-label="Levels" className="mt-4 grid grid-cols-6 gap-1">
        {LEVELS.map((code, i) => (
          <li
            key={code}
            aria-current={i === current ? "step" : undefined}
            className={`rounded-lg py-2 text-center text-sm font-semibold ${
              i === current
                ? "bg-teal-700 text-white"
                : i < current
                  ? "bg-teal-100 text-teal-900"
                  : "bg-stone-100 text-stone-500"
            }`}
          >
            {code}
          </li>
        ))}
      </ol>

      <div className="mt-5">
        <div className="flex justify-between text-xs text-stone-600">
          <span>Messages with mistakes, last {level.sessions_needed} sessions at {level.current_level}</span>
          <span className="font-semibold text-stone-800">{percent === null ? "–" : `${percent}%`}</span>
        </div>
        <div
          className="relative mt-1 h-3 overflow-hidden rounded-full bg-stone-200"
          role="meter"
          aria-label="Average share of messages with mistakes"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent ?? undefined}
          aria-valuetext={percent === null ? "No sessions yet" : `${percent}%`}
        >
          <div className="absolute inset-y-0 left-0 bg-emerald-200" style={{ width: `${level.up_threshold * 100}%` }} />
          <div className="absolute inset-y-0 right-0 bg-rose-200" style={{ width: `${(1 - level.down_threshold) * 100}%` }} />
          {percent !== null && (
            <div className="absolute inset-y-0 w-1 -translate-x-1/2 rounded bg-stone-900" style={{ left: `${Math.min(100, Math.max(0, percent))}%` }} />
          )}
        </div>
        <p className="mt-2 text-sm text-stone-700">
          {needed > 0
            ? `${needed} more ${needed === 1 ? "session" : "sessions"} at ${level.current_level} (with at least 3 messages each) before a level suggestion.`
            : level.direction === "up"
              ? `Under ${level.up_threshold * 100}%: you're ready to move up.`
              : level.direction === "down"
                ? `Over ${level.down_threshold * 100}%: an easier level may help.`
                : `Between ${level.up_threshold * 100}% and ${level.down_threshold * 100}%: ${level.current_level} suits you right now.`}
        </p>
      </div>
    </Card>
  );
}

function WeeklySessions({ weeks }: { weeks: Stats["sessions_per_week"] }) {
  const max = Math.max(1, ...weeks.map((w) => w.sessions));
  return (
    <Card>
      <h2 className="text-lg font-semibold">Sessions per week</h2>
      <ol className="mt-4 flex h-40 items-end gap-2">
        {weeks.map((w) => {
          const label = `Week of ${shortDate.format(parseDay(w.week_start))}`;
          return (
            <li key={w.week_start} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
              <span className="sr-only">{`${label}: ${w.sessions} ${w.sessions === 1 ? "session" : "sessions"}`}</span>
              <span aria-hidden className="text-xs text-stone-600">{w.sessions || ""}</span>
              <div
                aria-hidden
                className="w-full rounded-t bg-teal-600"
                style={{ height: `${(w.sessions / max) * 100}%`, minHeight: w.sessions ? 4 : 0 }}
              />
              <span aria-hidden className="text-[10px] whitespace-nowrap text-stone-500">
                {shortDate.format(parseDay(w.week_start))}
              </span>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function ErrorTypes({ counts }: { counts: Stats["error_types"] }) {
  const max = Math.max(1, ...counts.map((c) => c.count));
  return (
    <Card>
      <h2 className="text-lg font-semibold">Most common mistakes</h2>
      {counts.length === 0 ? (
        <p className="mt-3 text-stone-600">No mistakes found yet.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {counts.map((c) => (
            <li key={c.error_type}>
              <div className="flex justify-between text-sm">
                <span className="text-stone-800">{ERROR_LABELS[c.error_type]}</span>
                <span className="font-semibold text-stone-900">{c.count}</span>
              </div>
              <div aria-hidden className="mt-1 h-2 overflow-hidden rounded-full bg-stone-100">
                <div className="h-full rounded-full bg-amber-400" style={{ width: `${(c.count / max) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Trend({ points }: { points: Stats["error_rate_trend"] }) {
  return (
    <Card>
      <h2 className="text-lg font-semibold">Mistakes per session</h2>
      <p className="mt-1 text-sm text-stone-600">
        Share of your messages with at least one mistake, in your last {points.length || ""} sessions. Lower is better.
      </p>
      {points.length === 0 ? (
        <p className="mt-3 text-stone-600">No finished sessions yet.</p>
      ) : (
        <ol className="mt-4 flex h-40 items-end gap-2">
          {points.map((p) => {
            const percent = Math.round(p.error_rate * 100);
            const when = shortDate.format(new Date(p.ended_at));
            return (
              <li
                key={p.session_id}
                className="flex h-full flex-1 flex-col items-center justify-end gap-1"
                title={`${p.scenario_title} (${p.cefr_level}), ${when}: ${percent}%`}
              >
                <span className="sr-only">{`${p.scenario_title}, ${when}, ${p.cefr_level}: ${percent}% of messages had mistakes`}</span>
                <span aria-hidden className="text-xs text-stone-600">{percent}%</span>
                <div
                  aria-hidden
                  className={`w-full rounded-t ${percent <= 20 ? "bg-emerald-500" : percent >= 60 ? "bg-rose-500" : "bg-amber-400"}`}
                  style={{ height: `${Math.max(percent, 2)}%` }}
                />
                <span aria-hidden className="text-[10px] whitespace-nowrap text-stone-500">{when}</span>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
