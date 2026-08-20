"use client";

import { useEffect, useState } from "react";
import { Card, CardLabel } from "@/components/ui/Card";
import { BarChart } from "@/components/ui/BarChart";
import { api } from "@/lib/api";
import { AudienceReport } from "@/types";
import { formatHour, formatNumber } from "@/lib/utils";

// Chart every third hour so the axis stays readable on mobile.
const HOUR_STEP = 3;

export function AudiencePanel() {
  const [report, setReport] = useState<AudienceReport | null>(null);

  useEffect(() => {
    // The browser knows the viewer's timezone; the server does not, so
    // hours come back translated into the viewer's own local clock.
    const offsetHours = -new Date().getTimezoneOffset() / 60;
    api
      .get<AudienceReport>(`/analytics/audience?utc_offset=${offsetHours}`)
      .then(setReport)
      .catch(() => setReport(null));
  }, []);

  if (!report) return null;

  const best = report.has_enough_data
    ? [...report.hours].sort((a, b) => b.awake_fraction - a.awake_fraction)[0]
    : null;

  return (
    <Card>
      <CardLabel>Where your audience is, and when they&apos;re awake</CardLabel>

      {!report.has_enough_data ? (
        <p className="mt-3 text-sm text-stone-500">
          {report.message || "Not enough audience data yet."}
        </p>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
            {report.top_countries.map((c) => (
              <div key={c.country} className="text-sm">
                <span className="text-stone-800">{c.country}</span>{" "}
                <span className="text-stone-400">
                  {Math.round(c.share * 100)}% · {formatNumber(c.follower_count)}
                </span>
              </div>
            ))}
          </div>

          {best && (
            <p className="mt-4 text-sm text-stone-600">
              Most of your audience is awake around{" "}
              <span className="text-stone-900">{formatHour(best.hour_local)}</span> your time
              — about {Math.round(best.awake_fraction * 100)}% of them.
            </p>
          )}

          <div className="mt-6">
            <BarChart
              data={report.hours
                .filter((h) => h.hour_local % HOUR_STEP === 0)
                .sort((a, b) => a.hour_local - b.hour_local)
                .map((h) => ({
                  // AM/PM is kept here, unlike the denser hourly chart:
                  // with only 8 bars there is room, and "12" alone is
                  // ambiguous in a chart about when people are asleep.
                  label: formatHour(h.hour_local),
                  value: h.awake_fraction,
                  highlight: best ? h.hour_local === best.hour_local : false,
                }))}
              valueFormatter={(v) => `${Math.round(v * 100)}% awake`}
            />
          </div>

          {report.coverage < 0.9 && (
            <p className="mt-4 text-xs text-stone-500">
              Based on {Math.round(report.coverage * 100)}% of your followers — the rest are in
              countries we don&apos;t have a timezone for.
            </p>
          )}
        </>
      )}

      <p className="mt-5 border-t border-stone-100 pt-3 text-xs leading-relaxed text-stone-400">
        {report.caveat}
      </p>
    </Card>
  );
}
