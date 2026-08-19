import { ImageAnalysis } from "@/types";
import { Card, CardLabel } from "@/components/ui/Card";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <CardLabel>{label}</CardLabel>
      <p className="mt-1 text-sm text-stone-800">{value}</p>
    </div>
  );
}

export function MetricsGrid({ analysis }: { analysis: ImageAnalysis }) {
  return (
    <Card>
      <p className="mb-4 font-display text-lg text-stone-900">Visual metrics</p>
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
        <Metric label="Dimensions" value={`${analysis.width} × ${analysis.height}px`} />
        <Metric label="Aspect ratio" value={analysis.aspect_ratio.toFixed(2)} />
        <Metric label="Brightness" value={`${analysis.brightness.toFixed(0)} / 255`} />
        <Metric label="Contrast" value={analysis.contrast.toFixed(0)} />
        <Metric label="Saturation" value={`${analysis.saturation.toFixed(0)} / 255`} />
        <Metric label="Color temperature" value={`${analysis.color_temperature.toFixed(0)}K (approx.)`} />
        <Metric label="Sharpness" value={analysis.sharpness.toFixed(0)} />
        <Metric label="Highlight clipping" value={`${analysis.highlight_clipping_pct.toFixed(1)}%`} />
        <Metric label="Shadow clipping" value={`${analysis.shadow_clipping_pct.toFixed(1)}%`} />
        <Metric label="Faces detected" value={String(analysis.face_count)} />
        {analysis.largest_face_area_ratio !== null && (
          <Metric label="Largest face size" value={`${(analysis.largest_face_area_ratio * 100).toFixed(1)}% of frame`} />
        )}
        {analysis.negative_space_ratio !== null && (
          <Metric label="Negative space" value={`${(analysis.negative_space_ratio * 100).toFixed(0)}%`} />
        )}
      </div>

      {analysis.dominant_colors.length > 0 && (
        <div className="mt-6">
          <CardLabel>Dominant colors</CardLabel>
          <div className="mt-2 flex gap-2">
            {analysis.dominant_colors.map((c) => (
              <div key={c.hex} className="flex flex-col items-center gap-1">
                <div className="h-8 w-8 rounded-full border border-stone-200" style={{ backgroundColor: c.hex }} />
                <span className="text-[10px] text-stone-400">{Math.round(c.ratio * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
