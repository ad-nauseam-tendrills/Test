"use client";

import { useEffect, useState } from "react";
import { Card, CardLabel } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { HashtagReport } from "@/types";
import { formatPercent } from "@/lib/utils";

export function HashtagPanel() {
  const [report, setReport] = useState<HashtagReport | null>(null);

  useEffect(() => {
    api
      .get<HashtagReport>("/analytics/hashtags")
      .then(setReport)
      .catch(() => setReport(null));
  }, []);

  if (!report) return null;

  return (
    <Card>
      <CardLabel>Hashtags you use</CardLabel>

      {!report.has_enough_data ? (
        <p className="mt-3 text-sm text-stone-500">
          {report.message || "Not enough historical data yet."}
        </p>
      ) : (
        <div className="mt-4 flex flex-col gap-2">
          {report.hashtags.map((h) => (
            <div key={h.tag} className="flex items-baseline justify-between gap-4 text-sm">
              <span className="truncate text-stone-800">#{h.tag}</span>
              <span className="flex shrink-0 items-baseline gap-4 text-stone-500">
                <span className="text-xs">{h.post_count} posts</span>
                {h.avg_engagement_rate !== null ? (
                  <>
                    <span className="tabular-nums">{formatPercent(h.avg_engagement_rate)}</span>
                    {h.vs_median !== null && (
                      <span
                        className={`w-16 text-right text-xs tabular-nums ${
                          h.vs_median >= 1 ? "text-stone-700" : "text-stone-400"
                        }`}
                      >
                        {h.vs_median.toFixed(2)}× median
                      </span>
                    )}
                  </>
                ) : (
                  <span className="w-32 text-right text-xs italic text-stone-400">
                    too few posts
                  </span>
                )}
              </span>
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
