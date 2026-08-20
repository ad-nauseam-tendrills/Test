"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Image from "next/image";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { MetricsGrid } from "@/components/post/MetricsGrid";
import { RecommendationsList } from "@/components/post/RecommendationsList";
import { BeforeAfter } from "@/components/post/BeforeAfter";
import { CaptionSuggestions } from "@/components/post/CaptionSuggestions";
import { ScoreSummary, ScoreExplanations } from "@/components/post/ScoreSummary";
import { api, ApiError, fileUrl } from "@/lib/api";
import { ImageDetail } from "@/types";
import { formatDateTime } from "@/lib/utils";

function PostDetailContent() {
  const params = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ImageDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const data = await api.get<ImageDetail>(`/images/${params.id}`);
      setDetail(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load image.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  async function reanalyze() {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/images/${params.id}/analyze`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  async function generateVariant() {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/images/${params.id}/generate-variant`, { artwork_integrity_mode: true });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Optimization failed.");
    } finally {
      setBusy(false);
    }
  }

  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!detail) return <div className="py-24 text-center text-sm text-stone-400">Loading…</div>;

  const { image, analysis, scores, recommendations, variants } = detail;
  const latestVariant = variants[0];

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-display text-2xl text-stone-900">{image.original_filename}</p>
          <p className="mt-1 text-sm text-stone-500">
            Uploaded {formatDateTime(image.created_at)} · {image.width} × {image.height}px
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={reanalyze} disabled={busy}>
            {busy ? "Working…" : "Re-analyze"}
          </Button>
          {analysis && (
            <Button onClick={generateVariant} disabled={busy}>
              {busy ? "Working…" : "Generate optimized version"}
            </Button>
          )}
        </div>
      </div>

      {!analysis ? (
        <Card>
          <p className="text-sm text-stone-500">This image hasn&apos;t been analyzed yet.</p>
          <div className="relative mt-4 aspect-square w-full max-w-sm overflow-hidden rounded-xl bg-stone-100">
            {image.url && <Image src={fileUrl(image.url)} alt="" fill className="object-contain" unoptimized />}
          </div>
        </Card>
      ) : (
        <>
          {scores && <ScoreSummary scores={scores} />}

          <div className="grid gap-8 lg:grid-cols-2">
            <MetricsGrid analysis={analysis} />
            <div>
              <p className="mb-4 font-display text-lg text-stone-900">Recommendations</p>
              <RecommendationsList recommendations={recommendations} />
            </div>
          </div>

          <CaptionSuggestions imageId={image.id} />

          {scores && (
            <Card>
              <p className="mb-4 font-display text-lg text-stone-900">
                Historical comparison &amp; how scores work
              </p>
              <ScoreExplanations scores={scores} />
            </Card>
          )}

          {latestVariant ? (
            <BeforeAfter original={image} variant={latestVariant} />
          ) : (
            <Card>
              <p className="text-sm text-stone-500">
                No optimized version generated yet. Use &quot;Generate optimized version&quot; above to
                apply the recommended adjustments in Artwork Integrity mode.
              </p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export default function PostDetailPage() {
  return (
    <RequireAuth>
      <PostDetailContent />
    </RequireAuth>
  );
}
