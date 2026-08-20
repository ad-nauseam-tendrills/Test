from app.services.analytics.audience import (
    COUNTRY_UTC_OFFSETS,
    MIN_FOLLOWERS_FOR_ANALYSIS,
    analyze_audience_hours,
    awake_fraction_for_hour,
)


# --- Awake fraction ------------------------------------------------------


def test_single_timezone_audience_is_awake_midday_local():
    # UK audience, UTC+0. 12:00 UTC is midday there.
    assert awake_fraction_for_hour(12, {"GB": 1000}) == 1.0


def test_single_timezone_audience_is_asleep_overnight_local():
    # 03:00 UTC is 03:00 in the UK -- outside the waking window.
    assert awake_fraction_for_hour(3, {"GB": 1000}) == 0.0


def test_us_audience_shifted_from_utc():
    # US mapped to UTC-6: 12:00 UTC is 06:00 local, before the window opens.
    assert awake_fraction_for_hour(12, {"US": 1000}) == 0.0
    # 18:00 UTC is 12:00 local -- awake.
    assert awake_fraction_for_hour(18, {"US": 1000}) == 1.0


def test_split_audience_gives_partial_fraction():
    """A half-US half-UK audience is never fully awake at once."""
    demographics = {"US": 500, "GB": 500}
    fraction = awake_fraction_for_hour(13, demographics)
    # 13:00 UTC = 07:00 US (just awake) and 13:00 UK (awake) -> both.
    assert fraction == 1.0

    # 02:00 UTC = 20:00 previous day in the US (awake), 02:00 UK (asleep).
    assert awake_fraction_for_hour(2, demographics) == 0.5


def test_weighting_follows_audience_size():
    # 90% US, 10% UK. At 02:00 UTC only the US portion is awake.
    fraction = awake_fraction_for_hour(2, {"US": 900, "GB": 100})
    assert fraction == 0.9


def test_unknown_countries_are_excluded_not_guessed():
    """An unmapped country must not silently count as UTC+0."""
    # 'ZZ' is not a real code; only GB should be considered.
    assert awake_fraction_for_hour(12, {"GB": 100, "ZZ": 900}) == 1.0
    assert awake_fraction_for_hour(3, {"GB": 100, "ZZ": 900}) == 0.0


def test_returns_none_when_no_known_countries():
    assert awake_fraction_for_hour(12, {"ZZ": 500}) is None
    assert awake_fraction_for_hour(12, {}) is None


def test_country_codes_are_case_insensitive():
    assert awake_fraction_for_hour(12, {"gb": 100}) == awake_fraction_for_hour(12, {"GB": 100})


def test_offsets_are_plausible():
    for code, offset in COUNTRY_UTC_OFFSETS.items():
        assert -12 <= offset <= 14, f"{code} has an impossible offset"
        assert len(code) == 2


# --- Full report ---------------------------------------------------------


def test_reports_insufficient_data_for_small_audience():
    report = analyze_audience_hours({"GB": MIN_FOLLOWERS_FOR_ANALYSIS - 1})
    assert report["has_enough_data"] is False
    assert "100 followers" in report["message"]
    assert report["hours"] == []


def test_full_report_covers_all_hours():
    report = analyze_audience_hours({"US": 600, "GB": 300, "JP": 200})
    assert report["has_enough_data"] is True
    assert len(report["hours"]) == 24
    assert [h.hour_utc for h in report["hours"]] == list(range(24))
    for h in report["hours"]:
        assert 0.0 <= h.awake_fraction <= 1.0


def test_top_countries_ranked_by_size():
    report = analyze_audience_hours({"US": 600, "GB": 300, "JP": 100})
    assert [c["country"] for c in report["top_countries"]] == ["US", "GB", "JP"]
    assert report["top_countries"][0]["share"] == 0.6


def test_coverage_reflects_unmapped_countries():
    """Coverage must expose how much of the audience we could not place."""
    report = analyze_audience_hours({"GB": 500, "ZZ": 500})
    assert report["coverage"] == 0.5


def test_coverage_is_one_when_all_countries_known():
    report = analyze_audience_hours({"GB": 500, "US": 500})
    assert report["coverage"] == 1.0


def test_local_hour_conversion_uses_viewer_offset():
    report = analyze_audience_hours({"US": 1000}, viewer_utc_offset=-5)
    by_utc = {h.hour_utc: h.hour_local for h in report["hours"]}
    assert by_utc[12] == 7  # 12:00 UTC is 07:00 for a UTC-5 viewer
    assert by_utc[2] == 21  # wraps backwards across midnight


def test_caveat_disclaims_prediction():
    report = analyze_audience_hours({"US": 1000})
    caveat = report["caveat"].lower()
    assert "does not predict" in caveat
    assert "daylight saving" in caveat
