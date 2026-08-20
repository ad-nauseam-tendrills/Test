"""
Caption feature analysis.

Extracts structural properties from an account's own captions -- length,
whether it asks a question, how long the first line is, emoji use, line
breaks -- and reports how posts in each group performed relative to that
account's median.

Same discipline as the hashtag panel: these are group averages over posts
that happened to share a property, not evidence that the property caused
the result. Every group needs a minimum sample before a number is shown,
and the caveat travels with the data.

Nothing here needs an external API. It runs on captions already stored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import mean, median

# A group needs this many posts before its average means anything.
MIN_POSTS_PER_GROUP = 4

# And the account needs this many captioned posts overall.
MIN_CAPTIONED_POSTS = 8

CAVEAT = (
    "Each row averages the posts that happened to share that trait, from this "
    "account's history only. Traits overlap and the image itself varies far more "
    "than the caption does, so treat these as observations about your habits "
    "rather than levers to pull."
)

# Matches most emoji ranges. Not exhaustive across every Unicode revision,
# but close enough to distinguish "uses emoji" from "doesn't".
EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿]"
)
HASHTAG_PATTERN = re.compile(r"#\w+", re.UNICODE)
MENTION_PATTERN = re.compile(r"@\w+")


@dataclass
class CaptionedPost:
    caption: str | None
    engagement_rate: float | None


@dataclass
class FeatureGroupStat:
    feature: str  # e.g. "Length"
    group: str  # e.g. "Short (under 80 chars)"
    post_count: int
    avg_engagement_rate: float | None
    vs_median: float | None


def _strip_tags(caption: str) -> str:
    """Caption body with hashtags and mentions removed, for length measures."""
    without = HASHTAG_PATTERN.sub("", caption)
    without = MENTION_PATTERN.sub("", without)
    return re.sub(r"\s+", " ", without).strip()


def describe_caption(caption: str) -> dict[str, str]:
    """
    Bucket one caption into a group per feature. Buckets rather than raw
    values because an artist has tens of posts, not thousands -- a
    continuous correlation over 30 points would be noise dressed up as
    insight.
    """
    body = _strip_tags(caption)
    length = len(body)
    lines = [ln for ln in caption.splitlines() if ln.strip()]
    first_line = _strip_tags(lines[0]) if lines else ""

    if length == 0:
        length_group = "Tags only (no text)"
    elif length < 80:
        length_group = "Short (under 80 chars)"
    elif length < 250:
        length_group = "Medium (80-250 chars)"
    else:
        length_group = "Long (250+ chars)"

    return {
        "Length": length_group,
        "Question": "Asks a question" if "?" in body else "No question",
        "Emoji": "Uses emoji" if EMOJI_PATTERN.search(caption) else "No emoji",
        "Structure": "Multi-line" if len(lines) > 1 else "Single block",
        "Opening line": (
            "Short opener (under 60 chars)" if 0 < len(first_line) < 60 else "Long opener"
        ),
    }


def analyze_caption_features(posts: list[CaptionedPost]) -> dict:
    """Group an account's posts by caption trait and summarize performance."""
    captioned = [p for p in posts if p.caption and p.caption.strip()]

    if len(captioned) < MIN_CAPTIONED_POSTS:
        return {
            "has_enough_data": False,
            "message": "Not enough historical data yet.",
            "features": [],
            "caveat": CAVEAT,
        }

    all_rates = [p.engagement_rate for p in captioned if p.engagement_rate is not None]
    account_median = median(all_rates) if all_rates else None

    # feature -> group -> [rates], plus a parallel count so posts with no
    # engagement figure still contribute to the sample size.
    buckets: dict[str, dict[str, list[float]]] = {}
    counts: dict[str, dict[str, int]] = {}

    for post in captioned:
        for feature, group in describe_caption(post.caption or "").items():
            counts.setdefault(feature, {}).setdefault(group, 0)
            counts[feature][group] += 1
            if post.engagement_rate is not None:
                buckets.setdefault(feature, {}).setdefault(group, []).append(post.engagement_rate)

    results: list[FeatureGroupStat] = []
    for feature, groups in counts.items():
        # A feature only tells you something if at least two of its groups
        # are well-sampled -- otherwise there is nothing to compare.
        comparable = [
            g for g, n in groups.items() if n >= MIN_POSTS_PER_GROUP and buckets.get(feature, {}).get(g)
        ]
        if len(comparable) < 2:
            continue

        for group in comparable:
            rates = buckets[feature][group]
            avg = round(mean(rates), 5)
            results.append(
                FeatureGroupStat(
                    feature=feature,
                    group=group,
                    post_count=counts[feature][group],
                    avg_engagement_rate=avg,
                    vs_median=(
                        round(avg / account_median, 2) if account_median else None
                    ),
                )
            )

    results.sort(key=lambda r: (r.feature, -(r.avg_engagement_rate or 0)))

    return {
        "has_enough_data": bool(results),
        "message": None if results else "Not enough variety in your captions to compare yet.",
        "features": results,
        "caveat": CAVEAT,
    }
