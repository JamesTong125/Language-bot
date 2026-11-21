"""Adaptive difficulty: suggest a level change from recent error rates. Pure, no I/O.

A session counts when it has ended, was held at the learner's current level, and has at
least MIN_LEARNER_TURNS learner messages (shorter sessions say little). The suggestion looks
at the last WINDOW such sessions:
- average error rate at or below UP_THRESHOLD: suggest moving up one level;
- at or above DOWN_THRESHOLD: suggest moving down one level;
- otherwise, or with fewer than WINDOW sessions, no suggestion.
The learner always confirms the change.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.languages import CEFR_LEVELS

WINDOW = 3
MIN_LEARNER_TURNS = 3
UP_THRESHOLD = 0.2
DOWN_THRESHOLD = 0.6

Direction = Literal["up", "down"]

_RANK: dict[str, int] = {level: rank for rank, level in enumerate(CEFR_LEVELS)}


@dataclass(frozen=True)
class SessionRate:
    session_id: int
    error_rate: float  # 0 to 1: share of learner messages with a mistake


@dataclass(frozen=True)
class LevelSuggestion:
    current_level: str
    direction: Direction | None
    suggested_level: str | None
    average_error_rate: float | None
    sessions_counted: int
    sessions_needed: int
    session_ids: list[int]


def suggest_level(current: str, recent: Sequence[SessionRate]) -> LevelSuggestion:
    """``recent`` holds qualifying sessions, newest first. Only the first WINDOW are used."""
    window = list(recent)[:WINDOW]
    average = round(sum(s.error_rate for s in window) / len(window), 4) if window else None
    direction: Direction | None = None
    if len(window) == WINDOW and average is not None:
        if average <= UP_THRESHOLD:
            direction = "up"
        elif average >= DOWN_THRESHOLD:
            direction = "down"

    index = _RANK[current]
    suggested: str | None = None
    if direction == "up" and index + 1 < len(CEFR_LEVELS):
        suggested = CEFR_LEVELS[index + 1]
    elif direction == "down" and index > 0:
        suggested = CEFR_LEVELS[index - 1]
    if suggested is None:
        direction = None  # Already at A1 or C2.

    return LevelSuggestion(
        current_level=current,
        direction=direction,
        suggested_level=suggested,
        average_error_rate=average,
        sessions_counted=len(window),
        sessions_needed=WINDOW,
        session_ids=[s.session_id for s in window],
    )
