"""Phase 1: users and learner profiles

Revision ID: 0001
Revises:
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("native_language", sa.String(8), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "learner_profiles",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("target_language", sa.String(8), nullable=False),
        sa.Column("cefr_level", sa.String(2), nullable=False),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_learner_profiles"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_learner_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id", "target_language", name="uq_learner_profiles_user_id_target_language"
        ),
        sa.CheckConstraint(
            "cefr_level IN ('A1','A2','B1','B2','C1','C2')",
            name="ck_learner_profiles_cefr_level_valid",
        ),
    )
    op.create_index("ix_learner_profiles_user_id", "learner_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_learner_profiles_user_id", table_name="learner_profiles")
    op.drop_table("learner_profiles")
    op.drop_table("users")
