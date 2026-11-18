interface Props {
  role: "learner" | "partner";
  text: string;
  lang: string;
  streaming?: boolean;
  pending?: boolean;
}

export function MessageBubble({ role, text, lang, streaming = false, pending = false }: Props) {
  const isLearner = role === "learner";
  return (
    <li className={`flex ${isLearner ? "justify-end" : "justify-start"}`}>
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
    </li>
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
