import uuid

from sqlalchemy import ForeignKey, String, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class ImageVariant(UUIDPKMixin, TimestampMixin, Base):
    """An optimized/generated version of an UploadedImage."""

    __tablename__ = "image_variants"

    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_images.id", ondelete="CASCADE")
    )

    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)

    artwork_integrity_mode: Mapped[bool] = mapped_column(Boolean, default=True)

    # Exact adjustment values applied, e.g.
    # {"exposure": 0.12, "contrast": 0.05, "white_balance_shift_k": -150,
    #  "highlight_recovery": 0.3, "shadow_recovery": 0.15,
    #  "saturation": 0.05, "sharpen_amount": 0.2,
    #  "crop_box": [0, 40, 1080, 1350], "target_aspect_ratio": "4:5"}
    adjustments: Mapped[dict] = mapped_column(JSONB, default=dict)

    image: Mapped["UploadedImage"] = relationship(back_populates="variants")
