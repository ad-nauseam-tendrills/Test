import uuid

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class InstagramPostMetric(UUIDPKMixin, TimestampMixin, Base):
    """
    Engagement metrics for a single historical post.

    Kept as a separate table (1:1 with InstagramPost) so metrics can be
    re-synced / re-fetched independently of the immutable post content,
    and so future snapshot-over-time tracking (e.g. metrics-at-24h vs
    metrics-at-7d) could be added as additional rows without touching
    InstagramPost itself.
    """

    __tablename__ = "instagram_post_metrics"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instagram_posts.id", ondelete="CASCADE"),
        unique=True,
    )

    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Meta deprecated `impressions` for media created after 2024-07-02 and
    # replaced it with `views`. Both columns exist so older imports keep
    # their impressions figure while newer media populates views; the
    # analytics layer accepts either as an engagement denominator.
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_visits: Mapped[int | None] = mapped_column(Integer, nullable=True)

    post: Mapped["InstagramPost"] = relationship(back_populates="metrics")
