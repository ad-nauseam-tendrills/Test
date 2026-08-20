"use client";

import { useState } from "react";
import { Card, CardLabel } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api";
import { CaptionOption, GenerateCaptionsResponse } from "@/types";

export function CaptionSuggestions({ imageId }: { imageId: string }) {
  const [captions, setCaptions] = useState<CaptionOption[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<GenerateCaptionsResponse>(`/images/${imageId}/captions`);
      setCaptions(res.captions);
      setNote(res.note);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not generate captions.");
    } finally {
      setBusy(false);
    }
  }

  async function copy(caption: CaptionOption) {
    try {
      await navigator.clipboard.writeText(caption.caption_text);
      setCopiedId(caption.id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch {
      setError("Could not copy to clipboard.");
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-display text-lg text-stone-900">Caption suggestions</p>
        <Button variant="secondary" onClick={generate} disabled={busy}>
          {busy ? "Writing…" : captions.length ? "Try again" : "Suggest captions"}
        </Button>
      </div>

      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}

      {captions.length === 0 && !error && (
        <p className="mt-3 text-sm text-stone-500">
          Written from this image and the voice of your own past captions.
        </p>
      )}

      {captions.length > 0 && (
        <div className="mt-5 flex flex-col gap-4">
          {captions.map((caption) => (
            <div key={caption.id} className="border-t border-stone-100 pt-4 first:border-none first:pt-0">
              {caption.approach && (
                <CardLabel className="mb-1.5">{caption.approach}</CardLabel>
              )}
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-800">
                {caption.caption_text}
              </p>
              <button
                onClick={() => copy(caption)}
                className="mt-2 text-xs text-stone-500 underline-offset-4 hover:text-stone-900 hover:underline"
              >
                {copiedId === caption.id ? "Copied" : "Copy"}
              </button>
            </div>
          ))}
        </div>
      )}

      {note && (
        <p className="mt-5 border-t border-stone-100 pt-3 text-xs italic text-stone-400">{note}</p>
      )}
    </Card>
  );
}
