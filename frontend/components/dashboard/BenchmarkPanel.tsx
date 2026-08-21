"use client";

import { Card, CardLabel } from "@/components/ui/Card";
import { BenchmarkReport } from "@/types";
import { formatPercent, mediaTypeLabel } from "@/lib/utils";

/**
 * Population baselines, for orientation when there is little or no
 * history of your own.
 *
 * Every rate shown here is engagement per FOLLOWER, which is how the
 * published benchmarks are computed. The rest of the dashboard shows
 * engagement per REACH. The two are different numbers for the same post,
 * so this panel labels its basis explicitly and never sits next to a
 * reach-normalized figure without saying which is which.
 */
export function BenchmarkPanel({ report }: { report: BenchmarkReport | null }) {
  if (!report) return null;

  const cold = report.post_count === 0;

  return (
    <Card>
      <CardLabel>How this compares to accounts generally</CardLabel>

      <div className="mt-4 flex flex-wrap items-end gap-x-8 gap-y-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-stone-400">
            {cold ? "Typical account" : "Your account"}
          </p>
          <p className="mt-1 font-display text-2xl text-stone-900">
            {formatPercent(cold ? report.baseline_rate : report.own_rate, 2)}
          </p>
          <p className="text-xs text-stone-400">engagement per follower</p>
        </div>

        {!cold && (
          <div>
            <p className="text-xs uppercase tracking-wider text-stone-400">Typical account</p>
            <p className="mt-1 font-display text-2xl text-stone-500">
              {formatPercent(report.baseline_rate, 2)}
            </p>
            <p className="text-xs text-stone-400">population median</p>
          </div>
        )}

        {report.vs_baseline !== null && (
          <div>
            <p className="text-xs uppercase tracking-wider text-stone-400">Ratio</p>
            <p className="mt-1 font-display text-2xl text-stone-900">
              {report.vs_baseline.toFixed(2)}×
            </p>
            <p className="text-xs text-stone-400">
              {report.vs_baseline >= 1 ? "above" : "below"} the median
            </p>
          </div>
        )}
      </div>

      <p className="mt-4 text-sm text-stone-500">{report.explanation}</p>

      <div className="mt-5 border-t border-stone-100 pt-4">
        <p className="text-xs uppercase tracking-wider text-stone-400">By format</p>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
          {report.by_media_type.map((m) => (
            <div key={m.media_type} className="rounded-lg bg-stone-50 p-3">
              <p className="text-sm font-medium text-stone-800">
                {mediaTypeLabel(m.media_type)}
              </p>
              <p className="mt-1 font-display text-lg text-stone-900">
                {formatPercent(m.own_rate ?? m.baseline_rate, 2)}
              </p>
              <p className="text-xs text-stone-400">
                {m.post_count === 0
                  ? "typical account · you haven't posted this format"
                  : `your ${m.post_count} post${m.post_count === 1 ? "" : "s"} · median ${formatPercent(
                      m.baseline_rate,
                      2
                    )}`}
              </p>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-4 text-xs leading-relaxed text-stone-400">
        Measured per follower, so these are not comparable to the engagement rates elsewhere on
        this dashboard, which are measured per reach. {report.caveat} Source: {report.source},
        retrieved {report.retrieved}.
      </p>
    </Card>
  );
}
