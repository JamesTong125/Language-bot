from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.turn import Turn

ERROR_TYPES = ("grammar", "vocabulary", "spelling", "word_order", "conjugation", "register")


class Correction(Base):
    """One mistake found in a learner turn by the background error analysis."""

    __tablename__ = "corrections"
    __table_args__ = (
        CheckConstraint(
            "error_type IN (" + ",".join(f"'{t}'" for t in ERROR_TYPES) + ")",
            name="error_type_valid",
        ),
        CheckConstraint("severity BETWEEN 1 AND 3", name="severity_valid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    turn_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original: Mapped[str] = mapped_column(Text, nullable=False)
    corrected: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    turn: Mapped[Turn] = relationship(back_populates="corrections")
