"""The error-analysis output contract, and the checks applied to what the model returns.

Two layers:
1. ``AnalysisOut`` (Pydantic) checks the shape. A failure here triggers the one retry.
2. ``usable_corrections`` drops individual items that are well formed but wrong for this
   message: a span that isn't in the learner's text, or a "fix" that changes nothing.
"""

import logging
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

ErrorType = Literal["grammar", "vocabulary", "spelling", "word_order", "conjugation", "register"]

MAX_CORRECTIONS = 8


class CorrectionIn(BaseModel):
    original: str = Field(min_length=1, max_length=200)
    corrected: str = Field(max_length=200)
    error_type: ErrorType
    explanation: str = Field(min_length=1, max_length=400)
    severity: int = Field(ge=1, le=3)

    @field_validator("error_type", mode="before")
    @classmethod
    def normalise_type(cls, value: object) -> object:
        # Small models write "Word order", "word-order", or "word order".
        if isinstance(value, str):
            return re.sub(r"[\s-]+", "_", value.strip().lower())
        return value

    @field_validator("original", "corrected", "explanation")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


class AnalysisOut(BaseModel):
    corrections: list[CorrectionIn] = Field(max_length=MAX_CORRECTIONS)


def _normalise(text: str) -> str:
    """Compare text case-insensitively, ignoring spacing and curly-vs-straight quotes."""
    text = unicodedata.normalize("NFC", text).casefold()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", text).strip()


def usable_corrections(analysis: AnalysisOut, learner_text: str) -> list[CorrectionIn]:
    """Keep corrections that point at real text and actually change something."""
    haystack = _normalise(learner_text)
    kept: list[CorrectionIn] = []
    seen: set[tuple[str, str]] = set()
    dropped = 0
    for item in analysis.corrections:
        original, corrected = _normalise(item.original), _normalise(item.corrected)
        key = (original, corrected)
        if original not in haystack or original == corrected or key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(item)
    if dropped:
        logger.info("Dropped %d unusable corrections", dropped)
    return kept
