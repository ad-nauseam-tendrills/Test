"""Aggregates raw posts + metrics into the dashboard response shape."""
from __future__ import annotations

from statistics import mean

from sqlalchemy.orm import Session, joinedload

from app.models.instagram_post import InstagramPost
from app.services.analytics.engagement import PostEngagementInput, engagement_rate
from app.services.analytics.normalization import (
    INSUFFICIENT_DATA_MESSAGE,
    MIN_POSTS_FOR_STATS,
    has_enough_data,
    performance_index,
)
from app.services.analytics.timing import (
    TimedPost,
    best_posting_windows,
    performance_by_day_of_week,
    performance_by_hour_of_day,
    performance_by_media_type,
)


def _posts_for_account(db: Session, account_id) -> list[InstagramPost]:
    return (
        db.query(InstagramPost)
        .options(joinedload(InstagramPost.metrics))
        .filter(InstagramPost.account_id == account_id)
        .order_by(InstagramPost.posted_at.desc())
        .all()
    )


def annotate_post(post: InstagramPost, all_rates: list[float]) -> dict:
    """Compute engagement_rate + performance_index for a single post."""
    m = post.metrics
    er = None
    if m:
        er = engagement_rate(
            PostEngagementInput(
                likes=m.likes,
                comments=m.comments,
                saves=m.saves,
                shares=m.shares,
                reach=m.reach,
                impressions=m.impressions,
            )
        )
    return {
        "engagement_rate": er,
        "performance_index": performance_index(er, all_rates),
    }


def build_dashboard(db: Session, account_id) -> dict:
    posts = _posts_for_account(db, account_id)
    total_posts = len(posts)

    rates: list[float] = []
    annotated = []
    for p in posts:
        extra = annotate_post(p, [])  # fill rate list first pass
        annotated.append((p, extra))
        if extra["engagement_rate"] is not None:
            rates.append(extra["engagement_rate"])

    # Second pass to compute percentile now that we have the full distribution.
    for p, extra in annotated:
        extra["performance_index"] = performance_index(extra["engagement_rate"], rates)

    enough = has_enough_data(total_posts, MIN_POSTS_FOR_STATS)

    reaches = [p.metrics.reach for p, _ in annotated if p.metrics and p.metrics.reach is not None]
    saves = [p.metrics.saves for p, _ in annotated if p.metrics and p.metrics.saves is not None]

    overview = {
        "total_posts": total_posts,
        "avg_reach": round(mean(reaches), 1) if reaches else None,
        "avg_engagement_rate": round(mean(rates), 5) if rates else None,
        "avg_saves": round(mean(saves), 1) if saves else None,
        "has_enough_data": enough,
        "message": None if enough else INSUFFICIENT_DATA_MESSAGE,
    }

    best_posts_sorted = sorted(
        [(p, e) for p, e in annotated if e["engagement_rate"] is not None],
        key=lambda pe: pe[1]["engagement_rate"],
        reverse=True,
    )[:6]

    timed_posts = [
        TimedPost(
            posted_at=p.posted_at,
            engagement_rate=e["engagement_rate"],
            media_type=p.media_type,
            reach=p.metrics.reach if p.metrics else None,
        )
        for p, e in annotated
    ]

    return {
        "overview": overview,
        "best_posts": [(p, e) for p, e in best_posts_sorted],
        "recent_posts": annotated[:10],
        "by_day_of_week": performance_by_day_of_week(timed_posts),
        "by_hour_of_day": performance_by_hour_of_day(timed_posts),
        "by_media_type": performance_by_media_type(timed_posts),
        "posting_windows": best_posting_windows(timed_posts),
        "has_enough_data": enough,
        "insufficient_data_message": None if enough else INSUFFICIENT_DATA_MESSAGE,
        "all_engagement_rates": rates,
    }
