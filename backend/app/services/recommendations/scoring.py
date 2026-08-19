"""
Heuristic scoring system.

IMPORTANT: every score produced here is an explicit, explainable heuristic
derived from measurable properties and the account's own historical
statistics. None of these scores are predictions of future likes,
reach, or follower growth, and none should ever be presented that way.
Preferred phrasing: "this post appears more similar to historically
strong posts on this account" -- never "you will get X likes/followers".
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.image_analysis.metrics import ImageMetrics

MIN_POSTS_FOR_TIMING = 10
MIN_POSTS_FOR_SIMILARITY = 5


@dataclass
class ScoreSection:
    score: int
    label: str
    explanation: str


def _clamp(value: float, low: float = 0, high: float = 100) -> int:
    return int(round(max(low, min(high, value))))


def score_image_readiness(metrics: ImageMetrics) -> ScoreSection:
    score = 100.0
    reasons = []

    if metrics.highlight_clipping_pct > 2:
        penalty = min(25, metrics.highlight_clipping_pct * 2)
        score -= penalty
        reasons.append(f"-{penalty:.0f} for highlight clipping ({metrics.highlight_clipping_pct:.1f}% of pixels)")

    if metrics.shadow_clipping_pct > 2:
        penalty = min(20, metrics.shadow_clipping_pct * 1.5)
        score -= penalty
        reasons.append(f"-{penalty:.0f} for shadow clipping ({metrics.shadow_clipping_pct:.1f}% of pixels)")

    if metrics.contrast < 30:
        penalty = min(15, (30 - metrics.contrast) * 0.5)
        score -= penalty
        reasons.append(f"-{penalty:.0f} for low contrast ({metrics.contrast:.0f})")

    if metrics.sharpness < 60:
        penalty = min(20, (60 - metrics.sharpness) * 0.3)
        score -= penalty
        reasons.append(f"-{penalty:.0f} for low sharpness ({metrics.sharpness:.0f})")

    if metrics.brightness < 40 or metrics.brightness > 235:
        score -= 10
        reasons.append("-10 for extreme overall brightness (very dark or very bright)")

    ratio_delta = abs(metrics.aspect_ratio - (4 / 5))
    if ratio_delta > 0.4:
        score -= 5
        reasons.append("-5 for an aspect ratio far from typical feed formats")

    final = _clamp(score)
    explanation = (
        "Starts at 100 and subtracts points for measurable technical issues "
        "(clipped highlights/shadows, low contrast, low sharpness, extreme "
        "brightness). "
        + ("No issues detected." if not reasons else " ".join(reasons) + ".")
    )
    return ScoreSection(score=final, label=_label_for(final), explanation=explanation)


def score_timing_opportunity(
    current_hour: int,
    current_day_index: int,
    by_day_of_week: list[dict],
    by_hour_of_day: list[dict],
    total_posts: int,
) -> ScoreSection:
    if total_posts < MIN_POSTS_FOR_TIMING:
        return ScoreSection(
            score=50,
            label="Not enough data",
            explanation=(
                "Not enough historical data yet to evaluate timing. Default neutral score shown. "
                f"Import at least {MIN_POSTS_FOR_TIMING} historical posts to unlock this score."
            ),
        )

    day_rates = [d["avg_engagement_rate"] for d in by_day_of_week if d["avg_engagement_rate"] is not None]
    hour_rates = [h["avg_engagement_rate"] for h in by_hour_of_day if h["avg_engagement_rate"] is not None]

    day_entry = next((d for d in by_day_of_week if d["day_index"] == current_day_index), None)
    hour_entry = next((h for h in by_hour_of_day if h["hour"] == current_hour), None)

    def percentile_of(value, pool):
        if value is None or not pool:
            return 50.0
        rank = sum(1 for v in pool if v <= value)
        return (rank / len(pool)) * 100

    day_pct = percentile_of(day_entry["avg_engagement_rate"] if day_entry else None, day_rates)
    hour_pct = percentile_of(hour_entry["avg_engagement_rate"] if hour_entry else None, hour_rates)

    combined = (day_pct + hour_pct) / 2
    final = _clamp(combined)
    explanation = (
        "Compares the current day-of-week and hour-of-day against this account's own historical "
        f"average engagement rate for those buckets. Right now ranks around the {final}th percentile "
        "of this account's historical posting times. This reflects past patterns only, not a "
        "guarantee of future performance."
    )
    return ScoreSection(score=final, label=_label_for(final), explanation=explanation)


def score_historical_similarity(
    metrics: ImageMetrics,
    media_type_stats: list[dict],
    total_posts: int,
    assumed_media_type: str = "IMAGE",
) -> ScoreSection:
    if total_posts < MIN_POSTS_FOR_SIMILARITY:
        return ScoreSection(
            score=50,
            label="Not enough data",
            explanation=(
                "Not enough historical data yet to compare this image against past posts. "
                f"Import at least {MIN_POSTS_FOR_SIMILARITY} historical posts to unlock this score."
            ),
        )

    # Component 1: how closely the crop matches Instagram's tallest
    # standard feed ratio (a strong, format-level signal we can measure
    # directly on the new image).
    ratio_delta = abs(metrics.aspect_ratio - (4 / 5))
    format_fit = max(0.0, 100 - ratio_delta * 250)

    # Component 2: how this account's posts of the assumed media type
    # have performed relative to its overall median (metadata-based,
    # since v0.1 does not re-analyze historical post images).
    rates_for_type = next(
        (s["avg_engagement_rate"] for s in media_type_stats if s["media_type"] == assumed_media_type), None
    )
    all_rates = [s["avg_engagement_rate"] for s in media_type_stats if s["avg_engagement_rate"] is not None]
    if rates_for_type is not None and all_rates:
        overall_avg = sum(all_rates) / len(all_rates)
        media_type_fit = 50 + (rates_for_type - overall_avg) / (overall_avg or 1) * 100
        media_type_fit = max(0.0, min(100.0, media_type_fit))
    else:
        media_type_fit = 50.0

    combined = format_fit * 0.5 + media_type_fit * 0.5
    final = _clamp(combined)
    explanation = (
        "Compares this image's crop against Instagram's tallest standard feed format (4:5), and "
        f"compares how this account's past '{assumed_media_type.title()}' posts have performed relative "
        "to its own median. This post appears "
        + ("more similar to" if final >= 60 else "less similar to" if final < 40 else "roughly in line with")
        + " historically stronger posts on this account, based on format alone -- not a prediction of results."
    )
    return ScoreSection(score=final, label=_label_for(final), explanation=explanation)


def score_overall_readiness(
    image_readiness: ScoreSection, timing_opportunity: ScoreSection, historical_similarity: ScoreSection
) -> ScoreSection:
    combined = image_readiness.score * 0.45 + timing_opportunity.score * 0.25 + historical_similarity.score * 0.30
    final = _clamp(combined)
    explanation = (
        f"Weighted average of image readiness (45%, scored {image_readiness.score}), timing opportunity "
        f"(25%, scored {timing_opportunity.score}), and historical similarity (30%, scored "
        f"{historical_similarity.score}). This is a heuristic summary, not a prediction of likes, reach, "
        "or follower growth."
    )
    return ScoreSection(score=final, label=_label_for(final), explanation=explanation)


def _label_for(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 30:
        return "Needs attention"
    return "Poor"
