"""Phase 4: vocab items and reviews

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vocab_items",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("learner_profile_id", sa.BigInteger(), nullable=False),
        sa.Column("term", sa.String(120), nullable=False),
        sa.Column("translation", sa.String(200), nullable=False),
        sa.Column("example_sentence", sa.Text(), nullable=True),
        sa.Column("source_correction_id", sa.BigInteger(), nullable=True),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("ease", sa.Float(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vocab_items"),
        sa.ForeignKeyConstraint(
            ["learner_profile_id"],
            ["learner_profiles.id"],
            name="fk_vocab_items_learner_profile_id_learner_profiles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_correction_id"],
            ["corrections.id"],
            name="fk_vocab_items_source_correction_id_corrections",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name="fk_vocab_items_session_id_sessions",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_vocab_items_learner_profile_id_due_at", "vocab_items", ["learner_profile_id", "due_at"]
    )
    op.create_index("ix_vocab_items_session_id", "vocab_items", ["session_id"])
    op.create_index(
        "uq_vocab_items_learner_profile_id_lower_term",
        "vocab_items",
        ["learner_profile_id", sa.text("lower(term)")],
        unique=True,
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("vocab_item_id", sa.BigInteger(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column(
            "reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reviews"),
        sa.ForeignKeyConstraint(
            ["vocab_item_id"],
            ["vocab_items.id"],
            name="fk_reviews_vocab_item_id_vocab_items",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("rating BETWEEN 0 AND 5", name="ck_reviews_rating_valid"),
    )
    op.create_index("ix_reviews_vocab_item_id", "reviews", ["vocab_item_id"])


def downgrade() -> None:
    op.drop_index("ix_reviews_vocab_item_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("uq_vocab_items_learner_profile_id_lower_term", table_name="vocab_items")
    op.drop_index("ix_vocab_items_session_id", table_name="vocab_items")
    op.drop_index("ix_vocab_items_learner_profile_id_due_at", table_name="vocab_items")
    op.drop_table("vocab_items")
