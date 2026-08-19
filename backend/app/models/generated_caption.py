import uuid

from sqlalchemy import ForeignKey, Text, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class GeneratedCaption(UUIDPKMixin, TimestampMixin, Base):
    """Placeholder for future AI-generated caption suggestions. Not used in v0.1."""

    __tablename__ = "generated_captions"

    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_images.id", ondelete="CASCADE")
    )
    model_name: Mapped[str] = mapped_column(String(100))
    caption_text: Mapped[str] = mapped_column(Text)
    accepted: Mapped[bool | None] = mapped_column(nullable=True)
