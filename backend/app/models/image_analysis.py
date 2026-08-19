import uuid

from sqlalchemy import ForeignKey, Float, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class ImageAnalysis(UUIDPKMixin, TimestampMixin, Base):
    """
    Measurable visual properties extracted from an uploaded image, plus the
    heuristic scores derived from them. This is deliberately NOT a
    prediction of engagement -- see Recommendation / scoring docs.
    """

    __tablename__ = "image_analyses"

    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_images.id", ondelete="CASCADE")
    )

    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    aspect_ratio: Mapped[float] = mapped_column(Float)

    brightness: Mapped[float] = mapped_column(Float)
    contrast: Mapped[float] = mapped_column(Float)
    saturation: Mapped[float] = mapped_column(Float)
    color_temperature: Mapped[float] = mapped_column(Float)  # approximate, kelvin-ish
    sharpness: Mapped[float] = mapped_column(Float)

    highlight_clipping_pct: Mapped[float] = mapped_column(Float)
    shadow_clipping_pct: Mapped[float] = mapped_column(Float)

    face_count: Mapped[int] = mapped_column(Integer, default=0)
    largest_face_area_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    subject_offset_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    subject_offset_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    negative_space_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Structured, less-frequently-queried data (dominant color palette,
    # raw histogram summaries, etc.) kept as JSON rather than many columns.
    dominant_colors: Mapped[list] = mapped_column(JSONB, default=list)
    raw_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Heuristic scores (0-100), explicitly not predictive. See
    # services/recommendations/scoring.py for the full explanation text.
    image_readiness_score: Mapped[int] = mapped_column(Integer)
    historical_similarity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    image: Mapped["UploadedImage"] = relationship(back_populates="analyses")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
