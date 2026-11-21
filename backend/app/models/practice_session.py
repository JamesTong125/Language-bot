from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_column

if TYPE_CHECKING:
    from app.models.learner_profile import LearnerProfile
    from app.models.scenario import Scenario
    from app.models.turn import Turn


class PracticeSession(Base):
    """One conversation in a scenario. Named to avoid clashing with SQLAlchemy's Session."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("cefr_level IN ('A1','A2','B1','B2','C1','C2')", name="cefr_level_valid"),
    )

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
    # The learner's level when the session started. Level suggestions compare sessions at
    # the same level, and the partner keeps that level even if the profile changes mid-session.
    cefr_level: Mapped[str] = mapped_column(String(2), nullable=False)
    # Private sessions send every LLM call to the private provider only.
    is_private: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    learner_profile: Mapped[LearnerProfile] = relationship()
    scenario: Mapped[Scenario] = relationship()
    turns: Mapped[list[Turn]] = relationship(
        back_populates="session",
        order_by="(Turn.created_at, Turn.id)",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
