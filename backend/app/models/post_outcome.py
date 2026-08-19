import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class PostOutcome(UUIDPKMixin, TimestampMixin, Base):
    """
    Placeholder linking a Recommendation/ImageAnalysis to the actual
    real-world performance of the resulting post, once published and
    re-imported. Not populated in v0.1; this is the join point a future
    ML model would use as training data (predicted vs. actual).
    """

    __tablename__ = "post_outcomes"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("image_analyses.id", ondelete="CASCADE")
    )
    resulting_post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_posts.id"), nullable=True
    )
    notes: Mapped[dict] = mapped_column(JSONB, default=dict)
