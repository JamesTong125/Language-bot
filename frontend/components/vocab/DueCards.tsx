"use client";

import Link from "next/link";

import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";

/** A prompt on the home page when cards are due. Shows nothing otherwise, or on error. */
export function DueCards() {
  const [state] = useAsync(() => api.reviewQueue(1));
  if (state.status !== "ready" || state.data.due_count === 0) return null;
  const count = state.data.due_count;
  return (
    <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-teal-200 bg-teal-50 p-5">
      <p className="text-teal-950">
        <span className="font-semibold">
          {count} {count === 1 ? "card is" : "cards are"} due
        </span>{" "}
        for review.
      </p>
      <Link
        href="/review"
        className="inline-flex min-h-11 items-center rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
      >
        Review now
      </Link>
    </section>
  );
}
