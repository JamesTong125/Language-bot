"use client";

import { useLayoutEffect, useState } from "react";

import { AppShell, languageName } from "@/components/AppShell";
import { ReviewFlow } from "@/components/vocab/ReviewFlow";

export default function ReviewPage() {
  // Next.js keeps this page mounted but hidden after navigating away. Start a fresh
  // review (and reload due cards) each time it's shown again.
  const [run, setRun] = useState(0);
  useLayoutEffect(() => () => setRun((n) => n + 1), []);

  return (
    <AppShell>
      {({ profile, languages }) => (
        <div className="space-y-6">
          <h1 className="text-2xl font-bold">
            Review{" "}
            <span className="text-base font-normal text-stone-600">
              {languageName(languages, profile.current?.target_language ?? null)}
            </span>
          </h1>
          <ReviewFlow
            key={`${run}-${profile.current?.id}`}
            targetLang={profile.current?.target_language ?? "en"}
            nativeLang={profile.native_language ?? "en"}
          />
        </div>
      )}
    </AppShell>
  );
}
