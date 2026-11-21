import logging

from fastapi import APIRouter, HTTPException, status

from app.deps import (
    AnalysisLLM,
    AppSettings,
    CurrentProfile,
    CurrentUser,
    DbSession,
    PrivateLLM,
    too_many_requests,
)
from app.llm.base import LLMError
from app.schemas.conversation import ScenarioList, ScenarioOut
from app.schemas.custom_scenario import CreateScenarioRequest
from app.services.custom_scenarios import ScenarioRefusedError, create_custom_scenario
from app.services.rate_limits import RateLimitedError, check_scenarios
from app.services.scenarios import list_scenarios

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("")
async def get_scenarios(
    user: CurrentUser, profile: CurrentProfile, db: DbSession, private_llm: PrivateLLM
) -> ScenarioList:
    scenarios = await list_scenarios(db, user.id, profile.target_language)
    return ScenarioList(
        scenarios=[ScenarioOut.model_validate(s) for s in scenarios],
        private_available=private_llm is not None,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def post_scenario(
    body: CreateScenarioRequest,
    user: CurrentUser,
    profile: CurrentProfile,
    db: DbSession,
    llm: AnalysisLLM,
    settings: AppSettings,
) -> ScenarioOut:
    """Create a custom scenario from a short description, for the current language and level."""
    try:
        await check_scenarios(db, user.id, settings.rate_limit_scenarios_per_day)
    except RateLimitedError as exc:
        raise too_many_requests(exc) from exc
    try:
        scenario = await create_custom_scenario(db, user, profile, body.description, llm)
    except ScenarioRefusedError:
        raise HTTPException(
            status_code=422,
            detail="That scenario can't be used here. Try describing an everyday situation.",
        ) from None
    except LLMError as exc:
        logger.warning("Custom scenario failed for user %d: %s", user.id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Couldn't build your scenario right now. Please try again.",
        ) from exc
    return ScenarioOut.model_validate(scenario)
