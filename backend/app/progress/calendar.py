"""Streak and weekly bucketing over local dates. Pure functions, no I/O."""

from collections import Counter
from collections.abc import Iterable
from datetime import date, timedelta


def streak_days(active_days: Iterable[date], today: date) -> tuple[int, bool]:
    """Consecutive days with practice, ending today or yesterday.

    A streak isn't broken until a whole day passes without practice, so practising
    yesterday but not yet today still counts. Returns (days, practised_today).
    """
    days = set(active_days)
    practised_today = today in days
    day = today if practised_today else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count, practised_today


def week_start(day: date) -> date:
    """The Monday of the week containing ``day``."""
    return day - timedelta(days=day.weekday())


def first_week_start(today: date, weeks: int) -> date:
    return week_start(today) - timedelta(weeks=weeks - 1)


def sessions_per_week(
    session_days: Iterable[date], today: date, weeks: int
) -> list[tuple[date, int]]:
    """Counts for the last ``weeks`` weeks including this one, oldest first, zeros included."""
    first = first_week_start(today, weeks)
    counts = Counter(week_start(d) for d in session_days if d >= first)
    return [
        (first + timedelta(weeks=i), counts.get(first + timedelta(weeks=i), 0))
        for i in range(weeks)
    ]
