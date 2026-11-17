from fastapi import APIRouter
from sqlalchemy import text

from app.deps import DbSession
from app.languages import CEFR_LEVELS, LANGUAGES
from app.schemas.meta import LanguageOut, LanguagesOut

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(db: DbSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/languages")
async def languages() -> LanguagesOut:
    return LanguagesOut(
        languages=[
            LanguageOut(
                code=lang.code,
                name=lang.name,
                native_name=lang.native_name,
                speech_tag=lang.speech_tag,
            )
            for lang in LANGUAGES
        ],
        cefr_levels=list(CEFR_LEVELS),
    )
