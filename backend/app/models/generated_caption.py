import uuid

from sqlalchemy import ForeignKey, Text, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class GeneratedCaption(UUIDPKMixin, TimestampMixin, Base):
    """An AI-generated caption suggestion for an uploaded image."""

    __tablename__ = "generated_captions"

    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_images.id", ondelete="CASCADE")
    )
    model_name: Mapped[str] = mapped_column(String(100))
    caption_text: Mapped[str] = mapped_column(Text)
    # Short label for the angle taken, e.g. "process note" -- lets the UI
    # differentiate options at a glance.
    approach: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Set when the user copies/uses a suggestion. Currently write-only:
    # nothing reads it yet, but it is the signal a future ranking model
    # would train on.
    accepted: Mapped[bool | None] = mapped_column(nullable=True)
