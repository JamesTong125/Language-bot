"""Phase 6: session level and private sessions

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("cefr_level", sa.String(2), nullable=True))
    # Existing sessions get their profile's current level: the best information available.
    op.execute(
        "UPDATE sessions SET cefr_level = learner_profiles.cefr_level "
        "FROM learner_profiles WHERE learner_profiles.id = sessions.learner_profile_id"
    )
    op.alter_column("sessions", "cefr_level", nullable=False)
    op.create_check_constraint(
        "ck_sessions_cefr_level_valid",
        "sessions",
        "cefr_level IN ('A1','A2','B1','B2','C1','C2')",
    )
    op.add_column(
        "sessions",
        sa.Column("is_private", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("sessions", "is_private")
    op.drop_constraint("ck_sessions_cefr_level_valid", "sessions", type_="check")
    op.drop_column("sessions", "cefr_level")
