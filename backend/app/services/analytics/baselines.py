"""
Population baselines, for accounts without enough history of their own.

Everything else in this product reasons from the account's own past
posts, which is honest but useless on day one: a brand-new account has no
history to compare against, so every score falls back to a flat 50 and
the dashboard says "not enough data" indefinitely.

This module supplies a *prior* -- a published population median -- and a
way to blend it with whatever history does exist, so guidance degrades
smoothly instead of switching on at a threshold. With no posts you see
the population figure, clearly labelled as such. As posts accumulate the
account's own numbers take over, and the prior fades out.

--- The unit trap ---
The published benchmarks below are engagement **per follower**. The rate
used everywhere else in this app is engagement **per reach** (see
engagement.py), because reach is the better denominator for judging a
post against the people who actually saw it. The two are not comparable:
reach is typically far smaller than follower count, so a reach-normalized
rate reads several times higher for the same post.

Mixing them would silently corrupt every comparison, so this module works
exclusively in follower-normalized space and the API returns the two
rates under separate, explicitly-named fields.

--- Honesty ---
These are medians across large samples of other people's accounts. They
are a reference point, not a target and not a prediction. Published
studies disagree substantially -- Rival IQ's 2026 median is 0.30% while
Socialinsider's is 0.48%, measured the same way on different populations
-- so treat the number as an order of magnitude, not a precise bar.
"""
from __future__ import annotations

from dataclasses import dataclass

# --- Published benchmarks -------------------------------------------------
#
# Source: Socialinsider's 2026 Instagram benchmarks, chosen over Rival IQ's
# because Rival IQ samples brand/company accounts (18 industries x ~150
# companies) while this product is built for individual artists and
# photographers, whose accounts behave more like the creator population
# Socialinsider measures. Both are cited in the README so the choice --
# and the disagreement between them -- stays visible.
#
# All values are (likes + comments + saves + shares) / followers, per post.
# Retrieved August 2026. These drift year to year; re-check them rather
# than assuming they stay accurate.
BENCHMARK_SOURCE = "Socialinsider 2026 Instagram benchmarks"
BENCHMARK_RETRIEVED = "August 2026"

BASELINE_ENGAGEMENT_BY_FOLLOWERS = 0.0048

# Per-format medians from the same study. Instagram reports Reels as
# VIDEO through the API, so Reels' figure maps to VIDEO.
BASELINE_BY_MEDIA_TYPE: dict[str, float] = {
    "CAROUSEL_ALBUM": 0.0055,
    "VIDEO": 0.0048,
    "IMAGE": 0.0033,
}

# How much the prior is worth, expressed in posts. At this many posts of
# your own the blend is 50/50; by ~30 posts your own data carries ~86%.
# Deliberately small: the prior exists to avoid a cold start, not to drag
# a real account toward the average.
PRIOR_WEIGHT_POSTS = 5


@dataclass
class BlendedRate:
    """A baseline-blended statistic, carrying its own provenance."""

    value: float
    own_value: float | None
    baseline_value: float
    own_post_count: int
    # 0.0 = entirely the population baseline, 1.0 = entirely this account.
    own_weight: float

    @property
    def confidence(self) -> str:
        if self.own_post_count == 0:
            return "baseline only"
        if self.own_weight < 0.5:
            return "mostly baseline"
        if self.own_weight < 0.85:
            return "mixed"
        return "your account"

    def describe(self) -> str:
        """Plain-language provenance, shown next to the number in the UI."""
        if self.own_post_count == 0:
            return (
                f"No posts imported yet, so this is the population median from "
                f"{BENCHMARK_SOURCE} ({BENCHMARK_RETRIEVED}) rather than anything "
                f"about your account."
            )
        pct = round(self.own_weight * 100)
        return (
            f"Blends your {self.own_post_count} post"
            f"{'s' if self.own_post_count != 1 else ''} ({pct}% of the weight) with the "
            f"population median from {BENCHMARK_SOURCE} ({100 - pct}%). The baseline's "
            f"share shrinks as you import more posts."
        )


def blend_with_baseline(
    own_value: float | None,
    own_post_count: int,
    baseline_value: float,
    prior_weight: float = PRIOR_WEIGHT_POSTS,
) -> BlendedRate:
    """
    Shrink an account's own average toward a population baseline, in
    proportion to how little data backs it.

        blended = (n * own + k * baseline) / (n + k)

    This is ordinary empirical-Bayes shrinkage, not a model: with n=0 the
    result is exactly the baseline, and as n grows the baseline's pull
    falls away. It keeps a single fluke post from reading as a trend
    without discarding it.
    """
    if own_value is None or own_post_count <= 0:
        return BlendedRate(
            value=baseline_value,
            own_value=None,
            baseline_value=baseline_value,
            own_post_count=max(0, own_post_count),
            own_weight=0.0,
        )

    own_weight = own_post_count / (own_post_count + prior_weight)
    blended = (own_post_count * own_value + prior_weight * baseline_value) / (
        own_post_count + prior_weight
    )
    return BlendedRate(
        value=blended,
        own_value=own_value,
        baseline_value=baseline_value,
        own_post_count=own_post_count,
        own_weight=own_weight,
    )


def baseline_for_media_type(media_type: str) -> float:
    """Population median for a media type, falling back to the overall one."""
    return BASELINE_BY_MEDIA_TYPE.get(
        (media_type or "").upper(), BASELINE_ENGAGEMENT_BY_FOLLOWERS
    )


def relative_to_baseline(value: float | None, baseline_value: float) -> float | None:
    """
    `value` as a multiple of the baseline: 1.0 means level with it, 2.0
    means twice it. Returned instead of a percentage difference because
    engagement rates are small numbers where a ratio reads more clearly.
    """
    if value is None or not baseline_value:
        return None
    return round(value / baseline_value, 3)
