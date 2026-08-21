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
    if (status === "error") {
      setMessage(detail || "Could not connect that Instagram account.");
      return;
    }
    if (status !== "connected") return;

    const accountId = searchParams.get("account_id");
    if (!accountId) {
      setMessage(detail || "Instagram account connected.");
      return;
    }

    // Pull the post history immediately. Connecting is only ever a means
    // to this, and stopping at a connected-but-empty account would leave
    // the dashboard blank with no indication of what to do next.
    let cancelled = false;
    setBusy(true);
    setMessage(`${detail || "Connected."} Importing your posts…`);
    api
      .post<{ imported_count: number; skipped_count: number }>(`/accounts/${accountId}/import`)
      .then((result) => {
        if (cancelled) return;
        setMessage(
          `${detail || "Connected."} Imported ${result.imported_count} posts — ` +
            `your dashboard is ready.`
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setMessage(
          `${detail || "Connected."} Could not import posts yet: ` +
            `${err instanceof ApiError ? err.message : "unknown error"}. ` +
            `Use "Import history" below to retry.`
        );
      })
      .finally(() => {
        if (cancelled) return;
        setBusy(false);
        loadAccounts();
      });

    return () => {
      cancelled = true;
    };
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

  async function removeAccount(account: InstagramAccount) {
    // Deleting takes the imported post history with it, so make the user
    // say so explicitly -- there is no undo short of re-importing.
    const confirmed = window.confirm(
      `Remove @${account.username} and delete every post imported from it? ` +
        `This cannot be undone. You can reconnect the account afterwards.`
    );
    if (!confirmed) return;

    setBusy(true);
    setMessage(null);
    try {
      await api.delete(`/accounts/${account.id}`);
      await loadAccounts();
      setMessage(`Removed @${account.username} and its imported posts.`);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to remove account.");
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
          {accounts.map((account) => (
            <div key={account.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-stone-100 pt-4 first:border-none first:pt-0">
              <div>
                <p className="text-sm font-medium text-stone-800">
                  @{account.username}{" "}
                  <span className="ml-1 text-xs text-stone-400">
                    {account.is_active ? "Connected" : "Disconnected"}
                    {account.provider !== "meta" && ` · ${account.provider}`}
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
                <Button variant="ghost" onClick={() => removeAccount(account)} disabled={busy}>
                  Remove
                </Button>
              </div>
            </div>
          ))}

          {/* Always reachable, not just when nothing is connected: this is
              the only route to the real Instagram flow, and it is also how
              you replace an account that was connected by mistake. */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-stone-100 pt-4 first:border-none first:pt-0">
            <p className="text-sm text-stone-500">
              {accounts.length === 0
                ? "No account connected."
                : "Connect another Instagram account."}
            </p>
            <Button onClick={connectRealAccount} disabled={busy}>
              Connect Instagram
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <CardLabel>About the Instagram connection</CardLabel>
        <p className="mt-2 text-sm text-stone-500">
          Aperture reads your posts and their insights through the official Instagram API. Instagram
          is never scraped, nothing is ever posted or changed on your behalf, and the connection can
          be revoked at any time from Instagram under Settings → Apps and websites.
        </p>
        <p className="mt-2 text-sm text-stone-500">
          Connecting requires an Instagram professional (Creator or Business) account. Your recent
          posts are imported automatically once you connect; use{" "}
          <strong className="font-medium text-stone-700">Import history</strong> afterwards to pick
          up newer ones.
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
