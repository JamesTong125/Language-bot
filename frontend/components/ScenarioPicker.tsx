"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useLayoutEffect, useState } from "react";

import { Alert, Button, ErrorState, inputClass, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { CefrLevel, Scenario, ScenarioList } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const LEVELS: CefrLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];
const MAX_DESCRIPTION = 300;

function difficultyLabel(scenario: CefrLevel, learner: CefrLevel): string {
  const gap = LEVELS.indexOf(scenario) - LEVELS.indexOf(learner);
  if (gap <= -1) return "Easy for you";
  if (gap === 0) return "Your level";
  if (gap === 1) return "A stretch";
  return "Challenging";
}

export function ScenarioPicker({ learnerLevel }: { learnerLevel: CefrLevel }) {
  const [state, reload] = useAsync(() => api.scenarios());
  if (state.status === "loading") return <Spinner label="Loading scenarios" />;
  if (state.status === "error") return <ErrorState message={state.error.message} onRetry={reload} />;
  return <Picker initial={state.data} learnerLevel={learnerLevel} />;
}

function Picker({ initial, learnerLevel }: { initial: ScenarioList; learnerLevel: CefrLevel }) {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<Scenario[]>(initial.scenarios);
  const [newId, setNewId] = useState<number | null>(null);
  const [startingId, setStartingId] = useState<number | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [isPrivate, setIsPrivate] = useState(false);

  // Next.js keeps this page mounted but hidden after navigating away (React Activity).
  // Clear the "starting" state when it's hidden, so the buttons work again on return.
  useLayoutEffect(() => {
    return () => {
      setStartingId(null);
      setStartError(null);
    };
  }, []);

  async function start(scenario: Scenario) {
    setStartingId(scenario.id);
    setStartError(null);
    try {
      const session = await api.startSession(scenario.id, isPrivate);
      router.push(`/sessions/${session.id}`);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Could not start the conversation");
      setStartingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <CreateScenario
        onCreated={(scenario) => {
          setScenarios((prev) => [scenario, ...prev]);
          setNewId(scenario.id);
        }}
      />
      {initial.private_available && (
        <label className="flex w-fit cursor-pointer items-start gap-2 rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-700">
          <input
            type="checkbox"
            checked={isPrivate}
            onChange={(e) => setIsPrivate(e.target.checked)}
            className="mt-0.5 size-4 accent-teal-700"
          />
          <span>
            <span className="font-semibold text-stone-900">Private session</span>
            <span className="block text-stone-600">
              Use the private model for everything in the session. Nothing is sent to cloud AI
              providers.
            </span>
          </span>
        </label>
      )}
      {startError && <Alert>{startError}</Alert>}
      {scenarios.length === 0 ? (
        <p className="py-8 text-center text-stone-600">No scenarios are available yet.</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {scenarios.map((scenario) => (
            <li key={scenario.id}>
              <article
                className={`flex h-full flex-col rounded-2xl border bg-white p-5 shadow-sm ${
                  scenario.id === newId ? "border-teal-600 ring-2 ring-teal-600/30" : "border-stone-200"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-lg font-semibold text-stone-900">{scenario.title}</h3>
                  <span className="flex shrink-0 gap-1">
                    {scenario.is_custom && (
                      <span className="rounded-md bg-teal-50 px-2 py-0.5 text-xs font-semibold text-teal-900">
                        Custom
                      </span>
                    )}
                    <span
                      className="rounded-md bg-stone-100 px-2 py-0.5 text-xs font-semibold text-stone-700"
                      title={`Scenario difficulty ${scenario.cefr_level}`}
                    >
                      {scenario.cefr_level}
                    </span>
                  </span>
                </div>
                <p className="mt-1 text-xs font-medium text-teal-800">
                  {difficultyLabel(scenario.cefr_level, learnerLevel)}
                </p>
                <p className="mt-2 text-sm text-stone-700">{scenario.description}</p>
                <p className="mt-2 text-sm text-stone-600">
                  <span className="font-medium text-stone-800">Goal:</span> {scenario.goal}
                </p>
                <Button
                  className="mt-4 self-start"
                  onClick={() => start(scenario)}
                  disabled={startingId !== null}
                  aria-label={`Start ${scenario.title}`}
                >
                  {startingId === scenario.id ? "Starting…" : "Start"}
                </Button>
              </article>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CreateScenario({ onCreated }: { onCreated: (scenario: Scenario) => void }) {
  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const scenario = await api.createScenario(description);
      onCreated(scenario);
      setDescription("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the scenario");
    } finally {
      setCreating(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex w-full min-h-14 items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-stone-300 bg-white px-4 py-3 text-sm font-semibold text-teal-800 hover:border-teal-600 hover:bg-teal-50 focus-visible:outline-2 focus-visible:outline-teal-700"
      >
        <span aria-hidden className="text-lg">+</span> Create your own scenario
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl border border-teal-200 bg-teal-50/50 p-5">
      <label className="block text-sm font-medium text-stone-800">
        Describe a situation you want to practise
        <textarea
          autoFocus
          required
          minLength={8}
          maxLength={MAX_DESCRIPTION}
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="For example: returning a rental car that got a scratch, or chatting with a neighbour about a noisy party"
          className={inputClass}
        />
        <span className="mt-1 block text-xs font-normal text-stone-500">
          The AI writes the scene, the character, and a goal at your level. {description.length}/
          {MAX_DESCRIPTION}
        </span>
      </label>
      {error && <Alert>{error}</Alert>}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={creating || description.trim().length < 8}>
          {creating ? "Building your scene…" : "Create scenario"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={creating}
          onClick={() => {
            setOpen(false);
            setError(null);
          }}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}
