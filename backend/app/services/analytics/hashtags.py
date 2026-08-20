"""
Hashtag analysis derived entirely from an account's own post history.

This is descriptive, not causal. A hashtag appearing on high-performing
posts does not mean the hashtag caused that performance -- the image, the
timing, the caption, and the account's momentum at the time all vary
together, and none of it is controlled for. Instagram also does not
expose per-hashtag attribution, so there is no data source that could
settle it. Every number here is "posts carrying this tag averaged X",
and the API returns an explicit caveat alongside the numbers so the UI
cannot present them as a growth lever.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, median

# A hashtag: '#' followed by letters/digits/underscore. Instagram allows
# unicode letters, so \w with re.UNICODE covers accented tags too. Tags
# are compared case-insensitively (Instagram treats them that way) but
# reported in the casing the author most often used.
HASHTAG_PATTERN = re.compile(r"#(\w+)", re.UNICODE)

# Below this many posts a per-tag average is noise, so performance is
# withheld rather than shown with a caveat nobody reads.
MIN_POSTS_PER_TAG = 3

# Fewer tagged posts than this and the whole feature stays quiet.
MIN_TAGGED_POSTS = 5

CAVEAT = (
    "These are averages for posts that happened to carry each tag, drawn only from "
    "this account's own history. They do not show that a tag caused the result -- "
    "the image, caption, and timing all varied too, and Instagram does not report "
    "per-hashtag attribution."
)


@dataclass
class TaggedPost:
    caption: str | None
    engagement_rate: float | None


@dataclass
class HashtagStat:
    tag: str
    post_count: int
    avg_engagement_rate: float | None
    # Ratio against the account's median post. 1.0 means "in line with
    # this account's typical post"; None when the sample is too small.
    vs_median: float | None


def extract_hashtags(caption: str | None) -> list[str]:
    """Return the distinct hashtags in a caption, lowercased."""
    if not caption:
        return []
    # dict.fromkeys preserves first-seen order while de-duplicating, so a
    # tag repeated in one caption is not counted twice.
    return list(dict.fromkeys(m.lower() for m in HASHTAG_PATTERN.findall(caption)))


def analyze_hashtags(posts: list[TaggedPost], limit: int = 15) -> dict:
    """
    Group an account's posts by hashtag and summarize performance.

    Returns a dict with `has_enough_data`, the ranked `hashtags`, and the
    caveat text the UI must display alongside them.
    """
    rates_by_tag: dict[str, list[float]] = defaultdict(list)
    counts_by_tag: dict[str, int] = defaultdict(int)
    # Track original casing so "#StudioLight" isn't reported as "#studiolight".
    casings: dict[str, list[str]] = defaultdict(list)

    all_rates: list[float] = []
    tagged_post_count = 0

    for post in posts:
        tags = extract_hashtags(post.caption)
        if tags:
            tagged_post_count += 1
        if post.engagement_rate is not None:
            all_rates.append(post.engagement_rate)
        for raw in HASHTAG_PATTERN.findall(post.caption or ""):
            casings[raw.lower()].append(raw)
        for tag in tags:
            counts_by_tag[tag] += 1
            if post.engagement_rate is not None:
                rates_by_tag[tag].append(post.engagement_rate)

    if tagged_post_count < MIN_TAGGED_POSTS:
        return {
            "has_enough_data": False,
            "message": "Not enough historical data yet.",
            "hashtags": [],
            "caveat": CAVEAT,
        }

    account_median = median(all_rates) if all_rates else None

    stats: list[HashtagStat] = []
    for tag, count in counts_by_tag.items():
        rates = rates_by_tag.get(tag, [])
        enough = count >= MIN_POSTS_PER_TAG and bool(rates)
        avg = round(mean(rates), 5) if enough else None
        vs_median = (
            round(avg / account_median, 2)
            if enough and avg is not None and account_median
            else None
        )
        # Report the most frequently used casing for this tag.
        variants = casings.get(tag, [tag])
        display = max(set(variants), key=variants.count)
        stats.append(
            HashtagStat(
                tag=display,
                post_count=count,
                avg_engagement_rate=avg,
                vs_median=vs_median,
            )
        )

    # Tags with enough data rank first (by performance); the rest follow
    # by frequency so the user still sees what they habitually use.
    stats.sort(
        key=lambda s: (
            s.avg_engagement_rate is not None,
            s.avg_engagement_rate or 0,
            s.post_count,
        ),
        reverse=True,
    )

    return {
        "has_enough_data": True,
        "message": None,
        "hashtags": stats[:limit],
        "caveat": CAVEAT,
    }
