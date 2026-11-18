from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_column

if TYPE_CHECKING:
    from app.models.correction import Correction
    from app.models.practice_session import PracticeSession

TurnRole = Literal["learner", "partner"]


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (
        CheckConstraint("role IN ('learner','partner')", name="role_valid"),
        Index("ix_turns_session_id_created_at", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_column()

    session: Mapped[PracticeSession] = relationship(back_populates="turns")
    corrections: Mapped[list[Correction]] = relationship(
        back_populates="turn",
        order_by="Correction.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
