from app.services.analytics.engagement import (
    PostEngagementInput,
    engagement_breakdown,
    engagement_rate,
    save_rate,
)


def test_engagement_rate_uses_reach_when_available():
    post = PostEngagementInput(likes=100, comments=10, saves=5, shares=2, reach=1000, impressions=1500)
    assert engagement_rate(post) == round((100 + 10 + 5 + 2) / 1000, 5)


def test_engagement_rate_falls_back_to_impressions():
    post = PostEngagementInput(likes=50, comments=5, saves=0, shares=0, reach=None, impressions=500)
    assert engagement_rate(post) == round(55 / 500, 5)


def test_engagement_rate_none_without_denominator():
    post = PostEngagementInput(likes=50, comments=5, saves=0, shares=0, reach=None, impressions=None)
    assert engagement_rate(post) is None


def test_engagement_rate_handles_missing_metrics_as_zero():
    post = PostEngagementInput(likes=None, comments=None, saves=None, shares=None, reach=100, impressions=None)
    assert engagement_rate(post) == 0.0


def test_save_rate():
    post = PostEngagementInput(likes=10, comments=1, saves=8, shares=0, reach=200, impressions=None)
    assert save_rate(post) == round(8 / 200, 5)


def test_save_rate_none_when_saves_missing():
    post = PostEngagementInput(likes=10, comments=1, saves=None, shares=0, reach=200, impressions=None)
    assert save_rate(post) is None


def test_engagement_breakdown_rates():
    post = PostEngagementInput(likes=20, comments=2, saves=4, shares=1, reach=100, impressions=None)
    breakdown = engagement_breakdown(post)
    assert breakdown["like_rate"] == 0.2
    assert breakdown["comment_rate"] == 0.02
    assert breakdown["save_rate"] == 0.04
    assert breakdown["share_rate"] == 0.01
