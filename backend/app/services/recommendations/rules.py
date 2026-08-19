"""
Rule-based recommendation engine.

Every recommendation here is produced by an explicit, named rule that
compares a measured image property (or historical statistic) against a
fixed threshold. There is no learned model and no prediction of
engagement outcomes -- see services/recommendations/scoring.py for the
companion heuristic scoring system and its required disclaimers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.image_analysis.metrics import ImageMetrics
from app.services.image_processing.optimizer import Adjustments

TARGET_ASPECT_RATIO = 4 / 5  # Instagram's tallest standard feed ratio (portrait)
TARGET_ASPECT_LABEL = "4:5"


@dataclass
class RecommendationDraft:
    category: str
    severity: str  # info | suggestion | warning
    title: str
    detail: str
    rule_id: str
    metadata: dict = field(default_factory=dict)


def _crop_box_for_target_ratio(
    width: int, height: int, target_ratio: float, offset_x: float | None, offset_y: float | None
) -> tuple[int, int, int, int]:
    """
    Compute a crop box that achieves target_ratio (w/h) while keeping the
    detected subject center inside frame as much as possible.
    """
    current_ratio = width / height
    if current_ratio > target_ratio:
        # Too wide -- crop width.
        new_width = int(round(height * target_ratio))
        new_height = height
        max_shift = width - new_width
        center_bias = (offset_x or 0.0) * 0.5 + 0.5  # 0..1
        x0 = int(max(0, min(max_shift, max_shift * center_bias)))
        y0 = 0
    else:
        # Too tall -- crop height.
        new_width = width
        new_height = int(round(width / target_ratio))
        max_shift = height - new_height
        center_bias = (offset_y or 0.0) * 0.5 + 0.5
        y0 = int(max(0, min(max_shift, max_shift * center_bias)))
        x0 = 0

    return x0, y0, x0 + new_width, y0 + new_height


def generate_recommendations(
    metrics: ImageMetrics,
    historical_context: dict | None = None,
) -> tuple[list[RecommendationDraft], Adjustments]:
    """
    Returns (recommendation_drafts, suggested_adjustments). historical_context
    is optional and, when present, should contain:
      {"avg_brightness": float | None, "avg_contrast": float | None,
       "has_enough_data": bool}
    """
    historical_context = historical_context or {}
    drafts: list[RecommendationDraft] = []
    adjustments = Adjustments()

    # --- Crop / aspect ratio ---
    ratio_delta = abs(metrics.aspect_ratio - TARGET_ASPECT_RATIO)
    if ratio_delta > 0.06:
        crop_box = _crop_box_for_target_ratio(
            metrics.width, metrics.height, TARGET_ASPECT_RATIO,
            metrics.subject_offset_x, metrics.subject_offset_y,
        )
        adjustments.crop_box = crop_box
        adjustments.target_aspect_ratio = TARGET_ASPECT_LABEL
        drafts.append(
            RecommendationDraft(
                category="crop",
                severity="suggestion",
                title=f"Consider a {TARGET_ASPECT_LABEL} crop",
                detail=(
                    f"This image is {metrics.aspect_ratio:.2f}:1. Cropping to {TARGET_ASPECT_LABEL} "
                    "uses more vertical space in the Instagram feed, which tends to make the post "
                    "more prominent while scrolling."
                ),
                rule_id="crop.target_aspect_ratio",
                metadata={"current_ratio": metrics.aspect_ratio, "target_ratio": TARGET_ASPECT_RATIO},
            )
        )

    # --- Highlight clipping ---
    if metrics.highlight_clipping_pct > 2.0:
        adjustments.highlight_recovery = min(0.6, metrics.highlight_clipping_pct / 20)
        severity = "warning" if metrics.highlight_clipping_pct > 6.0 else "suggestion"
        drafts.append(
            RecommendationDraft(
                category="exposure",
                severity=severity,
                title="Highlights appear clipped",
                detail=(
                    f"About {metrics.highlight_clipping_pct:.1f}% of pixels are at or near pure white. "
                    "Detail may be lost in the brightest areas. A mild highlight recovery is suggested."
                ),
                rule_id="exposure.highlight_clipping",
                metadata={"highlight_clipping_pct": metrics.highlight_clipping_pct},
            )
        )

    # --- Shadow clipping ---
    if metrics.shadow_clipping_pct > 2.0:
        adjustments.shadow_recovery = min(0.6, metrics.shadow_clipping_pct / 20)
        severity = "warning" if metrics.shadow_clipping_pct > 6.0 else "suggestion"
        drafts.append(
            RecommendationDraft(
                category="exposure",
                severity=severity,
                title="Shadows appear clipped",
                detail=(
                    f"About {metrics.shadow_clipping_pct:.1f}% of pixels are at or near pure black. "
                    "Detail may be lost in the darkest areas. A mild shadow recovery is suggested."
                ),
                rule_id="exposure.shadow_clipping",
                metadata={"shadow_clipping_pct": metrics.shadow_clipping_pct},
            )
        )

    # --- Brightness vs this account's historically stronger posts ---
    avg_brightness = historical_context.get("avg_brightness")
    if avg_brightness and metrics.brightness < avg_brightness * 0.75:
        exposure_boost = min(0.3, (avg_brightness - metrics.brightness) / 255)
        adjustments.exposure = max(adjustments.exposure, exposure_boost)
        drafts.append(
            RecommendationDraft(
                category="exposure",
                severity="warning",
                title="Image is darker than your historically stronger posts",
                detail=(
                    f"This image's average brightness ({metrics.brightness:.0f}/255) is noticeably lower "
                    f"than the average for your historically stronger posts ({avg_brightness:.0f}/255). "
                    "A modest exposure lift is suggested if this isn't an intentional low-key shot."
                ),
                rule_id="exposure.dark_vs_history",
                metadata={"brightness": metrics.brightness, "historical_avg_brightness": avg_brightness},
            )
        )
    elif metrics.brightness < 60:
        drafts.append(
            RecommendationDraft(
                category="exposure",
                severity="suggestion",
                title="Image is quite dark overall",
                detail=(
                    f"Average brightness is {metrics.brightness:.0f}/255. If this isn't an intentional "
                    "low-key/dark composition, a mild exposure increase may help it read well on mobile screens."
                ),
                rule_id="exposure.low_brightness",
                metadata={"brightness": metrics.brightness},
            )
        )

    # --- Contrast ---
    if metrics.contrast < 30:
        adjustments.contrast = max(adjustments.contrast, 0.15)
        drafts.append(
            RecommendationDraft(
                category="contrast",
                severity="suggestion",
                title="Image reads a little flat",
                detail=(
                    f"Contrast (tonal spread) is {metrics.contrast:.0f}, which is low. A modest contrast "
                    "increase can add depth without altering the composition."
                ),
                rule_id="contrast.low_contrast",
                metadata={"contrast": metrics.contrast},
            )
        )

    # --- Sharpness ---
    if metrics.sharpness < 60:
        adjustments.sharpen_amount = 0.25
        drafts.append(
            RecommendationDraft(
                category="sharpness",
                severity="suggestion",
                title="Image may benefit from mild sharpening",
                detail=(
                    "The measured sharpness is on the lower side for this resolution. A light sharpening "
                    "pass can help fine detail hold up in feed thumbnails without changing the image content."
                ),
                rule_id="sharpness.low_sharpness",
                metadata={"sharpness": metrics.sharpness},
            )
        )

    # --- Subject placement / negative space ---
    if metrics.subject_offset_x is not None and abs(metrics.subject_offset_x) > 0.35:
        drafts.append(
            RecommendationDraft(
                category="subject",
                severity="info",
                title="Subject is positioned off-center",
                detail=(
                    "The visual focal point sits noticeably left or right of center. This can work well "
                    "intentionally; if not, a tighter crop toward the subject may improve balance."
                ),
                rule_id="subject.off_center_x",
                metadata={"subject_offset_x": metrics.subject_offset_x},
            )
        )

    if metrics.negative_space_ratio is not None and metrics.negative_space_ratio > 0.75:
        drafts.append(
            RecommendationDraft(
                category="subject",
                severity="info",
                title="Large area of negative space detected",
                detail=(
                    f"About {metrics.negative_space_ratio * 100:.0f}% of the frame has low visual detail. "
                    "If this is intentional (minimalist composition), no action is needed. Otherwise, a "
                    "tighter crop around the subject may read stronger in-feed."
                ),
                rule_id="subject.high_negative_space",
                metadata={"negative_space_ratio": metrics.negative_space_ratio},
            )
        )

    # --- Faces ---
    if metrics.faces:
        largest = max(metrics.faces, key=lambda f: f.area_ratio)
        if largest.area_ratio < 0.02:
            drafts.append(
                RecommendationDraft(
                    category="subject",
                    severity="info",
                    title="Faces detected but small in frame",
                    detail=(
                        "One or more faces were detected but occupy a small portion of the frame. "
                        "Artwork Integrity mode will never crop tighter than your chosen crop, but a "
                        "tighter manual crop could bring more attention to subjects with faces."
                    ),
                    rule_id="subject.small_face",
                    metadata={"largest_face_area_ratio": largest.area_ratio, "face_count": len(metrics.faces)},
                )
            )

    # --- Timing (derived from the account's own historical performance) ---
    posting_windows = historical_context.get("posting_windows")
    if posting_windows and posting_windows.get("has_enough_data") and posting_windows.get("best_days"):
        best_day = posting_windows["best_days"][0]["day"]
        best_hour_entry = posting_windows["best_hours"][0] if posting_windows.get("best_hours") else None
        hour_txt = f" around {best_hour_entry['hour']:02d}:00" if best_hour_entry else ""
        drafts.append(
            RecommendationDraft(
                category="timing",
                severity="info",
                title=f"This account has historically performed best on {best_day}{hour_txt}",
                detail=(
                    f"Based on this account's own imported history, {best_day}{hour_txt} shows the "
                    "highest average engagement rate. This is a descriptive pattern from past posts, "
                    "not a guarantee of future performance."
                ),
                rule_id="timing.best_window",
                metadata=posting_windows,
            )
        )
    elif posting_windows is not None and not posting_windows.get("has_enough_data"):
        drafts.append(
            RecommendationDraft(
                category="timing",
                severity="info",
                title="Not enough historical data yet",
                detail="Import more historical posts to unlock personalized posting-time recommendations.",
                rule_id="timing.insufficient_data",
                metadata={},
            )
        )

    return drafts, adjustments
