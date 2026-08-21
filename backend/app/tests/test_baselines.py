"""
Tests for population baselines and cold-start behaviour.

The thing these guard is a brand-new account: with no history, every
score used to collapse to a flat 50 and the dashboard said "not enough
data" forever. They also guard the unit trap -- published benchmarks are
per-follower while the rest of the app is per-reach, and blending the two
would corrupt every comparison silently.
"""
import pytest

from app.services.analytics.baselines import (
    BASELINE_ENGAGEMENT_BY_FOLLOWERS,
    PRIOR_WEIGHT_POSTS,
    baseline_for_media_type,
    blend_with_baseline,
    relative_to_baseline,
)
from app.services.analytics.engagement import (
    PostEngagementInput,
    engagement_rate,
    engagement_rate_by_followers,
)


# --- Shrinkage -----------------------------------------------------------


def test_no_history_yields_exactly_the_baseline():
    blended = blend_with_baseline(own_value=None, own_post_count=0, baseline_value=0.005)
    assert blended.value == 0.005
    assert blended.own_weight == 0.0
    assert blended.confidence == "baseline only"
    assert "No posts imported yet" in blended.describe()


def test_own_data_takes_over_as_posts_accumulate():
    baseline, own = 0.005, 0.010

    few = blend_with_baseline(own_value=own, own_post_count=1, baseline_value=baseline)
    many = blend_with_baseline(own_value=own, own_post_count=100, baseline_value=baseline)

    # Both sit between the two inputs, but more posts pull harder toward
    # the account's own number.
    assert baseline < few.value < many.value < own
    assert few.own_weight < many.own_weight
    assert many.confidence == "your account"


def test_blend_is_fifty_fifty_at_the_prior_weight():
    blended = blend_with_baseline(
        own_value=0.010, own_post_count=PRIOR_WEIGHT_POSTS, baseline_value=0.005
    )
    assert blended.value == pytest.approx(0.0075)
    assert blended.own_weight == pytest.approx(0.5)


def test_blend_never_leaves_the_interval_between_its_inputs():
    for count in (1, 3, 7, 40):
        for own, baseline in ((0.001, 0.02), (0.02, 0.001)):
            value = blend_with_baseline(own, count, baseline).value
            assert min(own, baseline) <= value <= max(own, baseline)


def test_zero_own_rate_is_kept_not_treated_as_missing():
    """An account whose posts genuinely got no engagement is not 'no data'."""
    blended = blend_with_baseline(own_value=0.0, own_post_count=20, baseline_value=0.005)
    assert blended.value < 0.005
    assert blended.own_value == 0.0
    assert blended.own_weight > 0.5
    assert blended.confidence != "baseline only"


def test_media_type_baselines_are_distinct_and_fall_back():
    assert baseline_for_media_type("CAROUSEL_ALBUM") != baseline_for_media_type("IMAGE")
    assert baseline_for_media_type("carousel_album") == baseline_for_media_type("CAROUSEL_ALBUM")
    assert baseline_for_media_type("SOMETHING_NEW") == BASELINE_ENGAGEMENT_BY_FOLLOWERS


def test_relative_to_baseline_reads_as_a_multiple():
    assert relative_to_baseline(0.010, 0.005) == 2.0
    assert relative_to_baseline(0.005, 0.005) == 1.0
    assert relative_to_baseline(None, 0.005) is None
    assert relative_to_baseline(0.005, 0) is None


# --- The unit trap -------------------------------------------------------


def test_follower_and_reach_rates_are_different_numbers():
    """
    Published benchmarks are per-follower; the dashboard's headline rate
    is per-reach. Reach is normally far below follower count, so the same
    post scores much higher per-reach -- these must never be conflated.
    """
    post = PostEngagementInput(
        likes=90, comments=6, saves=3, shares=1, reach=500, impressions=None, views=None,
        follower_count=10_000,
    )
    by_reach = engagement_rate(post)
    by_followers = engagement_rate_by_followers(post)

    assert by_reach == pytest.approx(100 / 500)
    assert by_followers == pytest.approx(100 / 10_000)
    assert by_reach > by_followers * 10


