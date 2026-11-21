import type { ReactNode } from "react";

interface Props {
  role: "learner" | "partner";
  text: string;
  lang: string;
  streaming?: boolean;
  pending?: boolean;
  /** Shows a speaker button that reads the message aloud. */
  onSpeak?: () => void;
  speaking?: boolean;
  /** Shown under the bubble, e.g. correction chips. */
  children?: ReactNode;
}

export function MessageBubble({
  role,
  text,
  lang,
  streaming = false,
  pending = false,
  onSpeak,
  speaking = false,
  children,
}: Props) {
  const isLearner = role === "learner";
  return (
    <li className={`flex flex-col ${isLearner ? "items-end" : "items-start"}`}>
      <div className={`flex w-full items-end gap-1 ${isLearner ? "flex-row-reverse" : ""}`}>
        <div
          className={`max-w-[85%] rounded-2xl px-4 py-2.5 sm:max-w-[75%] ${
            isLearner
              ? "rounded-br-sm bg-teal-700 text-white"
              : "rounded-bl-sm border border-stone-200 bg-white text-stone-900"
          } ${pending ? "opacity-70" : ""}`}
        >
          <span className="sr-only">{isLearner ? "You: " : "Partner: "}</span>
          <p lang={lang} className="whitespace-pre-wrap break-words">
            {text}
            {streaming && (
              <span aria-hidden className="ml-0.5 inline-block w-2 animate-pulse">
                ▍
              </span>
            )}
          </p>
        </div>
        {onSpeak && <SpeakButton onClick={onSpeak} speaking={speaking} />}
      </div>
      {children}
    </li>
  );
}

function SpeakButton({ onClick, speaking }: { onClick: () => void; speaking: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={speaking ? "Stop reading aloud" : "Read aloud"}
      aria-pressed={speaking}
      title={speaking ? "Stop" : "Listen"}
      className={`flex size-9 shrink-0 items-center justify-center rounded-full text-stone-500 hover:bg-stone-200 hover:text-stone-800 focus-visible:outline-2 focus-visible:outline-teal-700 ${
        speaking ? "bg-stone-200 text-teal-800" : ""
      }`}
    >
      {speaking ? (
        <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="currentColor">
          <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
      ) : (
        <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M11 5 6 9H3v6h3l5 4V5z" fill="currentColor" />
          <path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13" />
        </svg>
      )}
    </button>
  );
}

export function TypingIndicator() {
  return (
    <li className="flex justify-start">
      <div className="rounded-2xl rounded-bl-sm border border-stone-200 bg-white px-4 py-3">
        <span className="sr-only">Your partner is typing</span>
        <span aria-hidden className="flex gap-1">
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="size-2 animate-bounce rounded-full bg-stone-400"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
      </div>
    </li>
  );
}
