"use client";

import { AppShell } from "@/components/AppShell";
import { ConversationView } from "@/components/conversation/ConversationView";

export function SessionScreen({ sessionId }: { sessionId: number }) {
  return <AppShell>{() => <ConversationView sessionId={sessionId} />}</AppShell>;
}
