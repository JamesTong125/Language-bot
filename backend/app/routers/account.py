from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.deps import AppSettings, CurrentUser, DbSession
from app.schemas.account import DeleteAccountRequest
from app.security.cookies import clear_auth_cookie
from app.security.passwords import verify_password
from app.services.account_export import build_export
from app.services.users import delete_user

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export")
async def export_account(user: CurrentUser, db: DbSession) -> JSONResponse:
    export = await build_export(db, user)
    return JSONResponse(
        content=export.model_dump(mode="json"),
        headers={
            "Content-Disposition": 'attachment; filename="immersion-buddy-export.json"',
            "Cache-Control": "no-store",
        },
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    body: DeleteAccountRequest,
    response: Response,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> None:
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password")
    await delete_user(db, user)
    clear_auth_cookie(response, settings)
