"""Simplified SM-2 spaced-repetition scheduler. Pure functions, no I/O.

Ratings are 0 to 5, as in SM-2:
  0 blackout, 1 wrong, 2 wrong but familiar, 3 right with effort, 4 right, 5 easy.

- Ratings 0 to 2 reset the card: repetitions 0, interval 1 day.
- Ratings 3 to 5 grow the interval: 1 day, then 6 days, then the previous interval times
  the ease factor, rounded.
- Every rating adjusts the ease factor with the SM-2 formula, never below 1.3.
  The new ease is used for the interval that follows.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

DEFAULT_EASE = 2.5
MIN_EASE = 1.3
PASSING_RATING = 3
FIRST_INTERVAL_DAYS = 1
SECOND_INTERVAL_DAYS = 6


@dataclass(frozen=True)
class SrsState:
    ease: float
    interval_days: int
    repetitions: int
    due_at: datetime


def new_card(now: datetime) -> SrsState:
    """A fresh card is due right away."""
    return SrsState(ease=DEFAULT_EASE, interval_days=0, repetitions=0, due_at=now)


def next_ease(ease: float, rating: int) -> float:
    miss = 5 - rating
    return max(MIN_EASE, round(ease + 0.1 - miss * (0.08 + miss * 0.02), 4))


def schedule(item: SrsState, rating: int, now: datetime) -> SrsState:
    """Return the card's new state after a review. ``item`` is not modified."""
    if not 0 <= rating <= 5:
        raise ValueError(f"rating must be 0 to 5, got {rating}")
    ease = next_ease(item.ease, rating)
    if rating < PASSING_RATING:
        repetitions, interval = 0, FIRST_INTERVAL_DAYS
    else:
        repetitions = item.repetitions + 1
        if repetitions == 1:
            interval = FIRST_INTERVAL_DAYS
        elif repetitions == 2:
            interval = SECOND_INTERVAL_DAYS
        else:
            interval = max(1, round(item.interval_days * ease))
    return replace(
        item,
        ease=ease,
        interval_days=interval,
        repetitions=repetitions,
        due_at=now + timedelta(days=interval),
    )
