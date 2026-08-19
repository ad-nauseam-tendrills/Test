"""
Engagement calculations.

All rates are expressed as plain ratios (e.g. 0.045 == 4.5%) computed
against reach when available, falling back to impressions. Reach is
preferred because it is a better denominator for judging how well a post
performed with the people who actually saw it, versus followers-count
which does not account for algorithmic distribution.
"""
from dataclasses import dataclass


@dataclass
class PostEngagementInput:
    likes: int | None
    comments: int | None
    saves: int | None
    shares: int | None
    reach: int | None
    impressions: int | None


def engagement_rate(post: PostEngagementInput) -> float | None:
    """
    (likes + comments + saves + shares) / reach (or impressions as fallback).
    Returns None when there isn't enough data to compute a meaningful rate.
    """
    denominator = post.reach or post.impressions
    if not denominator:
        return None

    numerator = sum(v or 0 for v in (post.likes, post.comments, post.saves, post.shares))
    return round(numerator / denominator, 5)


def save_rate(post: PostEngagementInput) -> float | None:
    denominator = post.reach or post.impressions
    if not denominator or post.saves is None:
        return None
    return round(post.saves / denominator, 5)


def engagement_breakdown(post: PostEngagementInput) -> dict:
    """Per-metric rates, useful for the post detail view."""
    denominator = post.reach or post.impressions
    if not denominator:
        return {}
    return {
        "like_rate": round((post.likes or 0) / denominator, 5),
        "comment_rate": round((post.comments or 0) / denominator, 5),
        "save_rate": round((post.saves or 0) / denominator, 5),
        "share_rate": round((post.shares or 0) / denominator, 5),
    }
