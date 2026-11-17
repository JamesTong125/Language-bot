"use client";

import Link from "next/link";

import { AppShell, languageName } from "@/components/AppShell";
import { Card } from "@/components/ui";

export default function HomePage() {
  return (
    <AppShell>
      {({ profile, languages }) => {
        const current = profile.current;
        if (!current) return null;
        return (
          <div className="space-y-6">
            <h1 className="text-2xl font-bold">
              Welcome back
            </h1>
            <Card>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
                Currently practising
              </h2>
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
            <Card>
              <h2 className="text-lg font-semibold">Scenarios</h2>
              <p className="mt-2 text-stone-600">
                Role-play scenarios are not available yet. They are the next part of the app to be
                built.
              </p>
            </Card>
          </div>
        );
      }}
    </AppShell>
  );
}
