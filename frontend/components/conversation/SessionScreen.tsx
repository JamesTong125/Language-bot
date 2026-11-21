"use client";

import { AppShell } from "@/components/AppShell";
import { ConversationView } from "@/components/conversation/ConversationView";

export function SessionScreen({ sessionId }: { sessionId: number }) {
  return (
    <AppShell>
      {({ languages }) => {
        // BCP 47 tags (e.g. es-ES) pick the speech recognition and voice language.
        const tags = Object.fromEntries(languages.languages.map((l) => [l.code, l.speech_tag]));
        return <ConversationView sessionId={sessionId} speechTags={tags} />;
      }}
    </AppShell>
  );
}
