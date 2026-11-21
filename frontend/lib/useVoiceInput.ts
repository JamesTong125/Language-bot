"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  createRecognition,
  isFatalRecognitionError,
  recognitionErrorMessage,
  type SpeechRecognitionLike,
} from "@/lib/speech";

export interface ListenResult {
  /** The final transcript, or "" if nothing was heard. */
  text: string;
  /** The recognition error code, if one ended the attempt. */
  error: string | null;
}

interface Options {
  lang: string;
  /** Live transcript while the learner speaks. */
  onInterim: (text: string) => void;
}

/**
 * One utterance at a time: ``listen()`` resolves when the learner stops speaking.
 * ``error`` holds a message for the learner when voice input can't be used.
 */
export function useVoiceInput({ lang, onInterim }: Options) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active = useRef<SpeechRecognitionLike | null>(null);
  const interimRef = useRef(onInterim);

  useEffect(() => {
    interimRef.current = onInterim;
  }, [onInterim]);

  const stop = useCallback(() => {
    active.current?.stop();
  }, []);

  const cancel = useCallback(() => {
    const recognition = active.current;
    active.current = null;
    recognition?.abort();
    setListening(false);
  }, []);

  const listen = useCallback((): Promise<ListenResult> => {
    active.current?.abort();
    const recognition = createRecognition(lang);
    if (!recognition) return Promise.resolve({ text: "", error: "not-supported" });
    active.current = recognition;
    setError(null);
    setListening(true);

    return new Promise((resolve) => {
      let finalText = "";
      let lastError: string | null = null;
      recognition.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) finalText += result[0].transcript;
          else interim += result[0].transcript;
        }
        interimRef.current((finalText + interim).trim());
      };
      recognition.onerror = (event) => {
        lastError = event.error;
        const message = recognitionErrorMessage(event.error);
        if (message) setError(message);
      };
      recognition.onend = () => {
        if (active.current === recognition) active.current = null;
        setListening(false);
        resolve({ text: finalText.trim(), error: lastError });
      };
      try {
        recognition.start();
      } catch {
        // start() throws if a previous session is still closing.
        active.current = null;
        setListening(false);
        resolve({ text: "", error: "busy" });
      }
    });
  }, [lang]);

  // Stop the microphone when the page goes away.
  useEffect(() => () => active.current?.abort(), []);

  return { listening, error, setError, listen, stop, cancel, isFatal: isFatalRecognitionError };
}
