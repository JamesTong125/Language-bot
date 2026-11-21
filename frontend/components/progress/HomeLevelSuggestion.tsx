"use client";

import { LevelSuggestion } from "@/components/progress/LevelSuggestion";
import { api } from "@/lib/api";
import type { ProfileResponse } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

/** The level suggestion on the home page. Shows nothing while loading or on error. */
export function HomeLevelSuggestion({ profile, onChanged }: { profile: ProfileResponse; onChanged: () => void }) {
  const [state] = useAsync(() => api.stats());
  if (state.status !== "ready") return null;
  return <LevelSuggestion level={state.data.level} profile={profile} onChanged={onChanged} />;
}
