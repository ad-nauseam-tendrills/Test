from app.services.analytics.normalization import (
    has_enough_data,
    median_engagement_rate,
    percentile,
    performance_index,
    reach_relative_to_followers,
)


def test_reach_relative_to_followers():
    assert reach_relative_to_followers(500, 1000) == 0.5


def test_reach_relative_to_followers_missing_values():
    assert reach_relative_to_followers(None, 1000) is None
    assert reach_relative_to_followers(500, None) is None
    assert reach_relative_to_followers(500, 0) is None


def test_performance_index_percentile():
    rates = [0.01, 0.02, 0.03, 0.04, 0.05]
    # 0.03 is the median -> 60th percentile (3 of 5 values <= 0.03)
    assert performance_index(0.03, rates) == 60.0


def test_performance_index_top_post():
    rates = [0.01, 0.02, 0.03, 0.04, 0.05]
    assert performance_index(0.05, rates) == 100.0


def test_performance_index_none_without_data():
    assert performance_index(None, [0.1, 0.2]) is None
    assert performance_index(0.1, []) is None


def test_median_engagement_rate():
    assert median_engagement_rate([0.01, 0.03, 0.02]) == 0.02


def test_median_engagement_rate_empty():
    assert median_engagement_rate([]) is None


def test_percentile_basic():
    values = [1, 2, 3, 4, 5]
    assert percentile(values, 50) == 3
    assert percentile(values, 0) == 1
    assert percentile(values, 100) == 5


def test_percentile_empty():
    assert percentile([], 50) is None


def test_has_enough_data():
    assert has_enough_data(10, minimum=5) is True
    assert has_enough_data(3, minimum=5) is False
