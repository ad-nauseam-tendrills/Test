import { ScoreReport } from "@/types";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Card, CardLabel } from "@/components/ui/Card";

const SECTIONS: { key: keyof ScoreReport; label: string }[] = [
  { key: "overall_readiness", label: "Overall readiness" },
  { key: "image_readiness", label: "Image readiness" },
  { key: "timing_opportunity", label: "Timing opportunity" },
  { key: "historical_similarity", label: "Historical similarity" },
];

export function ScoreSummary({ scores }: { scores: ScoreReport }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {SECTIONS.map(({ key, label }) => {
        const section = scores[key];
        return (
          <Card key={key} className="flex flex-col items-center gap-3 p-5 text-center">
            <ScoreRing score={section.score} size={80} />
            <div>
              <CardLabel>{label}</CardLabel>
              <p className="mt-1 text-sm font-medium text-stone-800">{section.label}</p>
            </div>
          </Card>
        );
      })}
    </div>
  );
}

export function ScoreExplanations({ scores }: { scores: ScoreReport }) {
  return (
    <div className="flex flex-col gap-4">
      {SECTIONS.map(({ key, label }) => (
        <div key={key} className="border-b border-stone-100 pb-4 last:border-none">
          <p className="text-sm font-medium text-stone-800">
            {label} — {scores[key].score}/100
          </p>
          <p className="mt-1 text-sm text-stone-500">{scores[key].explanation}</p>
        </div>
      ))}
      <p className="text-xs italic text-stone-400">
        These are heuristic scores based on measurable image properties and this account&apos;s own
        historical data. They are not predictions of likes, reach, or follower growth.
      </p>
    </div>
  );
}
