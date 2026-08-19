"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { Dropzone } from "@/components/upload/Dropzone";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ScoreSummary, ScoreExplanations } from "@/components/post/ScoreSummary";
import { RecommendationsList } from "@/components/post/RecommendationsList";
import { api, ApiError } from "@/lib/api";
import { AnalyzeImageResponse, UploadedImage } from "@/types";
import { useAuth } from "@/lib/auth";

type Stage = "idle" | "uploading" | "uploaded" | "analyzing" | "analyzed" | "generating";

function UploadContent() {
  const { user } = useAuth();
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("idle");
  const [preview, setPreview] = useState<string | null>(null);
  const [image, setImage] = useState<UploadedImage | null>(null);
  const [result, setResult] = useState<AnalyzeImageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [artworkIntegrity, setArtworkIntegrity] = useState(user?.artwork_integrity_enabled ?? true);

  async function handleFile(file: File) {
    setError(null);
    setResult(null);
    setPreview(URL.createObjectURL(file));
    setStage("uploading");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const uploaded = await api.upload<UploadedImage>("/images/upload", formData);
      setImage(uploaded);
      setStage("uploaded");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
      setStage("idle");
    }
  }

  async function analyze() {
    if (!image) return;
    setStage("analyzing");
    setError(null);
    try {
      const res = await api.post<AnalyzeImageResponse>(`/images/${image.id}/analyze`);
      setResult(res);
      setStage("analyzed");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analysis failed.");
      setStage("uploaded");
    }
  }

  async function generateVariant() {
    if (!image) return;
    setStage("generating");
    setError(null);
    try {
      await api.post(`/images/${image.id}/generate-variant`, {
        artwork_integrity_mode: artworkIntegrity,
      });
      router.push(`/post/${image.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Optimization failed.");
      setStage("analyzed");
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="font-display text-2xl text-stone-900">Upload a new image</p>
        <p className="mt-1 text-sm text-stone-500">
          Get a measurable technical read and rule-based suggestions before you post.
        </p>
      </div>

      {!preview ? (
        <Dropzone onFile={handleFile} />
      ) : (
        <Card className="p-4">
          <div className="relative mx-auto aspect-square w-full max-w-md overflow-hidden rounded-xl bg-stone-100">
            <Image src={preview} alt="Preview" fill className="object-contain" unoptimized />
          </div>
        </Card>
      )}

      {error && <p className="text-sm text-red-700">{error}</p>}

      {preview && (
        <div className="flex flex-wrap items-center gap-4">
          {stage === "uploading" && <p className="text-sm text-stone-500">Uploading…</p>}
          {(stage === "uploaded" || stage === "analyzing") && (
            <Button onClick={analyze} disabled={stage === "analyzing"}>
              {stage === "analyzing" ? "Analyzing…" : "Analyze"}
            </Button>
          )}
          {(stage === "analyzed" || stage === "generating") && (
            <>
              <label className="flex items-center gap-2 text-sm text-stone-600">
                <input
                  type="checkbox"
                  checked={artworkIntegrity}
                  onChange={(e) => setArtworkIntegrity(e.target.checked)}
                />
                Artwork Integrity mode
              </label>
              <Button onClick={generateVariant} disabled={stage === "generating"}>
                {stage === "generating" ? "Generating…" : "Generate optimized version"}
              </Button>
            </>
          )}
          <Button
            variant="ghost"
            onClick={() => {
              setPreview(null);
              setImage(null);
              setResult(null);
              setStage("idle");
            }}
          >
            Start over
          </Button>
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-8">
          <ScoreSummary scores={result.scores} />
          <div className="grid gap-8 lg:grid-cols-2">
            <div>
              <p className="mb-4 font-display text-lg text-stone-900">Recommendations</p>
              <RecommendationsList recommendations={result.recommendations} />
            </div>
            <div>
              <p className="mb-4 font-display text-lg text-stone-900">How these scores work</p>
              <Card>
                <ScoreExplanations scores={result.scores} />
              </Card>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function UploadPage() {
  return (
    <RequireAuth>
      <UploadContent />
    </RequireAuth>
  );
}
