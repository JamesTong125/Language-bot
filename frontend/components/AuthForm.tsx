"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useLayoutEffect, useState } from "react";

import { Alert, Button, Card, inputClass } from "@/components/ui";
import { api } from "@/lib/api";

type Mode = "login" | "register";

const copy: Record<Mode, { title: string; submit: string; switchText: string; switchHref: string; switchLink: string }> = {
  login: {
    title: "Log in",
    submit: "Log in",
    switchText: "New here?",
    switchHref: "/register",
    switchLink: "Create an account",
  },
  register: {
    title: "Create your account",
    submit: "Create account",
    switchText: "Already have an account?",
    switchHref: "/login",
    switchLink: "Log in",
  },
};

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const text = copy[mode];

  // Next.js keeps this page mounted but hidden after navigating away. Reset when hidden,
  // so returning after logout shows a usable form without the old password.
  useLayoutEffect(() => {
    return () => {
      setSubmitting(false);
      setPassword("");
      setError(null);
    };
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "register") {
        await api.register(email, password);
        router.replace("/onboarding");
      } else {
        await api.login(email, password);
        const profile = await api.getProfile();
        router.replace(profile.current ? "/home" : "/onboarding");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-12">
      <Card>
        <h1 className="text-2xl font-bold text-stone-900">{text.title}</h1>
        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <label className="block text-sm font-medium text-stone-700">
            Email
            <input
              type="email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </label>
          <label className="block text-sm font-medium text-stone-700">
            Password
            <input
              type="password"
              name="password"
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              required
              minLength={mode === "register" ? 8 : 1}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby={mode === "register" ? "password-hint" : undefined}
              className={inputClass}
            />
            {mode === "register" && (
              <span id="password-hint" className="mt-1 block text-xs font-normal text-stone-500">
                At least 8 characters.
              </span>
            )}
          </label>
          {error && <Alert>{error}</Alert>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Please wait…" : text.submit}
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-stone-600">
          {text.switchText}{" "}
          <Link href={text.switchHref} className="font-semibold text-teal-800 underline">
            {text.switchLink}
          </Link>
        </p>
      </Card>
    </main>
  );
}
