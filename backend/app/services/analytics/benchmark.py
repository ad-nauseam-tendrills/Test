"""
Compares an account against published population baselines.

The point is cold start: with no history there is nothing to compare a
new post against, so this supplies a reference drawn from outside the
account and blends it away as real history arrives (see baselines.py).

Every number here is follower-normalized, matching how the published
benchmarks are computed and *not* matching the reach-normalized rate the
rest of the dashboard shows.
"""
from __future__ import annotations

from statistics import mean

from app.models.instagram_post import InstagramPost
from app.services.analytics.baselines import (
    BASELINE_ENGAGEMENT_BY_FOLLOWERS,
    BENCHMARK_RETRIEVED,
    BENCHMARK_SOURCE,
    baseline_for_media_type,
    blend_with_baseline,
    relative_to_baseline,
)
from app.services.analytics.engagement import (
    PostEngagementInput,
    engagement_rate_by_followers,
)

# Shown wherever a baseline-derived number is displayed. The product's
# standing rule is that nothing is ever presented as a prediction, and a
# borrowed population median is the easiest number to mistake for one.
BASELINE_CAVEAT = (
    "Population medians from other accounts, shown for orientation only. They are "
    "not a target, not a prediction, and not specific to your work or audience. "
    "Published studies disagree widely on these figures."
)


def _follower_rate(post: InstagramPost) -> float | None:
    m = post.metrics
    if not m:
        return None
    return engagement_rate_by_followers(
        PostEngagementInput(
            likes=m.likes,
            comments=m.comments,
            saves=m.saves,
            shares=m.shares,
            reach=m.reach,
            impressions=m.impressions,
            views=m.views,
            # Meta exposes no historical follower count, so imports stamp
            # each post with the count at import time. Back-dated posts
            # are therefore normalized against today's audience -- fine
            # for a recent window, increasingly approximate further back.
            follower_count=post.follower_count_at_posting,
        )
    )


def build_benchmark_report(posts: list[InstagramPost]) -> dict:
    """
    Blend this account's follower-normalized engagement against published
    baselines, overall and per media type.
    """
    rates = [r for r in (_follower_rate(p) for p in posts) if r is not None]
    own_overall = mean(rates) if rates else None

    overall = blend_with_baseline(
        own_value=own_overall,
        own_post_count=len(rates),
        baseline_value=BASELINE_ENGAGEMENT_BY_FOLLOWERS,
    )

    by_type: list[dict] = []
    seen_types = {(p.media_type or "IMAGE").upper() for p in posts}
    # Always report every format with a published baseline, not just the
    # ones already posted -- "carousels typically do better than singles"
    # is exactly the guidance a new account has no way to derive itself.
    for media_type in sorted(seen_types | {"IMAGE", "CAROUSEL_ALBUM", "VIDEO"}):
        type_rates = [
            r
            for r in (
                _follower_rate(p)
                for p in posts
                if (p.media_type or "IMAGE").upper() == media_type
            )
            if r is not None
        ]
        blended = blend_with_baseline(
            own_value=mean(type_rates) if type_rates else None,
            own_post_count=len(type_rates),
            baseline_value=baseline_for_media_type(media_type),
        )
        by_type.append(
            {
                "media_type": media_type,
                "post_count": len(type_rates),
                "own_rate": blended.own_value,
                "baseline_rate": blended.baseline_value,
                "blended_rate": round(blended.value, 6),
                "vs_baseline": relative_to_baseline(
                    blended.own_value, blended.baseline_value
                ),
                "confidence": blended.confidence,
            }
        )

    return {
        "source": BENCHMARK_SOURCE,
        "retrieved": BENCHMARK_RETRIEVED,
        "caveat": BASELINE_CAVEAT,
        "metric_basis": "followers",
        "own_rate": overall.own_value,
        "baseline_rate": overall.baseline_value,
        "blended_rate": round(overall.value, 6),
        "vs_baseline": relative_to_baseline(overall.own_value, overall.baseline_value),
        "post_count": overall.own_post_count,
        "confidence": overall.confidence,
        "explanation": overall.describe(),
        "by_media_type": by_type,
    }
