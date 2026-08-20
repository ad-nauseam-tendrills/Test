from app.services.analytics.hashtags import (
    MIN_POSTS_PER_TAG,
    TaggedPost,
    analyze_hashtags,
    extract_hashtags,
)


# --- Extraction ---------------------------------------------------------


def test_extract_hashtags_basic():
    assert extract_hashtags("A study in light #photography #studio") == ["photography", "studio"]


def test_extract_hashtags_lowercases():
    assert extract_hashtags("#StudioLight #FILM") == ["studiolight", "film"]


def test_extract_hashtags_deduplicates_within_one_caption():
    assert extract_hashtags("#art and more #art") == ["art"]


def test_extract_hashtags_handles_none_and_empty():
    assert extract_hashtags(None) == []
    assert extract_hashtags("") == []
    assert extract_hashtags("no tags here") == []


def test_extract_hashtags_ignores_bare_hash():
    assert extract_hashtags("number # 5") == []


def test_extract_hashtags_supports_unicode():
    assert extract_hashtags("#café #naturmorte") == ["café", "naturmorte"]


# --- Aggregation --------------------------------------------------------


def _posts(spec: list[tuple[str | None, float | None]]) -> list[TaggedPost]:
    return [TaggedPost(caption=c, engagement_rate=r) for c, r in spec]


def test_reports_insufficient_data_below_threshold():
    report = analyze_hashtags(_posts([("#art", 0.05), ("#art", 0.04)]))
    assert report["has_enough_data"] is False
    assert report["message"] == "Not enough historical data yet."
    assert report["hashtags"] == []


def test_aggregates_engagement_per_tag():
    posts = _posts(
        [
            ("#film study", 0.06),
            ("#film again", 0.08),
            ("#film more", 0.10),
            ("#digital one", 0.02),
            ("#digital two", 0.02),
            ("#digital three", 0.02),
        ]
    )
    report = analyze_hashtags(posts)
    assert report["has_enough_data"] is True

    by_tag = {h.tag: h for h in report["hashtags"]}
    assert by_tag["film"].post_count == 3
    assert by_tag["film"].avg_engagement_rate == 0.08
    assert by_tag["digital"].avg_engagement_rate == 0.02
    # Stronger tag ranks first.
    assert report["hashtags"][0].tag == "film"


def test_withholds_performance_for_thin_tags():
    """A tag used once must not get an average -- one post is noise."""
    posts = _posts(
        [
            ("#common a", 0.05),
            ("#common b", 0.05),
            ("#common c", 0.05),
            ("#rare d", 0.99),
            ("#common e", 0.05),
            ("#common f", 0.05),
        ]
    )
    report = analyze_hashtags(posts)
    by_tag = {h.tag: h for h in report["hashtags"]}

    assert by_tag["rare"].post_count == 1
    assert by_tag["rare"].avg_engagement_rate is None
    assert by_tag["rare"].vs_median is None
    # Despite its huge single-post rate, it must not outrank the real one.
    assert report["hashtags"][0].tag == "common"


def test_vs_median_is_relative_to_account():
    posts = _posts(
        [
            ("#strong a", 0.10),
            ("#strong b", 0.10),
            ("#strong c", 0.10),
            ("#weak d", 0.05),
            ("#weak e", 0.05),
            ("#weak f", 0.05),
        ]
    )
    report = analyze_hashtags(posts)
    by_tag = {h.tag: h for h in report["hashtags"]}
    # Account median across all six posts is 0.075.
    assert by_tag["strong"].vs_median == round(0.10 / 0.075, 2)
    assert by_tag["weak"].vs_median == round(0.05 / 0.075, 2)


def test_reports_most_common_casing():
    posts = _posts(
        [
            ("#StudioLight one", 0.05),
            ("#StudioLight two", 0.05),
            ("#studiolight three", 0.05),
            ("#other four", 0.05),
            ("#other five", 0.05),
        ]
    )
    report = analyze_hashtags(posts)
    tags = [h.tag for h in report["hashtags"]]
    assert "StudioLight" in tags
    assert "studiolight" not in tags


def test_posts_without_engagement_still_counted():
    posts = _posts([("#art a", None)] * 3 + [("#art b", 0.05)] * 3)
    report = analyze_hashtags(posts)
    by_tag = {h.tag: h for h in report["hashtags"]}
    assert by_tag["art"].post_count == 6
    assert by_tag["art"].avg_engagement_rate == 0.05


def test_caveat_disclaims_causation():
    report = analyze_hashtags(_posts([("#art x", 0.05)] * 6))
    caveat = report["caveat"].lower()
    assert "cause" in caveat
    # Must never imply the user should add tags to grow.
    assert "boost" not in caveat
    assert "increase your" not in caveat


def test_respects_limit():
    posts = _posts([(f"#tag{i} caption", 0.05) for i in range(30)])
    report = analyze_hashtags(posts, limit=5)
    assert len(report["hashtags"]) == 5


def test_min_posts_per_tag_constant_is_honoured():
    """A tag at exactly the threshold gets an average; one below does not."""
    at_threshold = _posts([("#edge x", 0.05)] * MIN_POSTS_PER_TAG + [("#pad y", 0.05)] * 5)
    report = analyze_hashtags(at_threshold)
    by_tag = {h.tag: h for h in report["hashtags"]}
    assert by_tag["edge"].avg_engagement_rate is not None

    below = _posts([("#edge x", 0.05)] * (MIN_POSTS_PER_TAG - 1) + [("#pad y", 0.05)] * 5)
    by_tag_below = {h.tag: h for h in analyze_hashtags(below)["hashtags"]}
    assert by_tag_below["edge"].avg_engagement_rate is None
