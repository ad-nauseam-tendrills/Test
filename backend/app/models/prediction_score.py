import uuid

from sqlalchemy import ForeignKey, String, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class PredictionScore(UUIDPKMixin, TimestampMixin, Base):
    """
    Placeholder for future ML-model output.

    Not used in v0.1 -- all current scoring is heuristic and lives on
    ImageAnalysis / Recommendation. This table exists so a future
    prediction model can attach versioned scores to an analysis without
    another migration touching existing heuristic-score columns.
    """

    __tablename__ = "prediction_scores"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("image_analyses.id", ondelete="CASCADE")
    )
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(50))
    predicted_metric: Mapped[str] = mapped_column(String(50))  # e.g. "engagement_rate_percentile"
    predicted_value: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
