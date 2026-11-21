"""Custom scenarios: the LLM expands a learner's short description into a full scene."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.prompt_builder import language_name
from app.llm.base import LLMClient, Message
from app.models import LearnerProfile, Scenario, User
from app.prompts import render_prompt
from app.schemas.custom_scenario import ScenarioDraft

logger = logging.getLogger(__name__)

SCENARIO_PROMPT = "scenario_v1"


class ScenarioRefusedError(Exception):
    pass


def build_scenario_messages(
    description: str, target_language: str, native_language: str, level: str
) -> list[Message]:
    system = render_prompt(
        SCENARIO_PROMPT,
        target_language=language_name(target_language),
        native_language=language_name(native_language),
        level=level,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"DESCRIPTION: {description}"},
    ]


async def create_custom_scenario(
    db: AsyncSession,
    user: User,
    profile: LearnerProfile,
    description: str,
    llm: LLMClient,
) -> Scenario:
    """Ask the model for a scene and save it for this learner's current language and level.

    Raises ScenarioRefusedError if the model refuses, and LLMError if the call fails.
    Nothing is saved in either case.
    """
    assert user.native_language
    draft = await llm.complete_json(
        build_scenario_messages(
            description, profile.target_language, user.native_language, profile.cefr_level
        ),
        ScenarioDraft,
        usage_tag=f"user:{user.id}:scenario",
    )
    if draft.refused:
        logger.info("Custom scenario refused for user %d", user.id)
        raise ScenarioRefusedError
    assert draft.title and draft.description and draft.partner_persona and draft.goal
    scenario = Scenario(
        title=draft.title,
        description=draft.description,
        partner_persona=draft.partner_persona,
        goal=draft.goal,
        target_language=profile.target_language,
        cefr_level=profile.cefr_level,
        is_custom=True,
        created_by=user.id,
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    logger.info("Created custom scenario %d for user %d", scenario.id, user.id)
    return scenario
