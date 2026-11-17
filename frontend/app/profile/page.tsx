"use client";

import { useState } from "react";

import { AccountDataCard } from "@/components/AccountDataCard";
import { AppShell, languageName } from "@/components/AppShell";
import { ProfileForm } from "@/components/ProfileForm";
import { Alert, Card } from "@/components/ui";
import { api } from "@/lib/api";

export default function ProfilePage() {
  const [saved, setSaved] = useState(false);

  return (
    <AppShell>
      {({ profile, languages, reload }) => (
        <div className="space-y-6">
          <h1 className="text-2xl font-bold">Profile</h1>
          <p className="break-all text-stone-600">Signed in as {profile.email}</p>

          <Card>
            <h2 className="text-lg font-semibold">Language and level</h2>
            {profile.profiles.length > 1 && (
              <p className="mt-1 text-sm text-stone-600">
                Your languages:{" "}
                {profile.profiles
                  .map((p) => `${languageName(languages, p.target_language)} (${p.cefr_level})`)
                  .join(", ")}
                . Each keeps its own history.
              </p>
            )}
            <div className="mt-4 space-y-4">
              {saved && <Alert tone="success">Profile saved.</Alert>}
              <ProfileForm
                key={profile.current?.updated_at}
                options={languages}
                profile={profile}
                submitLabel="Save changes"
                onSubmit={async (update) => {
                  setSaved(false);
                  await api.updateProfile(update);
                  setSaved(true);
                  reload();
                }}
              />
            </div>
          </Card>

          <AccountDataCard />
        </div>
      )}
    </AppShell>
  );
}
