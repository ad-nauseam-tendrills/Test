"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { Card, CardLabel } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { BarChart } from "@/components/ui/BarChart";
import { PostCard } from "@/components/dashboard/PostCard";
import { api, ApiError } from "@/lib/api";
import { DashboardResponse, InstagramAccount } from "@/types";
import { formatHour, formatNumber, formatPercent, mediaTypeLabel } from "@/lib/utils";

function DashboardContent() {
  const [account, setAccount] = useState<InstagramAccount | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const accounts = await api.get<InstagramAccount[]>("/accounts");
      const active = accounts.find((a) => a.is_active) ?? null;
      setAccount(active);
      const dash = await api.get<DashboardResponse>("/analytics/dashboard");
      setDashboard(dash);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to load dashboard.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function connectAccount() {
    setBusy(true);
    setMessage(null);
    try {
      const acc = await api.post<InstagramAccount>("/accounts/connect", { provider: "mock" });
      setAccount(acc);
      const result = await api.post<{ imported_count: number; skipped_count: number }>(
        `/accounts/${acc.id}/import`
      );
      setMessage(`Imported ${result.imported_count} historical posts.`);
      await load();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to connect account.");
    } finally {
      setBusy(false);
    }
  }

  async function reimport() {
    if (!account) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.post<{ imported_count: number; skipped_count: number }>(
        `/accounts/${account.id}/import`
      );
      setMessage(`Imported ${result.imported_count} new posts (${result.skipped_count} already up to date).`);
      await load();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Failed to import posts.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <div className="py-24 text-center text-sm text-stone-400">Loading dashboard…</div>;
  }

  if (!account) {
    return (
      <EmptyState
        title="Connect an Instagram account to get started"
        description="Aperture uses a mock Instagram integration in development, so you can explore the full experience without real Meta credentials."
        action={
          <Button onClick={connectAccount} disabled={busy}>
            {busy ? "Connecting…" : "Connect Instagram (mock)"}
          </Button>
        }
      />
    );
  }

  const overview = dashboard?.overview;

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="font-display text-2xl text-stone-900">@{account.username}</p>
          <p className="mt-1 text-sm text-stone-500">
            {formatNumber(account.follower_count)} followers · {overview?.total_posts ?? 0} posts imported
          </p>
        </div>
        <Button variant="secondary" onClick={reimport} disabled={busy}>
          {busy ? "Syncing…" : "Re-sync history"}
        </Button>
      </div>

      {message && <p className="text-sm text-stone-500">{message}</p>}

      {!dashboard?.has_enough_data && (
        <p className="rounded-lg bg-stone-100 px-4 py-3 text-sm text-stone-600">
          {dashboard?.insufficient_data_message || "Not enough historical data yet."}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Imported posts" value={formatNumber(overview?.total_posts)} />
        <Stat label="Avg. reach" value={formatNumber(overview?.avg_reach)} />
        <Stat label="Avg. engagement" value={formatPercent(overview?.avg_engagement_rate)} />
        <Stat label="Avg. saves" value={formatNumber(overview?.avg_saves)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardLabel>Performance by day of week</CardLabel>
          <div className="mt-6">
            <BarChart
              data={
                dashboard?.by_day_of_week.map((d) => ({
                  label: d.day.slice(0, 3),
                  value: d.avg_engagement_rate,
                })) ?? []
              }
              valueFormatter={(v) => formatPercent(v)}
            />
          </div>
        </Card>
        <Card>
          <CardLabel>Performance by hour of day</CardLabel>
          <div className="mt-6">
            <BarChart
              data={
                dashboard?.by_hour_of_day
                  .filter((h) => h.hour % 2 === 0)
                  .map((h) => ({ label: formatHour(h.hour).replace(/[AP]M/, ""), value: h.avg_engagement_rate })) ?? []
              }
              valueFormatter={(v) => formatPercent(v)}
            />
          </div>
        </Card>
      </div>

      {dashboard && dashboard.by_media_type.length > 1 && (
        <Card>
          <CardLabel>Carousel vs. single image vs. video</CardLabel>
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
            {dashboard.by_media_type.map((m) => (
              <div key={m.media_type} className="rounded-lg bg-stone-50 p-4">
                <p className="text-sm font-medium text-stone-800">{mediaTypeLabel(m.media_type)}</p>
                <p className="mt-1 text-xs text-stone-500">{m.post_count} posts</p>
                <p className="mt-2 font-display text-xl">{formatPercent(m.avg_engagement_rate)}</p>
                <p className="text-xs text-stone-400">avg. engagement</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardLabel>Strongest historical posts</CardLabel>
          <div className="mt-4 flex flex-col gap-1">
            {dashboard?.best_posts.length ? (
              dashboard.best_posts.map((p) => <PostCard key={p.id} post={p} />)
            ) : (
              <p className="py-6 text-center text-sm text-stone-400">No posts yet.</p>
            )}
          </div>
        </Card>
        <Card>
          <CardLabel>Recent posts</CardLabel>
          <div className="mt-4 flex flex-col gap-1">
            {dashboard?.recent_posts.length ? (
              dashboard.recent_posts.map((p) => <PostCard key={p.id} post={p} />)
            ) : (
              <p className="py-6 text-center text-sm text-stone-400">No posts yet.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-5">
      <CardLabel>{label}</CardLabel>
      <p className="mt-2 font-display text-2xl text-stone-900">{value}</p>
    </Card>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}
