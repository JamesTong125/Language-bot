interface Props {
  canListen: boolean;
  canSpeak: boolean;
  listening: boolean;
  handsFree: boolean;
  onHandsFreeChange: (on: boolean) => void;
  /** An error or notice for the learner, e.g. microphone blocked. */
  message: string | null;
}

/** The hands-free switch, listening status, and fallback notes under the message box. */
export function VoiceControls({
  canListen,
  canSpeak,
  listening,
  handsFree,
  onHandsFreeChange,
  message,
}: Props) {
  let fallback: string | null = null;
  if (!canListen && !canSpeak) {
    fallback = "Voice isn't available in this browser, so type your replies.";
  } else if (!canListen) {
    fallback =
      "Voice input isn't available in this browser (try Chrome, Edge, or Safari). Type your replies; you can still listen to any message.";
  } else if (!canSpeak) {
    fallback = "Reading aloud isn't available in this browser. You can still speak your replies.";
  }

  return (
    <div className="space-y-2">
      {canListen && canSpeak && (
        <label className="flex w-fit cursor-pointer items-center gap-2 text-sm text-stone-700">
          <input
            type="checkbox"
            role="switch"
            aria-checked={handsFree}
            checked={handsFree}
            onChange={(e) => onHandsFreeChange(e.target.checked)}
            className="size-4 accent-teal-700"
          />
          Hands-free: read replies aloud and listen for my answer
        </label>
      )}
      <p aria-live="polite" className="text-sm">
        {listening && (
          <span className="inline-flex items-center gap-2 font-medium text-rose-700">
            <span aria-hidden className="size-2 animate-pulse rounded-full bg-rose-600" />
            Listening… speak now
          </span>
        )}
        {!listening && message && <span className="text-amber-900">{message}</span>}
      </p>
      {fallback && <p className="text-xs text-stone-500">{fallback}</p>}
    </div>
  );
}
