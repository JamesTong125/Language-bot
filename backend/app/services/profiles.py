"""Learner profile persistence. A user has one profile per target language."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearnerProfile, User
from app.schemas.profile import ProfileUpdate


async def list_profiles(db: AsyncSession, user_id: int) -> list[LearnerProfile]:
    """All profiles for a user, most recently updated (the current one) first."""
    result = await db.execute(
        select(LearnerProfile)
        .where(LearnerProfile.user_id == user_id)
        .order_by(LearnerProfile.updated_at.desc(), LearnerProfile.id.desc())
    )
    return list(result.scalars())


async def get_current_profile(db: AsyncSession, user_id: int) -> LearnerProfile | None:
    profiles = await list_profiles(db, user_id)
    return profiles[0] if profiles else None


async def upsert_profile(db: AsyncSession, user: User, update: ProfileUpdate) -> LearnerProfile:
    """Create or update the profile for the target language and make it current."""
    user.native_language = update.native_language

    result = await db.execute(
        select(LearnerProfile).where(
            LearnerProfile.user_id == user.id,
            LearnerProfile.target_language == update.target_language,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = LearnerProfile(user_id=user.id, target_language=update.target_language)
        db.add(profile)

    profile.cefr_level = update.cefr_level
    profile.goals = update.goals
    # Always bump updated_at, even if nothing else changed, so this profile becomes current.
    profile.updated_at = func.clock_timestamp()

    await db.commit()
    await db.refresh(profile)
    return profile
