import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class InstagramAccount(UUIDPKMixin, TimestampMixin, Base):
    """
    A connected Instagram professional account.

    Auth/token material lives in separate, clearly-named columns
    (access_token, token_expires_at) so it can be isolated, encrypted at
    rest, or moved to a secrets store independently of ordinary account
    metadata (username, follower_count, etc.) without a schema redesign.
    """

    __tablename__ = "instagram_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )

    provider: Mapped[str] = mapped_column(String(20), default="mock")
    # Instagram-side identifiers / profile data (ordinary, non-secret).
    ig_user_id: Mapped[str] = mapped_column(String(64))
    username: Mapped[str] = mapped_column(String(255))
    account_type: Mapped[str] = mapped_column(String(32), default="BUSINESS")
    profile_picture_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Auth/token material (sensitive). Kept in dedicated columns so
    # this data can be treated differently (encryption, redaction from
    # logs/exports) from the profile fields above. ---
    access_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="instagram_accounts")
    posts: Mapped[list["InstagramPost"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
