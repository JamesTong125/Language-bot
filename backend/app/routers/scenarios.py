from fastapi import APIRouter

from app.deps import CurrentProfile, CurrentUser, DbSession
from app.schemas.conversation import ScenarioList, ScenarioOut
from app.services.scenarios import list_scenarios

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("")
async def get_scenarios(user: CurrentUser, profile: CurrentProfile, db: DbSession) -> ScenarioList:
    scenarios = await list_scenarios(db, user.id, profile.target_language)
    return ScenarioList(scenarios=[ScenarioOut.model_validate(s) for s in scenarios])
