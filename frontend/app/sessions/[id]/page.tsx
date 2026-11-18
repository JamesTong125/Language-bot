import { Suspense } from "react";

import { SessionScreen } from "@/components/conversation/SessionScreen";
import { Spinner } from "@/components/ui";

// Params are runtime data under Cache Components, so read them inside Suspense.
export default function SessionPage({ params }: PageProps<"/sessions/[id]">) {
  return (
    <Suspense fallback={<Spinner label="Loading conversation" />}>
      {params.then(({ id }) => (
        <SessionScreen sessionId={Number(id)} />
      ))}
    </Suspense>
  );
}
