import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Experiment(UUIDPKMixin, TimestampMixin, Base):
    """Placeholder for future A/B testing between image/caption variants. Not used in v0.1."""

    __tablename__ = "experiments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="draft")

    variants: Mapped[list["ExperimentVariant"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentVariant(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "experiment_variants"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE")
    )
    image_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("image_variants.id"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(50))  # e.g. "A", "B"
    result: Mapped[dict] = mapped_column(JSONB, default=dict)

    experiment: Mapped["Experiment"] = relationship(back_populates="variants")
