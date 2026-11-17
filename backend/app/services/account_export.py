"""Builds the data export for a user. Extend this whenever a table gains user data."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.account import AccountExport, ExportedUser
from app.schemas.profile import LearnerProfileOut
from app.services.profiles import list_profiles


async def build_export(db: AsyncSession, user: User) -> AccountExport:
    profiles = await list_profiles(db, user.id)
    return AccountExport(
        exported_at=datetime.now(UTC),
        user=ExportedUser(
            id=user.id,
            email=user.email,
            native_language=user.native_language,
            created_at=user.created_at,
        ),
        learner_profiles=[LearnerProfileOut.model_validate(p) for p in profiles],
    )
