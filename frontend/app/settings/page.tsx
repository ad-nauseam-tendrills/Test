"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { Card, CardLabel } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { InstagramAccount, User } from "@/types";
import { formatDateTime, formatNumber } from "@/lib/utils";

function SettingsContent() {
  const { user, refreshUser } = useAuth();
  const searchParams = useSearchParams();
  const [accounts, setAccounts] = useState<InstagramAccount[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // The Meta OAuth callback bounces the browser back here with a status.
  useEffect(() => {
    const status = searchParams.get("instagram");
    const detail = searchParams.get("message");
    if (status === "connected") {
      setMessage(detail || "Instagram account connected.");
    } else if (status === "error") {
      setMessage(detail || "Could not connect that Instagram account.");
    }
  }, [searchParams]);

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
      setMessage("Mock Instagram account connected.");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to connect account.");
    } finally {
      setBusy(false);
    }
  }

  async function connectRealAccount() {
    setBusy(true);
    setMessage(null);
    try {
      const { authorize_url } = await api.get<{ authorize_url: string }>(
        "/accounts/meta/authorize-url"
      );
      // Full-page navigation: Instagram's consent screen refuses to render
      // in an iframe, and the OAuth redirect must land on the backend.
      window.location.href = authorize_url;
    } catch (err) {
      setMessage(
        err instanceof ApiError
          ? err.message
          : "Could not start the Instagram connection flow."
      );
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
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-stone-500">No account connected.</p>
              <div className="flex gap-2">
                <Button onClick={connectRealAccount} disabled={busy}>
                  Connect Instagram
                </Button>
                <Button variant="secondary" onClick={connectAccount} disabled={busy}>
                  Use demo data
                </Button>
              </div>
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
        <CardLabel>About the two connection options</CardLabel>
        <p className="mt-2 text-sm text-stone-500">
          <strong className="font-medium text-stone-700">Connect Instagram</strong> uses the official
          Meta Graph API to import your real posts and insights. It requires an Instagram
          professional (Creator or Business) account, and the backend must be configured with Meta
          app credentials. Instagram is never scraped — only documented API endpoints are used.
        </p>
        <p className="mt-2 text-sm text-stone-500">
          <strong className="font-medium text-stone-700">Use demo data</strong> connects a mock
          provider that generates realistic synthetic post history locally. Nothing leaves your
          machine and no credentials are needed — useful for exploring the app before wiring up a
          real account.
        </p>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      {/* SettingsContent reads the OAuth callback's query params via
          useSearchParams, which must sit inside a Suspense boundary. */}
      <Suspense fallback={<div className="py-24 text-center text-sm text-stone-400">Loading…</div>}>
        <SettingsContent />
      </Suspense>
    </RequireAuth>
  );
}
