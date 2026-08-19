import uuid

from sqlalchemy import ForeignKey, String, Integer, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class UploadedImage(UUIDPKMixin, TimestampMixin, Base):
    """A new image uploaded by the user for optimization (not yet posted)."""

    __tablename__ = "uploaded_images"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )

    # Safe, randomly generated storage key -- never the user-supplied
    # filename -- used as the on-disk/object-storage identifier.
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="uploaded_images")
    analyses: Mapped[list["ImageAnalysis"]] = relationship(
        back_populates="image", cascade="all, delete-orphan"
    )
    variants: Mapped[list["ImageVariant"]] = relationship(
        back_populates="image", cascade="all, delete-orphan"
    )
