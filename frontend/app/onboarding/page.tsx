"use client";

import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProfileForm } from "@/components/ProfileForm";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";

export default function OnboardingPage() {
  const router = useRouter();

  return (
    <AppShell requireProfile={false}>
      {({ profile, languages }) => (
        <Card>
          <h1 className="text-2xl font-bold">Set up your practice</h1>
          <p className="mt-2 text-stone-600">
            Tell us what you speak and what you want to learn. You can change this later.
          </p>
          <div className="mt-6">
            <ProfileForm
              options={languages}
              profile={profile}
              submitLabel="Start learning"
              onSubmit={async (update) => {
                await api.updateProfile(update);
                router.replace("/home");
              }}
            />
          </div>
        </Card>
      )}
    </AppShell>
  );
}
