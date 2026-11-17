"""Supported languages and CEFR levels."""

from dataclasses import dataclass
from typing import Literal

CefrLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_LEVELS: tuple[CefrLevel, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1
    name: str  # English name
    native_name: str
    speech_tag: str  # BCP 47 tag for the browser Web Speech API


LANGUAGES: tuple[Language, ...] = (
    Language("en", "English", "English", "en-US"),
    Language("es", "Spanish", "Español", "es-ES"),
    Language("fr", "French", "Français", "fr-FR"),
    Language("de", "German", "Deutsch", "de-DE"),
    Language("it", "Italian", "Italiano", "it-IT"),
    Language("pt", "Portuguese", "Português", "pt-BR"),
    Language("nl", "Dutch", "Nederlands", "nl-NL"),
    Language("pl", "Polish", "Polski", "pl-PL"),
    Language("sv", "Swedish", "Svenska", "sv-SE"),
    Language("ja", "Japanese", "日本語", "ja-JP"),
    Language("ko", "Korean", "한국어", "ko-KR"),
    Language("zh", "Chinese (Mandarin)", "中文", "zh-CN"),
)

LANGUAGE_CODES: frozenset[str] = frozenset(lang.code for lang in LANGUAGES)


def is_supported(code: str) -> bool:
    return code in LANGUAGE_CODES
