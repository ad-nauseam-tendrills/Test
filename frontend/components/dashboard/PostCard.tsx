import Image from "next/image";
import { InstagramPost } from "@/types";
import { formatDate, formatNumber, formatPercent, mediaTypeLabel } from "@/lib/utils";

export function PostCard({ post }: { post: InstagramPost }) {
  return (
    <a
      href={post.permalink ?? "#"}
      target="_blank"
      rel="noreferrer"
      className="group flex gap-4 rounded-xl p-2 transition-colors hover:bg-stone-100"
    >
      <div className="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-lg bg-stone-200">
        {post.thumbnail_url && (
          <Image
            src={post.thumbnail_url}
            alt=""
            fill
            className="object-cover transition-transform group-hover:scale-105"
            sizes="80px"
            unoptimized
          />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs uppercase tracking-wide text-stone-400">
            {mediaTypeLabel(post.media_type)}
          </span>
          <span className="text-xs text-stone-400">{formatDate(post.posted_at)}</span>
        </div>
        <p className="mt-1 truncate text-sm text-stone-700">{post.caption || "No caption"}</p>
        <div className="mt-1.5 flex gap-4 text-xs text-stone-500">
          <span>{formatNumber(post.metrics?.likes)} likes</span>
          <span>{formatNumber(post.metrics?.saves)} saves</span>
          <span>{formatPercent(post.engagement_rate)} eng.</span>
        </div>
      </div>
    </a>
  );
}
