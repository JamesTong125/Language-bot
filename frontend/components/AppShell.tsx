"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { ErrorState, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { LanguagesResponse, ProfileResponse } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

export interface AppData {
  profile: ProfileResponse;
  languages: LanguagesResponse;
  reload: () => void;
}

interface Props {
  /** Send learners without a profile to onboarding. Off for the onboarding page itself. */
  requireProfile?: boolean;
  children: (data: AppData) => ReactNode;
}

const navLinks = [
  { href: "/home", label: "Home" },
  { href: "/review", label: "Review" },
  { href: "/vocab", label: "Vocab" },
  { href: "/profile", label: "Profile" },
];

async function loadAppData(): Promise<Omit<AppData, "reload">> {
  const [profile, languages] = await Promise.all([api.getProfile(), api.languages()]);
  return { profile, languages };
}

/** Signed-in layout: loads the profile, redirects when signed out or not onboarded. */
export function AppShell({ requireProfile = true, children }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const [state, reload] = useAsync(loadAppData);
  const [loggingOut, setLoggingOut] = useState(false);

  const signedOut = state.status === "error" && state.error instanceof ApiError && state.error.status === 401;
  const needsOnboarding = requireProfile && state.status === "ready" && !state.data.profile.current;

  useEffect(() => {
    if (signedOut) router.replace("/login");
    else if (needsOnboarding) router.replace("/onboarding");
  }, [signedOut, needsOnboarding, router]);

  async function logout() {
    setLoggingOut(true);
    try {
      await api.logout();
    } finally {
      // Pages stay mounted after navigation, so reset or the button stays disabled.
      setLoggingOut(false);
      router.replace("/login");
    }
  }

  let body: ReactNode;
  if (state.status === "loading" || signedOut || needsOnboarding) {
    body = <Spinner />;
  } else if (state.status === "error") {
    body = <ErrorState message={state.error.message} onRetry={reload} />;
  } else {
    body = children({ ...state.data, reload });
  }

  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b border-stone-200 bg-white">
        <nav aria-label="Main" className="mx-auto flex max-w-3xl flex-wrap items-center gap-x-1 gap-y-2 px-4 py-3 sm:gap-x-4">
          <Link href="/home" className="mr-auto text-lg font-bold text-teal-800">
            Language learning bot
          </Link>
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
              className="rounded-md px-2 py-2 text-sm font-medium text-stone-700 hover:text-teal-800 aria-[current=page]:text-teal-800 aria-[current=page]:underline"
            >
              {link.label}
            </Link>
          ))}
          <button
            type="button"
            onClick={logout}
            disabled={loggingOut}
            className="rounded-md px-2 py-2 text-sm font-medium text-stone-700 hover:text-teal-800"
          >
            {loggingOut ? "Logging out…" : "Log out"}
          </button>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">{body}</main>
    </div>
  );
}

export function languageName(languages: LanguagesResponse, code: string | null): string {
  return languages.languages.find((lang) => lang.code === code)?.name ?? code ?? "Not set";
}
