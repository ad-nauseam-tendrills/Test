"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { Card, CardLabel } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { InstagramAccount, User } from "@/types";
import { formatDateTime, formatNumber } from "@/lib/utils";

function SettingsContent() {
  const { user, refreshUser } = useAuth();
  const [accounts, setAccounts] = useState<InstagramAccount[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadAccounts() {
    try {
      const list = await api.get<InstagramAccount[]>("/accounts");
      setAccounts(list);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to load accounts.");
    }
  }

  useEffect(() => {
    loadAccounts();
  }, []);

  async function toggleArtworkIntegrity() {
    if (!user) return;
    setBusy(true);
    try {
      const updated = await api.put<User>("/settings", {
        artwork_integrity_enabled: !user.artwork_integrity_enabled,
      });
      refreshUser(updated);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to update setting.");
    } finally {
      setBusy(false);
    }
  }

  async function connectAccount() {
    setBusy(true);
    setMessage(null);
    try {
      await api.post<InstagramAccount>("/accounts/connect", { provider: "mock" });
      await loadAccounts();
      setMessage("Instagram account connected.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to connect account.");
    } finally {
      setBusy(false);
    }
  }

  async function disconnectAccount(accountId: string) {
    setBusy(true);
    setMessage(null);
    try {
      await api.post<InstagramAccount>(`/accounts/${accountId}/disconnect`);
      await loadAccounts();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to disconnect account.");
    } finally {
      setBusy(false);
    }
  }

  async function importPosts(accountId: string) {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.post<{ imported_count: number; skipped_count: number }>(
        `/accounts/${accountId}/import`
      );
      setMessage(`Imported ${result.imported_count} new posts (${result.skipped_count} already up to date).`);
      await loadAccounts();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to import posts.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-8">
      <div>
        <p className="font-display text-2xl text-stone-900">Settings</p>
      </div>

      {message && <p className="text-sm text-stone-500">{message}</p>}

      <Card>
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="text-sm font-medium text-stone-800">Artwork Integrity mode</p>
            <p className="mt-1 text-sm text-stone-500">
              When on, optimization only ever applies photographic preparation — exposure, white
              balance, contrast, highlight/shadow recovery, mild saturation correction, sharpening,
              resize, crop, and perspective correction. It never repaints, alters shapes or faces, or
              changes composition beyond cropping.
            </p>
          </div>
          <button
            onClick={toggleArtworkIntegrity}
            disabled={busy || !user}
            className={`relative h-7 w-12 flex-shrink-0 rounded-full transition-colors ${
              user?.artwork_integrity_enabled ? "bg-stone-900" : "bg-stone-300"
            }`}
          >
            <span
              className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-transform ${
                user?.artwork_integrity_enabled ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </Card>

      <Card>
        <CardLabel>Instagram connection</CardLabel>
        <div className="mt-4 flex flex-col gap-4">
          {accounts.length === 0 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-stone-500">No account connected.</p>
              <Button onClick={connectAccount} disabled={busy}>
                Connect (mock)
              </Button>
            </div>
          )}
          {accounts.map((account) => (
            <div key={account.id} className="flex items-center justify-between border-t border-stone-100 pt-4 first:border-none first:pt-0">
              <div>
                <p className="text-sm font-medium text-stone-800">
                  @{account.username}{" "}
                  <span className="ml-1 text-xs text-stone-400">
                    {account.is_active ? "Connected" : "Disconnected"} · {account.provider}
                  </span>
                </p>
                <p className="mt-0.5 text-xs text-stone-500">
                  {formatNumber(account.follower_count)} followers · last synced{" "}
                  {account.last_synced_at ? formatDateTime(account.last_synced_at) : "never"}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => importPosts(account.id)} disabled={busy}>
                  Import history
                </Button>
                {account.is_active && (
                  <Button variant="ghost" onClick={() => disconnectAccount(account.id)} disabled={busy}>
                    Disconnect
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardLabel>About the mock integration</CardLabel>
        <p className="mt-2 text-sm text-stone-500">
          This development build uses a mock Instagram provider that generates realistic, synthetic
          historical post data locally — no real Meta credentials are required and Instagram is never
          scraped. A real Meta Graph API integration can be enabled later by an administrator by
          setting <code className="rounded bg-stone-100 px-1 py-0.5 text-xs">INSTAGRAM_PROVIDER=meta</code> and
          configuring Meta app credentials on the backend.
        </p>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsContent />
    </RequireAuth>
  );
}
