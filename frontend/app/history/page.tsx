"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { EmptyState } from "@/components/ui/EmptyState";
import { api, ApiError } from "@/lib/api";
import { InstagramPost } from "@/types";
import { formatDate, formatNumber, formatPercent, mediaTypeLabel } from "@/lib/utils";

function HistoryContent() {
  const [posts, setPosts] = useState<InstagramPost[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<InstagramPost[]>("/posts?limit=100")
      .then(setPosts)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load history."));
  }, []);

  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!posts) return <div className="py-24 text-center text-sm text-stone-400">Loading…</div>;

  if (posts.length === 0) {
    return (
      <EmptyState
        title="No historical posts imported yet"
        description="Connect an Instagram account and import your history from the dashboard."
      />
    );
  }

  return (
    <div>
      <div className="mb-8">
        <p className="font-display text-2xl text-stone-900">Post history</p>
        <p className="mt-1 text-sm text-stone-500">{posts.length} imported posts</p>
      </div>
      <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
        {posts.map((post) => (
          <a
            key={post.id}
            href={post.permalink ?? "#"}
            target="_blank"
            rel="noreferrer"
            className="group flex flex-col gap-2"
          >
            <div className="relative aspect-[4/5] w-full overflow-hidden rounded-xl bg-stone-200">
              {post.thumbnail_url && (
                <Image
                  src={post.thumbnail_url}
                  alt=""
                  fill
                  className="object-cover transition-transform group-hover:scale-105"
                  sizes="240px"
                  unoptimized
                />
              )}
              <span className="absolute left-2 top-2 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-stone-700">
                {mediaTypeLabel(post.media_type)}
              </span>
            </div>
            <div className="text-xs text-stone-500">
              <div className="flex justify-between">
                <span>{formatDate(post.posted_at)}</span>
                <span>{formatPercent(post.engagement_rate)}</span>
              </div>
              <div className="mt-0.5 flex justify-between text-stone-400">
                <span>{formatNumber(post.metrics?.likes)} likes</span>
                <span>{formatNumber(post.metrics?.saves)} saves</span>
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

export default function HistoryPage() {
  return (
    <RequireAuth>
      <HistoryContent />
    </RequireAuth>
  );
}
