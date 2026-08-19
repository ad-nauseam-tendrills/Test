import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class InstagramPost(UUIDPKMixin, TimestampMixin, Base):
    """A historical (already-published) Instagram post imported from a provider."""

    __tablename__ = "instagram_posts"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_accounts.id", ondelete="CASCADE")
    )

    ig_media_id: Mapped[str] = mapped_column(String(64), index=True)
    media_type: Mapped[str] = mapped_column(String(20))  # IMAGE, VIDEO, CAROUSEL_ALBUM
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    permalink: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Follower count at the time of posting (used to normalize engagement
    # across periods of audience growth). May be null for older imports
    # where the provider cannot supply a historical value.
    follower_count_at_posting: Mapped[int | None] = mapped_column(Integer, nullable=True)

    account: Mapped["InstagramAccount"] = relationship(back_populates="posts")
    metrics: Mapped["InstagramPostMetric"] = relationship(
        back_populates="post", uselist=False, cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="source_post"
    )

    __table_args__ = ()
