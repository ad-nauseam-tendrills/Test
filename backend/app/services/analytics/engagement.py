"""
Engagement calculations.

All rates are expressed as plain ratios (e.g. 0.045 == 4.5%) computed
against reach when available, falling back to views and then impressions.
Reach is preferred because it is a better denominator for judging how
well a post performed with the people who actually saw it, versus
followers-count which does not account for algorithmic distribution.

`views` and `impressions` are the same underlying idea across a Meta API
change (impressions was deprecated for media created after 2024-07-02),
so a post carries at most one of them and either serves as a fallback.
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
    views: int | None = None
    follower_count: int | None = None


def interaction_total(post: PostEngagementInput) -> int:
    return sum(v or 0 for v in (post.likes, post.comments, post.saves, post.shares))


def engagement_rate_by_followers(post: PostEngagementInput) -> float | None:
    """
    (likes + comments + saves + shares) / followers.

    A second, deliberately separate rate from engagement_rate() above.
    Published industry benchmarks are all computed per follower, so this
    is the only rate that can honestly be compared against them -- see
    baselines.py. It is NOT interchangeable with the reach-normalized
    rate: reach is usually well below follower count, so the same post
    scores several times higher there.
    """
    if not post.follower_count:
        return None
    return round(interaction_total(post) / post.follower_count, 6)


def _denominator(post: PostEngagementInput) -> int | None:
    return post.reach or post.views or post.impressions


def engagement_rate(post: PostEngagementInput) -> float | None:
    """
    (likes + comments + saves + shares) / reach (or views/impressions as
    fallback). Returns None when there isn't enough data to compute a
    meaningful rate.
    """
    denominator = _denominator(post)
    if not denominator:
        return None

    return round(interaction_total(post) / denominator, 5)


def save_rate(post: PostEngagementInput) -> float | None:
    denominator = _denominator(post)
    if not denominator or post.saves is None:
        return None
    return round(post.saves / denominator, 5)


def engagement_breakdown(post: PostEngagementInput) -> dict:
    """Per-metric rates, useful for the post detail view."""
    denominator = _denominator(post)
    if not denominator:
        return {}
    return {
        "like_rate": round((post.likes or 0) / denominator, 5),
        "comment_rate": round((post.comments or 0) / denominator, 5),
        "save_rate": round((post.saves or 0) / denominator, 5),
        "share_rate": round((post.shares or 0) / denominator, 5),
    }
