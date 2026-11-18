"""Phase 2: scenarios, sessions, turns, LLM usage, built-in scenarios

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CEFR_CHECK = "cefr_level IN ('A1','A2','B1','B2','C1','C2')"

# Built-in scenarios work in any target language (target_language is NULL).
BUILT_IN_SCENARIOS = [
    {
        "title": "Ordering at a café",
        "description": "You walk into a busy neighbourhood café and want a drink and a snack.",
        "partner_persona": "A friendly, chatty barista who recommends the pastry of the day.",
        "goal": "Order a drink and something to eat, ask the price, and pay.",
        "cefr_level": "A1",
    },
    {
        "title": "Asking for directions",
        "description": "You're lost in a new city and stop someone on the street.",
        "partner_persona": "A helpful local who walks this street every day and knows the area.",
        "goal": "Find out how to get to the train station and how long it takes.",
        "cefr_level": "A1",
    },
    {
        "title": "Checking into a hotel",
        "description": "You arrive at a small hotel in the evening with a reservation.",
        "partner_persona": "A polite receptionist who needs your details and explains the hotel.",
        "goal": "Check in, ask what time breakfast is, and ask for the Wi-Fi password.",
        "cefr_level": "A2",
    },
    {
        "title": "Shopping for clothes",
        "description": "You're in a clothes shop looking for a jacket for a trip.",
        "partner_persona": "An enthusiastic shop assistant who likes to suggest options.",
        "goal": "Describe what you want, ask for another size, and decide whether to buy it.",
        "cefr_level": "A2",
    },
    {
        "title": "At the doctor's",
        "description": "You've felt unwell for a few days and have an appointment.",
        "partner_persona": "A calm, patient family doctor who asks careful questions.",
        "goal": "Explain your symptoms, answer the doctor's questions, and understand the advice.",
        "cefr_level": "B1",
    },
    {
        "title": "Viewing an apartment",
        "description": "You're visiting an apartment you might rent.",
        "partner_persona": "A busy landlord who wants to find a reliable tenant quickly.",
        "goal": "Ask about rent, bills, and the neighbourhood, then arrange next steps.",
        "cefr_level": "B1",
    },
    {
        "title": "Job interview",
        "description": "You're interviewing for a job you really want at a mid-sized company.",
        "partner_persona": "A professional but friendly hiring manager.",
        "goal": "Describe your experience, answer questions about strengths, and ask "
        "about the role.",
        "cefr_level": "B2",
    },
    {
        "title": "Returning a faulty product",
        "description": "The headphones you bought last week stopped working.",
        "partner_persona": "A customer service agent who must follow the store's return policy.",
        "goal": "Explain the problem and negotiate a refund or replacement.",
        "cefr_level": "B2",
    },
    {
        "title": "Debating city plans",
        "description": "At a community meeting, residents discuss a plan to close a road to cars.",
        "partner_persona": "A sharp, opinionated neighbour who strongly supports the plan.",
        "goal": "Give your opinion, respond to their arguments, and reach a compromise.",
        "cefr_level": "C1",
    },
]


def upgrade() -> None:
    scenarios = op.create_table(
        "scenarios",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("partner_persona", sa.Text(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("target_language", sa.String(8), nullable=True),
        sa.Column("cefr_level", sa.String(2), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scenarios"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_scenarios_created_by_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint(CEFR_CHECK, name="ck_scenarios_cefr_level_valid"),
        sa.CheckConstraint(
            "is_custom = (created_by IS NOT NULL)", name="ck_scenarios_custom_has_owner"
        ),
    )
    op.create_index("ix_scenarios_created_by", "scenarios", ["created_by"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("learner_profile_id", sa.BigInteger(), nullable=False),
        sa.Column("scenario_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_rate", sa.Numeric(5, 4), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.ForeignKeyConstraint(
            ["learner_profile_id"],
            ["learner_profiles.id"],
            name="fk_sessions_learner_profile_id_learner_profiles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
            name="fk_sessions_scenario_id_scenarios",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_sessions_learner_profile_id", "sessions", ["learner_profile_id"])
    op.create_index("ix_sessions_scenario_id", "sessions", ["scenario_id"])

    op.create_table(
        "turns",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_turns"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name="fk_turns_session_id_sessions", ondelete="CASCADE"
        ),
        sa.CheckConstraint("role IN ('learner','partner')", name="ck_turns_role_valid"),
    )
    op.create_index("ix_turns_session_id_created_at", "turns", ["session_id", "created_at"])

    op.create_table(
        "llm_usage",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(255), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=False),
        sa.Column("completion_tokens", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_llm_usage"),
        sa.UniqueConstraint("day", "provider", "model", name="uq_llm_usage_day_provider_model"),
    )

    op.bulk_insert(
        scenarios,
        [
            {**s, "target_language": None, "is_custom": False, "created_by": None}
            for s in BUILT_IN_SCENARIOS
        ],
    )


def downgrade() -> None:
    op.drop_table("llm_usage")
    op.drop_index("ix_turns_session_id_created_at", table_name="turns")
    op.drop_table("turns")
    op.drop_index("ix_sessions_scenario_id", table_name="sessions")
    op.drop_index("ix_sessions_learner_profile_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_scenarios_created_by", table_name="scenarios")
    op.drop_table("scenarios")
