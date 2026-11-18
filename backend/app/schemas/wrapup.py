"""The session wrap-up output contract, and the checks applied to it."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

_ONLY_IDS = re.compile(r"^\s*C\d+(\s*[,;/&]?\s*(and\s+)?C\d+)*\s*\.?\s*$", re.IGNORECASE)

MAX_VOCAB = 10
# Words the partner used (not from a correction) are capped: small models pad the list.
MAX_PARTNER_WORDS = 3


def _clean_list(values: list[str]) -> list[str]:
    return [v.strip() for v in values if v and v.strip()]


class SummaryIn(BaseModel):
    went_well: str = Field(min_length=1, max_length=600)
    recurring_mistakes: list[str] = Field(default_factory=list, max_length=3)
    practice: list[str] = Field(min_length=1, max_length=3)

    @field_validator("recurring_mistakes", "practice")
    @classmethod
    def clean(cls, values: list[str]) -> list[str]:
        cleaned = _clean_list(values)
        if any(len(v) > 300 for v in cleaned):
            raise ValueError("Each item must be under 300 characters")
        if any(_ONLY_IDS.match(v) for v in cleaned):
            raise ValueError("Describe each item in words, not as correction ids like C1")
        return cleaned

    @field_validator("went_well")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


class VocabIn(BaseModel):
    term: str = Field(min_length=1, max_length=120)
    translation: str = Field(min_length=1, max_length=200)
    example_sentence: str | None = Field(default=None, max_length=300)
    # "C3" when the word comes from correction C3 in the prompt, else null.
    source: str | None = None

    @field_validator("term", "translation")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("example_sentence", "source")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class WrapUpOut(SummaryIn):
    """Flat on purpose: small models often break nested JSON objects."""

    # Required (may be empty), so a reply that forgets the list triggers the retry.
    vocab: list[VocabIn] = Field(max_length=MAX_VOCAB)

    def summary(self) -> SummaryIn:
        return SummaryIn(
            went_well=self.went_well,
            recurring_mistakes=self.recurring_mistakes,
            practice=self.practice,
        )


_SOURCE = re.compile(r"^C(\d+)$", re.IGNORECASE)


def source_index(source: str | None, correction_count: int) -> int | None:
    """Turn "C3" into the 0-based index 2, if it names a correction that exists."""
    if not source:
        return None
    match = _SOURCE.match(source.strip())
    if not match:
        return None
    index = int(match.group(1)) - 1
    return index if 0 <= index < correction_count else None


# Leading articles to ignore when comparing terms, so "un café" and "el café" match.
_ARTICLES: dict[str, tuple[str, ...]] = {
    "es": ("el", "la", "los", "las", "un", "una", "unos", "unas"),
    "fr": ("le", "la", "les", "l'", "un", "une", "des", "du", "de la", "de l'"),
    "it": ("il", "lo", "la", "i", "gli", "le", "l'", "un", "uno", "una", "un'"),
    "pt": ("o", "a", "os", "as", "um", "uma", "uns", "umas"),
    "de": ("der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer"),
    "nl": ("de", "het", "een", "'t"),
    "sv": ("en", "ett"),
    "en": ("the", "a", "an", "to"),
}


def normalise_term(term: str, language: str | None = None) -> str:
    """The key used to spot duplicates: case, spacing, and edge punctuation don't count.

    With ``language``, a leading article is ignored too. Accents do count ("papa" and
    "papá" are different words).
    """
    term = term.casefold().replace("\u2019", "'")
    term = re.sub(r"\s+", " ", term).strip()
    term = term.strip(' .,;:!?¡¿"()[]«»').strip()
    for article in sorted(_ARTICLES.get(language or "", ()), key=len, reverse=True):
        joiner = "" if article.endswith("'") else " "
        prefix = article + joiner
        if term.startswith(prefix) and len(term) > len(prefix):
            return term[len(prefix) :].strip()
    return term


def _contains_phrase(haystack: str, phrase: str) -> bool:
    """Whole-word match, so "con" doesn't match inside "contigo"."""
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", haystack) is not None


def select_vocab(
    items: list[VocabIn],
    correction_count: int,
    learner_texts: list[str],
    known_terms: frozenset[str] = frozenset(),
    language: str | None = None,
) -> list[tuple[VocabIn, int | None]]:
    """Pick the words to add, with the index of the correction each came from.

    Keeps every item linked to a correction. Keeps at most MAX_PARTNER_WORDS others, and
    drops those the learner already typed themselves: they know that word. Terms already in
    the deck (``known_terms``, normalised) don't use up the partner-word allowance; the
    caller still counts them as skipped duplicates.
    """
    learner = " ".join(normalise_term(t) for t in learner_texts)
    chosen: list[tuple[VocabIn, int | None]] = []
    partner_words = 0
    for item in items:
        index = source_index(item.source, correction_count)
        if index is None:
            term = normalise_term(item.term, language)
            if not term or _contains_phrase(learner, term):
                continue
            if term not in known_terms:
                if partner_words >= MAX_PARTNER_WORDS:
                    continue
                partner_words += 1
        chosen.append((item, index))
    return chosen


@dataclass(frozen=True)
class CorrectionForVocab:
    corrected: str
    explanation: str


def cards_for_missed_corrections(
    chosen: Sequence[tuple[VocabIn, int | None]], corrections: Sequence[CorrectionForVocab]
) -> list[tuple[VocabIn, int]]:
    """Every mistake becomes a card, even if the model forgot it.

    For each correction no chosen item points at, make a card from the correction itself:
    the corrected text on the front, the explanation (in the learner's language) on the back.
    """
    covered = {index for _, index in chosen if index is not None}
    extra: list[tuple[VocabIn, int]] = []
    for index, c in enumerate(corrections):
        term = c.corrected.strip()
        if index in covered or not term or len(term) > 120:
            continue
        extra.append(
            (VocabIn(term=term, translation=c.explanation[:200], source=f"C{index + 1}"), index)
        )
    return extra
