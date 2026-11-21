"use client";

import { AppShell, languageName } from "@/components/AppShell";
import { Dashboard } from "@/components/progress/Dashboard";

export default function ProgressPage() {
  return (
    <AppShell>
      {({ profile, languages, reload }) => (
        <div className="space-y-6">
          <h1 className="text-2xl font-bold">
            Progress{" "}
            <span className="text-base font-normal text-stone-600">
              {languageName(languages, profile.current?.target_language ?? null)}
            </span>
          </h1>
          {/* Re-fetch stats whenever the profile changes, e.g. after a level change. */}
          <Dashboard key={profile.current?.updated_at} profile={profile} onProfileChanged={reload} />
        </div>
      )}
    </AppShell>
  );
}
