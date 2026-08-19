from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Global default for newly generated image variants. Individual
    # generation requests may still override this per-request.
    artwork_integrity_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    instagram_accounts: Mapped[list["InstagramAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    uploaded_images: Mapped[list["UploadedImage"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
