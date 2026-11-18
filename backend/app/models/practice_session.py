from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_column

if TYPE_CHECKING:
    from app.models.learner_profile import LearnerProfile
    from app.models.scenario import Scenario
    from app.models.turn import Turn


class PracticeSession(Base):
    """One conversation in a scenario. Named to avoid clashing with SQLAlchemy's Session."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    learner_profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = created_at_column()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    learner_profile: Mapped[LearnerProfile] = relationship()
    scenario: Mapped[Scenario] = relationship()
    turns: Mapped[list[Turn]] = relationship(
        back_populates="session",
        order_by="(Turn.created_at, Turn.id)",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
