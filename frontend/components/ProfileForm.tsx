"use client";

import { type FormEvent, useState } from "react";

import { Alert, Button, inputClass } from "@/components/ui";
import type { CefrLevel, LanguagesResponse, ProfileResponse, ProfileUpdate } from "@/lib/types";

const levelDescriptions: Record<CefrLevel, string> = {
  A1: "Beginner",
  A2: "Elementary",
  B1: "Intermediate",
  B2: "Upper intermediate",
  C1: "Advanced",
  C2: "Proficient",
};

interface Props {
  options: LanguagesResponse;
  profile: ProfileResponse;
  submitLabel: string;
  onSubmit: (update: ProfileUpdate) => Promise<void>;
}

export function ProfileForm({ options, profile, submitLabel, onSubmit }: Props) {
  const [nativeLanguage, setNativeLanguage] = useState(profile.native_language ?? "");
  const [targetLanguage, setTargetLanguage] = useState(profile.current?.target_language ?? "");
  const [level, setLevel] = useState<CefrLevel>(profile.current?.cefr_level ?? "A1");
  const [goals, setGoals] = useState(profile.current?.goals ?? "");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Picking a language that already has a profile loads its saved level and goals.
  function chooseTarget(code: string) {
    setTargetLanguage(code);
    const existing = profile.profiles.find((p) => p.target_language === code);
    // A language without a profile starts fresh, so goals from another language don't carry over.
    setLevel(existing?.cefr_level ?? "A1");
    setGoals(existing?.goals ?? "");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (nativeLanguage === targetLanguage) {
      setError("Pick a target language that is different from your native language.");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({
        native_language: nativeLanguage,
        target_language: targetLanguage,
        cefr_level: level,
        goals: goals.trim() || null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your profile");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <label className="block text-sm font-medium text-stone-700">
        I speak
        <select
          required
          value={nativeLanguage}
          onChange={(e) => setNativeLanguage(e.target.value)}
          className={inputClass}
        >
          <option value="" disabled>
            Choose your native language
          </option>
          {options.languages.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.name} ({lang.native_name})
            </option>
          ))}
        </select>
      </label>

      <label className="block text-sm font-medium text-stone-700">
        I want to practise
        <select
          required
          value={targetLanguage}
          onChange={(e) => chooseTarget(e.target.value)}
          className={inputClass}
        >
          <option value="" disabled>
            Choose a target language
          </option>
          {options.languages
            .filter((lang) => lang.code !== nativeLanguage)
            .map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name} ({lang.native_name})
              </option>
            ))}
        </select>
      </label>

      <fieldset>
        <legend className="text-sm font-medium text-stone-700">My level</legend>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {options.cefr_levels.map((code) => (
            <label
              key={code}
              className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm has-checked:border-teal-700 has-checked:bg-teal-50 has-focus-visible:outline-2 has-focus-visible:outline-teal-700"
            >
              <input
                type="radio"
                name="cefr_level"
                value={code}
                checked={level === code}
                onChange={() => setLevel(code)}
                className="accent-teal-700"
              />
              <span>
                <span className="font-semibold">{code}</span>{" "}
                <span className="text-stone-600">{levelDescriptions[code]}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <label className="block text-sm font-medium text-stone-700">
        Goals <span className="font-normal text-stone-500">(optional)</span>
        <textarea
          value={goals}
          maxLength={1000}
          rows={3}
          onChange={(e) => setGoals(e.target.value)}
          placeholder="For example: get by on a trip to Madrid, or prepare for job interviews"
          className={inputClass}
        />
      </label>

      {error && <Alert>{error}</Alert>}
      <Button type="submit" disabled={submitting || !nativeLanguage || !targetLanguage} className="w-full sm:w-auto">
        {submitting ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
