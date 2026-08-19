import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class ScheduledPost(UUIDPKMixin, TimestampMixin, Base):
    """
    Placeholder for future publish-scheduling. Not used in v0.1 -- this
    MVP does not publish to Instagram. Exists so the data model does not
    need to change when scheduling/publishing is implemented.
    """

    __tablename__ = "scheduled_posts"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_accounts.id", ondelete="CASCADE")
    )
    image_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("image_variants.id", ondelete="CASCADE")
    )
    caption: Mapped[str | None] = mapped_column(String(2200), nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, queued, published, failed
