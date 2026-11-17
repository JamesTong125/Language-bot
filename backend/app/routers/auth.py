from fastapi import APIRouter, HTTPException, Response, status

from app.deps import AppSettings, DbSession
from app.schemas.auth import LoginRequest, RegisterRequest, UserOut
from app.security.cookies import clear_auth_cookie, set_auth_cookie
from app.security.tokens import create_access_token
from app.services.users import EmailTakenError, authenticate, create_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_out(user_id: int, email: str, native_language: str | None) -> UserOut:
    return UserOut(id=user_id, email=email, native_language=native_language)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, response: Response, db: DbSession, settings: AppSettings
) -> UserOut:
    try:
        user = await create_user(db, body.email, body.password, body.native_language)
    except EmailTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An account with this email exists"
        ) from None
    token = create_access_token(user.id, settings.jwt_secret, settings.jwt_expiry_days)
    set_auth_cookie(response, token, settings)
    return _to_out(user.id, user.email, user.native_language)


@router.post("/login")
async def login(
    body: LoginRequest, response: Response, db: DbSession, settings: AppSettings
) -> UserOut:
    user = await authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    token = create_access_token(user.id, settings.jwt_secret, settings.jwt_expiry_days)
    set_auth_cookie(response, token, settings)
    return _to_out(user.id, user.email, user.native_language)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, settings: AppSettings) -> None:
    clear_auth_cookie(response, settings)
