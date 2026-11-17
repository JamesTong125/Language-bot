from pydantic import BaseModel

from app.languages import CefrLevel


class LanguageOut(BaseModel):
    code: str
    name: str
    native_name: str
    speech_tag: str


class LanguagesOut(BaseModel):
    languages: list[LanguageOut]
    cefr_levels: list[CefrLevel]
