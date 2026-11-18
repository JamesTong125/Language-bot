"use client";

import { AppShell, languageName } from "@/components/AppShell";
import { DeckView } from "@/components/vocab/DeckView";

export default function VocabPage() {
  return (
    <AppShell>
      {({ profile, languages }) => (
        <div className="space-y-6">
          <h1 className="text-2xl font-bold">
            Vocabulary{" "}
            <span className="text-base font-normal text-stone-600">
              {languageName(languages, profile.current?.target_language ?? null)}
            </span>
          </h1>
          <DeckView
            key={profile.current?.id}
            targetLang={profile.current?.target_language ?? "en"}
            nativeLang={profile.native_language ?? "en"}
          />
        </div>
      )}
    </AppShell>
  );
}
