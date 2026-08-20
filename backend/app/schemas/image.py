import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadedImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    file_size_bytes: int
    width: int
    height: int
    created_at: datetime
    url: str | None = None


class DominantColor(BaseModel):
    hex: str
    ratio: float


class ImageAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    image_id: uuid.UUID
    width: int
    height: int
    aspect_ratio: float
    brightness: float
    contrast: float
    saturation: float
    color_temperature: float
    sharpness: float
    highlight_clipping_pct: float
    shadow_clipping_pct: float
    face_count: int
    largest_face_area_ratio: float | None
    subject_offset_x: float | None
    subject_offset_y: float | None
    negative_space_ratio: float | None
    dominant_colors: list[DominantColor]
    image_readiness_score: int
    historical_similarity_score: int | None


class ScoreBreakdown(BaseModel):
    score: int
    label: str
    explanation: str


class ScoreReport(BaseModel):
    image_readiness: ScoreBreakdown
    timing_opportunity: ScoreBreakdown
    historical_similarity: ScoreBreakdown
    overall_readiness: ScoreBreakdown


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    severity: str
    title: str
    detail: str
    rule_id: str


class AnalyzeImageResponse(BaseModel):
    analysis: ImageAnalysisRead
    scores: ScoreReport
    recommendations: list[RecommendationRead]


class AdjustmentValues(BaseModel):
    exposure: float = 0.0
    contrast: float = 0.0
    white_balance_shift: float = 0.0
    highlight_recovery: float = 0.0
    shadow_recovery: float = 0.0
    saturation: float = 0.0
    sharpen_amount: float = 0.0
    crop_box: list[int] | None = None
    target_aspect_ratio: str | None = None


class ImageVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    image_id: uuid.UUID
    width: int
    height: int
    artwork_integrity_mode: bool
    adjustments: dict
    created_at: datetime
    url: str | None = None


class GenerateVariantRequest(BaseModel):
    artwork_integrity_mode: bool = True
    # Allow the user to accept/override individual recommended adjustments.
    overrides: AdjustmentValues | None = None


class CaptionOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    caption_text: str
    approach: str | None = None


class GenerateCaptionsResponse(BaseModel):
    captions: list[CaptionOptionRead]
    # Shown with the suggestions so they read as a creative starting
    # point rather than a performance recommendation.
    note: str
