"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.llm.base import LLMClient
from app.llm.factory import get_analysis_llm, get_chat_llm, get_private_llm
from app.models import LearnerProfile, User
from app.security.cookies import COOKIE_NAME
from app.security.tokens import decode_user_id
from app.services.profiles import get_current_profile as get_current_profile_for
from app.services.rate_limits import RateLimitedError
from app.services.users import get_user

DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    db: DbSession,
    settings: AppSettings,
    access_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    if not access_token:
        raise unauthorized
    user_id = decode_user_id(access_token, settings.jwt_secret)
    if user_id is None:
        raise unauthorized
    user = await get_user(db, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_profile(user: CurrentUser, db: DbSession) -> LearnerProfile:
    """The learner's current profile. 409 if they haven't finished onboarding."""
    profile = await get_current_profile_for(db, user.id)
    if profile is None or not user.native_language:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Finish setting up your profile first"
        )
    return profile


CurrentProfile = Annotated[LearnerProfile, Depends(get_current_profile)]
ChatLLM = Annotated[LLMClient, Depends(get_chat_llm)]
AnalysisLLM = Annotated[LLMClient, Depends(get_analysis_llm)]
PrivateLLM = Annotated[LLMClient | None, Depends(get_private_llm)]


def too_many_requests(exc: RateLimitedError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=exc.message,
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )
