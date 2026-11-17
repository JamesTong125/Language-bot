"""User account persistence."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.security.passwords import hash_password, verify_password


class EmailTakenError(Exception):
    pass


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, email: str, password: str, native_language: str | None
) -> User:
    user = User(email=email, password_hash=hash_password(password), native_language=native_language)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise EmailTakenError from exc
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not verify_password(password, user.password_hash if user else None):
        return None
    return user


async def delete_user(db: AsyncSession, user: User) -> None:
    """Delete the user. Foreign keys cascade to every related row."""
    await db.delete(user)
    await db.commit()
