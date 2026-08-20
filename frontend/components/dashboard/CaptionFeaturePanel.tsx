"use client";

import { useEffect, useState } from "react";
import { Card, CardLabel } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { CaptionFeatureReport, FeatureGroup } from "@/types";
import { formatPercent } from "@/lib/utils";

function groupByFeature(features: FeatureGroup[]): [string, FeatureGroup[]][] {
  const map = new Map<string, FeatureGroup[]>();
  for (const f of features) {
    map.set(f.feature, [...(map.get(f.feature) ?? []), f]);
  }
  return Array.from(map.entries());
}

export function CaptionFeaturePanel() {
  const [report, setReport] = useState<CaptionFeatureReport | null>(null);

  useEffect(() => {
    api
      .get<CaptionFeatureReport>("/analytics/caption-features")
      .then(setReport)
      .catch(() => setReport(null));
  }, []);

  if (!report) return null;

  return (
    <Card>
      <CardLabel>Your caption habits</CardLabel>

      {!report.has_enough_data ? (
        <p className="mt-3 text-sm text-stone-500">
          {report.message || "Not enough historical data yet."}
        </p>
      ) : (
        <div className="mt-4 flex flex-col gap-5">
          {groupByFeature(report.features).map(([feature, groups]) => (
            <div key={feature}>
              <p className="text-xs uppercase tracking-wider text-stone-400">{feature}</p>
              <div className="mt-1.5 flex flex-col gap-1.5">
                {groups.map((g) => (
                  <div
                    key={g.group}
                    className="flex items-baseline justify-between gap-4 text-sm"
                  >
                    <span className="truncate text-stone-800">{g.group}</span>
                    <span className="flex shrink-0 items-baseline gap-4 text-stone-500">
                      <span className="text-xs">{g.post_count} posts</span>
                      <span className="tabular-nums">
                        {formatPercent(g.avg_engagement_rate)}
                      </span>
                      {g.vs_median !== null && (
                        <span
                          className={`w-16 text-right text-xs tabular-nums ${
                            g.vs_median >= 1 ? "text-stone-700" : "text-stone-400"
                          }`}
                        >
                          {g.vs_median.toFixed(2)}× median
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="mt-5 border-t border-stone-100 pt-3 text-xs leading-relaxed text-stone-400">
        {report.caveat}
      </p>
    </Card>
  );
}
