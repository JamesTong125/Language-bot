from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column


class Scenario(Base):
    """A role-play setup. Built-in scenarios have no target language: they work in any."""

    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint("cefr_level IN ('A1','A2','B1','B2','C1','C2')", name="cefr_level_valid"),
        CheckConstraint("is_custom = (created_by IS NOT NULL)", name="custom_has_owner"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    partner_persona: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    target_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cefr_level: Mapped[str] = mapped_column(String(2), nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = created_at_column()
