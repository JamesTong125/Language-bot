"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Alert, Button, Card, inputClass } from "@/components/ui";
import { api } from "@/lib/api";

/** Data export and account deletion. */
export function AccountDataCard() {
  const router = useRouter();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [password, setPassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function exportData() {
    setExporting(true);
    setExportError(null);
    try {
      const blob = await api.exportAccount();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "immersion-buddy-export.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteAccount(password);
      // Pages stay mounted after navigation; clear the form so it isn't stuck on return.
      setDeleting(false);
      setConfirmingDelete(false);
      setPassword("");
      router.replace("/");
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Could not delete your account");
      setDeleting(false);
    }
  }

  return (
    <Card>
      <h2 className="text-lg font-semibold">Your data</h2>
      <p className="mt-1 text-sm text-stone-600">
        Download everything we store about you as a JSON file.
      </p>
      <div className="mt-4 space-y-3">
        {exportError && <Alert>{exportError}</Alert>}
        <Button variant="secondary" onClick={exportData} disabled={exporting}>
          {exporting ? "Preparing…" : "Export my data"}
        </Button>
      </div>

      <hr className="my-6 border-stone-200" />

      <h3 className="font-semibold text-red-800">Delete account</h3>
      <p className="mt-1 text-sm text-stone-600">
        This permanently deletes your account, profiles, and all practice history. It cannot be
        undone.
      </p>
      {!confirmingDelete ? (
        <Button variant="secondary" className="mt-4" onClick={() => setConfirmingDelete(true)}>
          Delete my account…
        </Button>
      ) : (
        <form onSubmit={deleteAccount} className="mt-4 space-y-3">
          <label className="block text-sm font-medium text-stone-700">
            Enter your password to confirm
            <input
              type="password"
              autoComplete="current-password"
              required
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
          </label>
          {deleteError && <Alert>{deleteError}</Alert>}
          <div className="flex flex-wrap gap-3">
            <Button type="submit" variant="danger" disabled={deleting || !password}>
              {deleting ? "Deleting…" : "Permanently delete"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setConfirmingDelete(false);
                setPassword("");
                setDeleteError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
