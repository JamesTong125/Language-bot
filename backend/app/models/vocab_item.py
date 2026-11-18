from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column


class VocabItem(Base):
    """A word or phrase to study, with its spaced-repetition state."""

    __tablename__ = "vocab_items"
    __table_args__ = (
        Index("ix_vocab_items_learner_profile_id_due_at", "learner_profile_id", "due_at"),
        # Safety net for deduplication; the service also normalises terms before inserting.
        Index(
            "uq_vocab_items_learner_profile_id_lower_term",
            "learner_profile_id",
            func.lower(text("term")),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    learner_profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learner_profiles.id", ondelete="CASCADE"), nullable=False
    )
    term: Mapped[str] = mapped_column(String(120), nullable=False)
    translation: Mapped[str] = mapped_column(String(200), nullable=False)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_correction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("corrections.id", ondelete="SET NULL"), nullable=True
    )
    # The session whose wrap-up created the item, so the summary page can list its words.
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ease: Mapped[float] = mapped_column(Float, nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
