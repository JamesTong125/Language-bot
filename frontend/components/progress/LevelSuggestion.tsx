"use client";

import { useState } from "react";

import { Alert, Button } from "@/components/ui";
import { api } from "@/lib/api";
import type { LevelProgress, ProfileResponse } from "@/lib/types";

function dismissKey(profileId: number, level: LevelProgress): string {
  // A new suggestion (based on newer sessions) shows again even after a dismissal.
  return `level-suggestion-dismissed:${profileId}:${Math.max(...level.session_ids)}`;
}

function readDismissed(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

interface Props {
  level: LevelProgress;
  profile: ProfileResponse;
  /** Called after the learner accepts, so the page can reload profile and stats. */
  onChanged: () => void;
}

/** Suggests moving up or down a level. Nothing changes until the learner confirms. */
export function LevelSuggestion({ level, profile, onChanged }: Props) {
  const current = profile.current;
  const key = current && level.session_ids.length ? dismissKey(current.id, level) : "";
  const [dismissed, setDismissed] = useState(() => (key ? readDismissed(key) : false));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!current || !profile.native_language || !level.direction || !level.suggested_level || dismissed) {
    return null;
  }
  const percent = Math.round((level.average_error_rate ?? 0) * 100);
  const up = level.direction === "up";

  async function accept() {
    if (!current || !profile.native_language || !level.suggested_level) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateProfile({
        native_language: profile.native_language,
        target_language: current.target_language,
        cefr_level: level.suggested_level,
        goals: current.goals,
      });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't change your level");
      setSaving(false);
    }
  }

  function dismiss() {
    try {
      window.localStorage.setItem(key, "1");
    } catch {
      // Private browsing may block storage; hiding it for now is enough.
    }
    setDismissed(true);
  }

  return (
    <section
      aria-label="Level suggestion"
      className={`rounded-2xl border p-5 ${up ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}
    >
      <h2 className={`font-semibold ${up ? "text-emerald-950" : "text-amber-950"}`}>
        {up
          ? `Ready for ${level.suggested_level}?`
          : `Would ${level.suggested_level} feel more comfortable?`}
      </h2>
      <p className="mt-1 text-stone-800">
        {up
          ? `In your last ${level.sessions_counted} sessions at ${level.current_level}, ${percent === 0 ? "none" : `only ${percent}%`} of your messages had mistakes. Moving up gives you longer, more natural replies.`
          : `In your last ${level.sessions_counted} sessions at ${level.current_level}, ${percent}% of your messages had mistakes. Moving down gives you shorter, simpler replies while you build confidence.`}
      </p>
      {error && (
        <div className="mt-3">
          <Alert>{error}</Alert>
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-3">
        <Button onClick={accept} disabled={saving}>
          {saving ? "Changing…" : `Switch to ${level.suggested_level}`}
        </Button>
        <Button variant="secondary" onClick={dismiss} disabled={saving}>
          Stay at {level.current_level}
        </Button>
      </div>
    </section>
  );
}
