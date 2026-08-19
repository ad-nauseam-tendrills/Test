import Image from "next/image";
import { ImageVariant, UploadedImage } from "@/types";
import { Card, CardLabel } from "@/components/ui/Card";
import { fileUrl } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

const ADJUSTMENT_LABELS: Record<string, string> = {
  exposure: "Exposure",
  contrast: "Contrast",
  white_balance_shift: "White balance",
  highlight_recovery: "Highlight recovery",
  shadow_recovery: "Shadow recovery",
  saturation: "Saturation",
  sharpen_amount: "Sharpening",
  target_aspect_ratio: "Crop target",
  rotation_degrees: "Straightening",
};

export function BeforeAfter({ original, variant }: { original: UploadedImage; variant: ImageVariant }) {
  const adjustments = Object.entries(variant.adjustments).filter(
    ([key, value]) => key !== "crop_box" && value !== null && value !== 0 && value !== "0"
  );

  return (
    <Card>
      <div className="flex items-center justify-between">
        <p className="font-display text-lg text-stone-900">Before / after</p>
        <span className="text-xs text-stone-400">Generated {formatDateTime(variant.created_at)}</span>
      </div>
      <div className="mt-5 grid gap-6 sm:grid-cols-2">
        <div>
          <CardLabel>Original</CardLabel>
          <div className="relative mt-2 aspect-square w-full overflow-hidden rounded-xl bg-stone-100">
            {original.url && (
              <Image src={fileUrl(original.url)} alt="Original" fill className="object-contain" unoptimized />
            )}
          </div>
        </div>
        <div>
          <CardLabel>Optimized {variant.artwork_integrity_mode && "· Artwork Integrity"}</CardLabel>
          <div className="relative mt-2 aspect-square w-full overflow-hidden rounded-xl bg-stone-100">
            {variant.url && (
              <Image src={fileUrl(variant.url)} alt="Optimized" fill className="object-contain" unoptimized />
            )}
          </div>
        </div>
      </div>

      <div className="mt-6">
        <CardLabel>Exact adjustment values applied</CardLabel>
        {adjustments.length === 0 ? (
          <p className="mt-2 text-sm text-stone-500">No adjustments were necessary.</p>
        ) : (
          <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
            {adjustments.map(([key, value]) => (
              <div key={key} className="flex justify-between text-sm">
                <span className="text-stone-500">{ADJUSTMENT_LABELS[key] ?? key}</span>
                <span className="text-stone-800">{String(value)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
