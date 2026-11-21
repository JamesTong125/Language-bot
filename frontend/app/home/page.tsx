"use client";

import Link from "next/link";

import { AppShell, languageName } from "@/components/AppShell";
import { ScenarioPicker } from "@/components/ScenarioPicker";
import { HomeLevelSuggestion } from "@/components/progress/HomeLevelSuggestion";
import { DueCards } from "@/components/vocab/DueCards";
import { Card } from "@/components/ui";

export default function HomePage() {
  return (
    <AppShell>
      {({ profile, languages, reload }) => {
        const current = profile.current;
        if (!current) return null;
        return (
          <div className="space-y-8">
            <Card>
              <h1 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
                Currently practising
              </h1>
              <p className="mt-2 text-xl font-semibold">
                {languageName(languages, current.target_language)}{" "}
                <span className="ml-1 rounded-md bg-teal-100 px-2 py-0.5 text-sm text-teal-900">
                  {current.cefr_level}
                </span>
              </p>
              {current.goals && <p className="mt-2 text-stone-700">Goal: {current.goals}</p>}
              <Link
                href="/profile"
                className="mt-4 inline-block text-sm font-semibold text-teal-800 underline"
              >
                Change language or level
              </Link>
            </Card>
            <HomeLevelSuggestion key={current.updated_at} profile={profile} onChanged={reload} />
            <DueCards key={current.id} />
            <section aria-labelledby="scenarios-heading">
              <h2 id="scenarios-heading" className="text-xl font-bold">
                Pick a scenario
              </h2>
              <p className="mt-1 mb-4 text-stone-600">
                Your partner speaks {languageName(languages, current.target_language)} at your
                level.
              </p>
              <ScenarioPicker key={current.id} learnerLevel={current.cefr_level} />
            </section>
          </div>
        );
      }}
    </AppShell>
  );
}
