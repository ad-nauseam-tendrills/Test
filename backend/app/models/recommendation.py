import uuid

from sqlalchemy import ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Recommendation(UUIDPKMixin, TimestampMixin, Base):
    """
    A single rule-based recommendation produced for an image analysis
    (e.g. "crop to 4:5", "highlights are clipped"). Kept as discrete rows
    (rather than embedded JSON) so recommendations can be individually
    tracked, dismissed, or -- later -- fed back into a training set for
    an eventual ML ranking model.
    """

    __tablename__ = "recommendations"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("image_analyses.id", ondelete="CASCADE")
    )
    # Optional link to a historical post, when a recommendation is derived
    # from timing/performance analysis rather than the image itself.
    source_post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_posts.id"), nullable=True
    )

    category: Mapped[str] = mapped_column(String(50))  # crop, exposure, timing, subject, ...
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info, suggestion, warning
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text)
    # Rule identifier + inputs that triggered it, for transparency/debugging.
    rule_id: Mapped[str] = mapped_column(String(100))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    analysis: Mapped["ImageAnalysis"] = relationship(back_populates="recommendations")
    source_post: Mapped["InstagramPost"] = relationship(back_populates="recommendations")
