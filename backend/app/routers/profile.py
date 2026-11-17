from fastapi import APIRouter

from app.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.profile import LearnerProfileOut, ProfileOut, ProfileUpdate
from app.services.profiles import list_profiles, upsert_profile

router = APIRouter(prefix="/profile", tags=["profile"])


async def _profile_out(db: DbSession, user: User) -> ProfileOut:
    profiles = [LearnerProfileOut.model_validate(p) for p in await list_profiles(db, user.id)]
    return ProfileOut(
        email=user.email,
        native_language=user.native_language,
        current=profiles[0] if profiles else None,
        profiles=profiles,
    )


@router.get("")
async def get_profile(user: CurrentUser, db: DbSession) -> ProfileOut:
    return await _profile_out(db, user)


@router.put("")
async def put_profile(body: ProfileUpdate, user: CurrentUser, db: DbSession) -> ProfileOut:
    await upsert_profile(db, user, body)
    return await _profile_out(db, user)