def test_follower_rate_is_none_without_a_follower_count():
    post = PostEngagementInput(
        likes=10, comments=0, saves=0, shares=0, reach=100, impressions=None, views=None,
        follower_count=None,
    )
    assert engagement_rate_by_followers(post) is None
    # The reach-normalized rate is unaffected.
    assert engagement_rate(post) == pytest.approx(0.1)


def test_follower_rate_survives_missing_interaction_metrics():
    post = PostEngagementInput(
        likes=50, comments=None, saves=None, shares=None, reach=None, impressions=None,
        views=None, follower_count=1000,
    )
    assert engagement_rate_by_followers(post) == pytest.approx(0.05)


# --- Cold-start scores ---------------------------------------------------


from types import SimpleNamespace  # noqa: E402

from app.services.recommendations.scoring import (  # noqa: E402
    MIN_POSTS_FOR_SIMILARITY,
    MIN_POSTS_FOR_TIMING,
    score_historical_similarity,
    score_timing_opportunity,
)


def _metrics(aspect_ratio: float):
    return SimpleNamespace(aspect_ratio=aspect_ratio)


def test_similarity_scores_the_crop_with_no_history():
    """
    Crop is measured from the image itself, so it is just as valid on day
    one. A well-cropped image must not score the same as a badly cropped
    one merely because the account is new.
    """
    good = score_historical_similarity(_metrics(4 / 5), [], total_posts=0)
    bad = score_historical_similarity(_metrics(2.4), [], total_posts=0)

    assert good.score > bad.score
    assert good.score > 50
    assert good.label != "Not enough data"
    # And it says plainly that this is not about the account's history.
    assert "not enough to compare" in good.explanation
    assert "population figure" in good.explanation


def test_similarity_uses_own_history_once_there_is_enough():
    stats = [
        {"media_type": "IMAGE", "avg_engagement_rate": 0.09},
        {"media_type": "VIDEO", "avg_engagement_rate": 0.03},
    ]
    result = score_historical_similarity(
        _metrics(4 / 5), stats, total_posts=MIN_POSTS_FOR_SIMILARITY
    )
    assert "this account's past" in result.explanation
    assert "population figure" not in result.explanation


def test_timing_falls_back_to_where_the_audience_actually_is():
    """
    With no posting history, follower geography is a real signal about
    this specific account -- unlike a borrowed population average.
    """
    # 09:00 UTC: Japan (UTC+9) is at 18:00 and awake; the US (UTC-6) is at
    # 03:00 and asleep. Picked deliberately -- at many other hours both
    # are awake and the two are indistinguishable.
    tokyo_audience = score_timing_opportunity(
        current_hour=9, current_day_index=2, by_day_of_week=[], by_hour_of_day=[],
        total_posts=0, audience_countries={"JP": 1000},
    )
    us_audience = score_timing_opportunity(
        current_hour=9, current_day_index=2, by_day_of_week=[], by_hour_of_day=[],
        total_posts=0, audience_countries={"US": 1000},
    )

    assert tokyo_audience.score > us_audience.score
    assert tokyo_audience.label != "Not enough data"
    assert "audience's location" in tokyo_audience.explanation
    # Never overclaims: awake is not the same as receptive.
    assert "not the same as being receptive" in tokyo_audience.explanation


def test_timing_stays_neutral_when_there_is_nothing_to_fall_back_on():
    result = score_timing_opportunity(
        current_hour=12, current_day_index=2, by_day_of_week=[], by_hour_of_day=[],
        total_posts=0, audience_countries={},
    )
    assert result.score == 50
    assert result.label == "Not enough data"
    assert "withholds it below" in result.explanation


def test_timing_prefers_own_history_over_the_fallback():
    by_day = [{"day": "Wednesday", "day_index": 2, "post_count": 5, "avg_engagement_rate": 0.09}]
    by_hour = [{"hour": 9, "post_count": 5, "avg_engagement_rate": 0.09}]
    result = score_timing_opportunity(
        current_hour=9, current_day_index=2, by_day_of_week=by_day, by_hour_of_day=by_hour,
        total_posts=MIN_POSTS_FOR_TIMING, audience_countries={"US": 1000},
    )
    assert "this account's own historical" in result.explanation
    assert "audience's location" not in result.explanation
