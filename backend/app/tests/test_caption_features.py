from app.services.analytics.caption_features import (
    MIN_POSTS_PER_GROUP,
    CaptionedPost,
    analyze_caption_features,
    describe_caption,
)


# --- Feature extraction --------------------------------------------------


def test_short_caption_bucketed_as_short():
    assert describe_caption("Studio light.")["Length"] == "Short (under 80 chars)"


def test_long_caption_bucketed_as_long():
    assert describe_caption("word " * 60)["Length"] == "Long (250+ chars)"


def test_hashtags_excluded_from_length():
    """A short caption with a tag wall is still a short caption."""
    caption = "Nice light. " + " ".join(f"#tag{i}" for i in range(30))
    assert describe_caption(caption)["Length"] == "Short (under 80 chars)"


def test_caption_that_is_only_tags():
    assert describe_caption("#art #studio #film")["Length"] == "Tags only (no text)"


def test_question_detection():
    assert describe_caption("What do you think?")["Question"] == "Asks a question"
    assert describe_caption("This is a statement.")["Question"] == "No question"


def test_question_mark_inside_hashtag_does_not_count():
    # '?' cannot appear in a tag, but tags are stripped before checking,
    # so a tag-only caption is never a question.
    assert describe_caption("#art #studio")["Question"] == "No question"


def test_emoji_detection():
    assert describe_caption("New work 🎨")["Emoji"] == "Uses emoji"
    assert describe_caption("New work")["Emoji"] == "No emoji"


def test_structure_detection():
    assert describe_caption("one line only")["Structure"] == "Single block"
    assert describe_caption("first line\n\nsecond line")["Structure"] == "Multi-line"


def test_opening_line_length():
    assert describe_caption("Short hook.\nThen more text.")["Opening line"] == (
        "Short opener (under 60 chars)"
    )
    long_first = "x" * 90 + "\nsecond"
    assert describe_caption(long_first)["Opening line"] == "Long opener"


def test_every_caption_gets_all_features():
    features = describe_caption("Anything at all")
    assert set(features) == {"Length", "Question", "Emoji", "Structure", "Opening line"}


# --- Aggregation ---------------------------------------------------------


def _posts(spec):
    return [CaptionedPost(caption=c, engagement_rate=r) for c, r in spec]


def test_insufficient_data_below_threshold():
    report = analyze_caption_features(_posts([("A caption", 0.05)] * 3))
    assert report["has_enough_data"] is False
    assert report["features"] == []


def test_uncaptioned_posts_do_not_count_toward_threshold():
    report = analyze_caption_features(_posts([(None, 0.05)] * 20))
    assert report["has_enough_data"] is False


def test_compares_groups_within_a_feature():
    posts = _posts(
        [("Do you like this?", 0.10)] * MIN_POSTS_PER_GROUP
        + [("A plain statement.", 0.04)] * MIN_POSTS_PER_GROUP
    )
    report = analyze_caption_features(posts)
    assert report["has_enough_data"] is True

    questions = [f for f in report["features"] if f.feature == "Question"]
    by_group = {f.group: f for f in questions}
    assert by_group["Asks a question"].avg_engagement_rate == 0.10
    assert by_group["No question"].avg_engagement_rate == 0.04
    # Higher-performing group sorts first within its feature.
    assert questions[0].group == "Asks a question"


def test_feature_with_only_one_populated_group_is_omitted():
    """Nothing to compare means the feature says nothing -- drop it."""
    posts = _posts([("Every caption asks something?", 0.05)] * 12)
    report = analyze_caption_features(posts)
    features_present = {f.feature for f in report["features"]}
    assert "Question" not in features_present


def test_group_below_min_sample_is_omitted():
    posts = _posts(
        [("A plain statement here.", 0.05)] * 12
        + [("A rare question?", 0.90)] * (MIN_POSTS_PER_GROUP - 1)
    )
    report = analyze_caption_features(posts)
    question_groups = {f.group for f in report["features"] if f.feature == "Question"}
    # The thin, wildly-performing group must not appear at all.
    assert "Asks a question" not in question_groups


def test_vs_median_is_relative_to_account():
    posts = _posts(
        [("Do you like this?", 0.10)] * MIN_POSTS_PER_GROUP
        + [("A plain statement.", 0.05)] * MIN_POSTS_PER_GROUP
    )
    report = analyze_caption_features(posts)
    by_group = {f.group: f for f in report["features"] if f.feature == "Question"}
    # Median across all eight posts is 0.075.
    assert by_group["Asks a question"].vs_median == round(0.10 / 0.075, 2)


def test_posts_without_engagement_still_count_in_sample():
    posts = _posts(
        [("Do you like this?", 0.10)] * MIN_POSTS_PER_GROUP
        + [("Do you like this?", None)] * 2
        + [("A plain statement.", 0.05)] * MIN_POSTS_PER_GROUP
    )
    report = analyze_caption_features(posts)
    by_group = {f.group: f for f in report["features"] if f.feature == "Question"}
    assert by_group["Asks a question"].post_count == MIN_POSTS_PER_GROUP + 2
    # But the average is computed only from posts that have a rate.
    assert by_group["Asks a question"].avg_engagement_rate == 0.10


def test_caveat_disclaims_causation():
    posts = _posts(
        [("Do you like this?", 0.10)] * MIN_POSTS_PER_GROUP
        + [("A plain statement.", 0.05)] * MIN_POSTS_PER_GROUP
    )
    caveat = analyze_caption_features(posts)["caveat"].lower()
    assert "overlap" in caveat
    assert "rather than levers" in caveat
