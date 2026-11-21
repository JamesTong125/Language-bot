"use client";

import { useSyncExternalStore } from "react";

/*
 * Browser Web Speech API: SpeechRecognition (voice input) and speechSynthesis (read aloud).
 * Support varies: Chrome, Edge and Safari have recognition; Firefox doesn't. Everything here
 * fails soft, so typing always works.
 */

export interface RecognitionResultEvent {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
}

export interface RecognitionErrorEvent {
  error: string;
}

export interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type RecognitionConstructor = new () => SpeechRecognitionLike;

function recognitionConstructor(): RecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function synthesisAvailable(): boolean {
  return (
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance === "function"
  );
}

const noSubscribe = () => () => undefined;

/** True when voice input works here. False during server rendering. */
export function useRecognitionSupported(): boolean {
  return useSyncExternalStore(noSubscribe, () => recognitionConstructor() !== null, () => false);
}

/** True when reading aloud works here. False during server rendering. */
export function useSynthesisSupported(): boolean {
  return useSyncExternalStore(noSubscribe, synthesisAvailable, () => false);
}

export function createRecognition(lang: string): SpeechRecognitionLike | null {
  const Ctor = recognitionConstructor();
  if (!Ctor) return null;
  const recognition = new Ctor();
  recognition.lang = lang;
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.maxAlternatives = 1;
  return recognition;
}

/** A sentence for each recognition error, or null when it isn't worth showing. */
export function recognitionErrorMessage(error: string): string | null {
  switch (error) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone access is blocked. Allow it in your browser settings, or keep typing.";
    case "audio-capture":
      return "No microphone was found. You can keep typing.";
    case "network":
      return "Voice input needs an internet connection in this browser. You can keep typing.";
    case "language-not-supported":
      return "Your browser can't recognise speech in this language. You can keep typing.";
    case "no-speech":
    case "aborted":
      return null;
    default:
      return "Voice input stopped working. You can keep typing.";
  }
}

/** Errors that will happen again if we retry, so hands-free mode should stop. */
export function isFatalRecognitionError(error: string): boolean {
  return ["not-allowed", "service-not-allowed", "audio-capture", "network", "language-not-supported"].includes(error);
}

function pickVoice(lang: string): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  const wanted = lang.toLowerCase();
  const base = wanted.split("-")[0];
  return (
    voices.find((v) => v.lang.toLowerCase() === wanted) ??
    voices.find((v) => v.lang.toLowerCase().split(/[-_]/)[0] === base) ??
    null
  );
}

/**
 * Read text aloud. Resolves when speech ends, is cancelled, or fails; never rejects.
 * Starting a new utterance cancels the one playing.
 */
export function speak(text: string, lang: string): Promise<void> {
  if (!synthesisAvailable() || !text.trim()) return Promise.resolve();
  const synth = window.speechSynthesis;
  synth.cancel();
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    const voice = pickVoice(lang);
    if (voice) utterance.voice = voice;
    utterance.rate = 0.95;
    let settled = false;
    const done = () => {
      if (!settled) {
        settled = true;
        resolve();
      }
    };
    utterance.onend = done;
    utterance.onerror = done;
    synth.speak(utterance);
    // Some browsers never fire onend if speech is blocked; don't hang forever.
    window.setTimeout(done, Math.max(8000, text.length * 150));
  });
}

export function stopSpeaking(): void {
  if (synthesisAvailable()) window.speechSynthesis.cancel();
}
