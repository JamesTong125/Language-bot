"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.models import User
from app.security.cookies import COOKIE_NAME
from app.security.tokens import decode_user_id
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
