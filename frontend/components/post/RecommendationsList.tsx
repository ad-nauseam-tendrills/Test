import { Recommendation } from "@/types";
import { Card } from "@/components/ui/Card";
import { SeverityBadge } from "@/components/ui/Badge";

export function RecommendationsList({ recommendations }: { recommendations: Recommendation[] }) {
  if (recommendations.length === 0) {
    return (
      <Card>
        <p className="text-sm text-stone-500">No issues detected. This image looks technically ready.</p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {recommendations.map((rec) => (
        <Card key={rec.id} className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-stone-800">{rec.title}</p>
            <SeverityBadge severity={rec.severity} />
          </div>
          <p className="text-sm text-stone-500">{rec.detail}</p>
        </Card>
      ))}
    </div>
  );
}
