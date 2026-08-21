from app.services.image_analysis.metrics import ImageMetrics
from app.services.recommendations.rules import generate_recommendations
from app.services.recommendations.scoring import (
    score_historical_similarity,
    score_image_readiness,
    score_overall_readiness,
    score_timing_opportunity,
)


def _base_metrics(**overrides) -> ImageMetrics:
    defaults = dict(
        width=1080,
        height=1350,  # 4:5 already
        aspect_ratio=1080 / 1350,
        brightness=140,
        contrast=55,
        saturation=90,
        color_temperature=6000,
        sharpness=200,
        highlight_clipping_pct=0.0,
        shadow_clipping_pct=0.0,
        dominant_colors=[],
        faces=[],
        subject_offset_x=0.0,
        subject_offset_y=0.0,
        negative_space_ratio=0.3,
    )
    defaults.update(overrides)
    return ImageMetrics(**defaults)


def test_no_recommendations_for_clean_well_exposed_image():
    metrics = _base_metrics()
    drafts, adjustments = generate_recommendations(metrics)
    rule_ids = {d.rule_id for d in drafts}
    assert "crop.target_aspect_ratio" not in rule_ids
    assert "exposure.highlight_clipping" not in rule_ids
    assert "exposure.shadow_clipping" not in rule_ids


def test_recommends_crop_for_square_image():
    metrics = _base_metrics(width=1080, height=1080, aspect_ratio=1.0)
    drafts, adjustments = generate_recommendations(metrics)
    rule_ids = {d.rule_id for d in drafts}
    assert "crop.target_aspect_ratio" in rule_ids
    assert adjustments.crop_box is not None
    assert adjustments.target_aspect_ratio == "4:5"


def test_warns_on_highlight_clipping():
    metrics = _base_metrics(highlight_clipping_pct=8.0)
    drafts, adjustments = generate_recommendations(metrics)
    warning = next(d for d in drafts if d.rule_id == "exposure.highlight_clipping")
    assert warning.severity == "warning"
    assert adjustments.highlight_recovery > 0


def test_warns_on_shadow_clipping():
    metrics = _base_metrics(shadow_clipping_pct=8.0)
    drafts, adjustments = generate_recommendations(metrics)
    warning = next(d for d in drafts if d.rule_id == "exposure.shadow_clipping")
    assert warning.severity == "warning"
    assert adjustments.shadow_recovery > 0


def test_warns_on_dark_image_vs_history():
    metrics = _base_metrics(brightness=60)
    drafts, adjustments = generate_recommendations(metrics, {"avg_brightness": 150})
    warning = next(d for d in drafts if d.rule_id == "exposure.dark_vs_history")
    assert warning.severity == "warning"
    assert adjustments.exposure > 0


def test_recommends_sharpening_for_soft_image():
    metrics = _base_metrics(sharpness=20)
    drafts, adjustments = generate_recommendations(metrics)
    rule_ids = {d.rule_id for d in drafts}
    assert "sharpness.low_sharpness" in rule_ids
    assert adjustments.sharpen_amount > 0


def test_flags_off_center_subject():
    metrics = _base_metrics(subject_offset_x=0.6)
    drafts, _ = generate_recommendations(metrics)
    rule_ids = {d.rule_id for d in drafts}
    assert "subject.off_center_x" in rule_ids


# --- Scoring ---


def test_image_readiness_perfect_for_clean_image():
    metrics = _base_metrics()
    section = score_image_readiness(metrics)
    assert section.score >= 85


def test_image_readiness_penalizes_clipping():
    clean = score_image_readiness(_base_metrics())
    clipped = score_image_readiness(_base_metrics(highlight_clipping_pct=10.0, shadow_clipping_pct=10.0))
    assert clipped.score < clean.score


def test_timing_opportunity_insufficient_data():
    """With no history AND no follower geography, there is nothing to say."""
    section = score_timing_opportunity(12, 2, [], [], total_posts=2)
    assert section.score == 50
    assert "Not enough" in section.explanation


def test_historical_similarity_insufficient_data():
    """
    Too little history to compare against the account's own posts, so the
    score falls back to the crop -- which is measured from the image and
    needs no history. It must say so rather than implying otherwise.
    """
    section = score_historical_similarity(_base_metrics(), [], total_posts=1)
    assert "not enough to compare" in section.explanation
    assert "Import at least" in section.explanation
    # Crop still discriminates: a far-off ratio scores below a feed-shaped one.
    wide = score_historical_similarity(
        _base_metrics(aspect_ratio=2.4), [], total_posts=1
    )
    assert wide.score < section.score


def test_overall_readiness_is_weighted_average():
    from app.services.recommendations.scoring import ScoreSection

    readiness = ScoreSection(score=80, label="Good", explanation="")
    timing = ScoreSection(score=60, label="Fair", explanation="")
    similarity = ScoreSection(score=40, label="Fair", explanation="")
    overall = score_overall_readiness(readiness, timing, similarity)
    expected = round(80 * 0.45 + 60 * 0.25 + 40 * 0.30)
    assert overall.score == expected


def test_scores_never_claim_specific_engagement_numbers():
    metrics = _base_metrics()
    section = score_historical_similarity(metrics, [], total_posts=1)
    assert "likes" not in section.explanation.lower()
    assert "followers" not in section.explanation.lower()
