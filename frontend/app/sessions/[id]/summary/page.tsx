import { Suspense } from "react";

import { SessionSummaryScreen } from "@/components/conversation/SessionSummary";
import { Spinner } from "@/components/ui";

export default function SummaryPage({ params }: PageProps<"/sessions/[id]/summary">) {
  return (
    <Suspense fallback={<Spinner label="Loading summary" />}>
      {params.then(({ id }) => (
        <SessionSummaryScreen sessionId={Number(id)} />
      ))}
    </Suspense>
  );
}
