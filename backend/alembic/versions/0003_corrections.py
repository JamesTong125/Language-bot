"""Phase 3: corrections

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "corrections",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("turn_id", sa.BigInteger(), nullable=False),
        sa.Column("original", sa.Text(), nullable=False),
        sa.Column("corrected", sa.Text(), nullable=False),
        sa.Column("error_type", sa.String(20), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_corrections"),
        sa.ForeignKeyConstraint(
            ["turn_id"], ["turns.id"], name="fk_corrections_turn_id_turns", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "error_type IN ('grammar','vocabulary','spelling','word_order','conjugation',"
            "'register')",
            name="ck_corrections_error_type_valid",
        ),
        sa.CheckConstraint("severity BETWEEN 1 AND 3", name="ck_corrections_severity_valid"),
    )
    op.create_index("ix_corrections_turn_id", "corrections", ["turn_id"])


def downgrade() -> None:
    op.drop_index("ix_corrections_turn_id", table_name="corrections")
    op.drop_table("corrections")
