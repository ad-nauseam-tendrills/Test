"""
Normalization helpers so posts made at different follower counts, or at
different points in an account's history, can be fairly compared.

We deliberately avoid anything that looks like a predictive model here --
these are descriptive statistics only (percentiles, z-like relative
scores against the account's own history).
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median


MIN_POSTS_FOR_STATS = 5
MIN_POSTS_FOR_BREAKDOWNS = 10


@dataclass
class NormalizedPost:
    id: str
    engagement_rate: float | None
    reach: int | None
    follower_count_at_posting: int | None


def reach_relative_to_followers(reach: int | None, follower_count: int | None) -> float | None:
    """Reach as a fraction of the follower count at posting time."""
    if not reach or not follower_count:
        return None
    return round(reach / follower_count, 5)


def performance_index(
    engagement_rate: float | None,
    all_engagement_rates: list[float],
) -> float | None:
    """
    A post's engagement rate expressed as a percentile (0-100) within the
    account's own historical distribution. This lets us say "this post
    performed better than X% of this account's own posts" without
    claiming any absolute or predictive meaning.
    """
    if engagement_rate is None or not all_engagement_rates:
        return None

    sorted_rates = sorted(all_engagement_rates)
    rank = sum(1 for r in sorted_rates if r <= engagement_rate)
    percentile = (rank / len(sorted_rates)) * 100
    return round(percentile, 1)


def median_engagement_rate(rates: list[float]) -> float | None:
    clean = [r for r in rates if r is not None]
    if not clean:
        return None
    return round(median(clean), 5)


def percentile(values: list[float], pct: float) -> float | None:
    """Simple linear-interpolation percentile (0-100), no external deps."""
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    k = (len(clean) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(clean) - 1)
    if f == c:
        return clean[f]
    return clean[f] + (clean[c] - clean[f]) * (k - f)


def has_enough_data(post_count: int, minimum: int = MIN_POSTS_FOR_STATS) -> bool:
    return post_count >= minimum


INSUFFICIENT_DATA_MESSAGE = "Not enough historical data yet."
