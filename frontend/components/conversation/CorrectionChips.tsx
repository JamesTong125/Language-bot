"use client";

import { useId, useState } from "react";

import type { Correction, ErrorType } from "@/lib/types";

const TYPE_LABELS: Record<ErrorType, string> = {
  grammar: "Grammar",
  vocabulary: "Vocabulary",
  spelling: "Spelling",
  word_order: "Word order",
  conjugation: "Conjugation",
  register: "Tone",
};

const SEVERITY_STYLES: Record<Correction["severity"], string> = {
  1: "border-sky-200 bg-sky-50 text-sky-900",
  2: "border-amber-300 bg-amber-50 text-amber-950",
  3: "border-rose-300 bg-rose-50 text-rose-950",
};

const SEVERITY_LABELS: Record<Correction["severity"], string> = {
  1: "small slip",
  2: "mistake",
  3: "hard to understand",
};

interface Props {
  corrections: Correction[];
  checking: boolean;
  targetLang: string;
  nativeLang: string;
}

/** Correction chips under a learner message. Each chip expands to show the fix and why. */
export function CorrectionChips({ corrections, checking, targetLang, nativeLang }: Props) {
  if (checking) {
    return (
      <p role="status" className="mt-1 text-right text-xs text-stone-500">
        Checking your message…
      </p>
    );
  }
  if (corrections.length === 0) return null;
  return (
    <ul aria-label="Corrections" className="mt-1.5 flex flex-col items-end gap-1.5">
      {corrections.map((c) => (
        <Chip key={c.id} correction={c} targetLang={targetLang} nativeLang={nativeLang} />
      ))}
    </ul>
  );
}

function Chip({
  correction: c,
  targetLang,
  nativeLang,
}: {
  correction: Correction;
  targetLang: string;
  nativeLang: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <li className={`max-w-[85%] rounded-xl border text-sm sm:max-w-[75%] ${SEVERITY_STYLES[c.severity]}`}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-9 w-full flex-wrap items-baseline gap-x-2 rounded-xl px-3 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-teal-700"
      >
        <span className="shrink-0 text-xs font-semibold uppercase tracking-wide opacity-80">
          {TYPE_LABELS[c.error_type]}
        </span>
        <span lang={targetLang} className="break-words">
          <span className="line-through opacity-70">{c.original}</span>
          {" → "}
          <span className="font-semibold">{c.corrected || "(remove)"}</span>
        </span>
        <span aria-hidden className="ml-auto shrink-0 pl-1 text-xs">
          {open ? "▲" : "▼"}
        </span>
        <span className="sr-only">{`, ${SEVERITY_LABELS[c.severity]}. ${open ? "Hide" : "Show"} explanation`}</span>
      </button>
      <div id={panelId} hidden={!open} className="border-t border-current/15 px-3 py-2">
        <p lang={nativeLang} className="text-stone-800">
          {c.explanation}
        </p>
      </div>
    </li>
  );
}
