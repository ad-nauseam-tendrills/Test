"""
Timing analysis: best posting days/hours derived purely from an account's
own historical engagement, with explicit statistical-confidence caveats.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import mean

from app.services.analytics.normalization import MIN_POSTS_FOR_BREAKDOWNS

DAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]


@dataclass
class TimedPost:
    posted_at: datetime
    engagement_rate: float | None
    media_type: str
    reach: int | None = None


def performance_by_day_of_week(posts: list[TimedPost]) -> list[dict]:
    buckets: dict[int, list[float]] = defaultdict(list)
    counts: dict[int, int] = defaultdict(int)
    for p in posts:
        idx = p.posted_at.weekday()
        counts[idx] += 1
        if p.engagement_rate is not None:
            buckets[idx].append(p.engagement_rate)

    results = []
    for idx, name in enumerate(DAY_NAMES):
        rates = buckets.get(idx, [])
        results.append(
            {
                "day": name,
                "day_index": idx,
                "post_count": counts.get(idx, 0),
                "avg_engagement_rate": round(mean(rates), 5) if rates else None,
            }
        )
    return results


def performance_by_hour_of_day(posts: list[TimedPost]) -> list[dict]:
    buckets: dict[int, list[float]] = defaultdict(list)
    counts: dict[int, int] = defaultdict(int)
    for p in posts:
        hour = p.posted_at.hour
        counts[hour] += 1
        if p.engagement_rate is not None:
            buckets[hour].append(p.engagement_rate)

    results = []
    for hour in range(24):
        rates = buckets.get(hour, [])
        results.append(
            {
                "hour": hour,
                "post_count": counts.get(hour, 0),
                "avg_engagement_rate": round(mean(rates), 5) if rates else None,
            }
        )
    return results


def performance_by_media_type(posts: list[TimedPost]) -> list[dict]:
    buckets: dict[str, list[float]] = defaultdict(list)
    reach_buckets: dict[str, list[int]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for p in posts:
        counts[p.media_type] += 1
        if p.engagement_rate is not None:
            buckets[p.media_type].append(p.engagement_rate)
        if p.reach is not None:
            reach_buckets[p.media_type].append(p.reach)

    results = []
    for media_type in counts:
        rates = buckets.get(media_type, [])
        reaches = reach_buckets.get(media_type, [])
        results.append(
            {
                "media_type": media_type,
                "post_count": counts[media_type],
                "avg_engagement_rate": round(mean(rates), 5) if rates else None,
                "avg_reach": round(mean(reaches), 1) if reaches else None,
            }
        )
    return sorted(results, key=lambda r: r["media_type"])


def best_posting_windows(posts: list[TimedPost], top_n: int = 3) -> dict:
    """
    Returns the best day(s) and hour(s) by historical average engagement,
    with an explicit flag for whether there's enough data to trust the
    result. Never claims statistical significance -- just a descriptive
    ranking of the account's own history.
    """
    enough_data = len(posts) >= MIN_POSTS_FOR_BREAKDOWNS

    by_day = [d for d in performance_by_day_of_week(posts) if d["avg_engagement_rate"] is not None]
    by_hour = [h for h in performance_by_hour_of_day(posts) if h["avg_engagement_rate"] is not None]

    best_days = sorted(by_day, key=lambda d: d["avg_engagement_rate"], reverse=True)[:top_n]
    best_hours = sorted(by_hour, key=lambda h: h["avg_engagement_rate"], reverse=True)[:top_n]

    return {
        "has_enough_data": enough_data,
        "best_days": best_days,
        "best_hours": best_hours,
    }
