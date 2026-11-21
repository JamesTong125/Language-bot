"""Level suggestions and the calendar helpers behind the dashboard. Pure functions."""

from datetime import date

import pytest

from app.progress.calendar import first_week_start, sessions_per_week, streak_days, week_start
from app.progress.level import SessionRate, suggest_level


def rates(*values: float) -> list[SessionRate]:
    return [SessionRate(session_id=100 - i, error_rate=v) for i, v in enumerate(values)]


# --- Level suggestions ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("values", "direction", "suggested"),
    [
        ((0.1, 0.0, 0.2), "up", "B1"),
        ((0.2, 0.2, 0.2), "up", "B1"),  # threshold is inclusive
        ((0.6, 0.7, 0.8), "down", "A1"),
        ((0.6, 0.6, 0.6), "down", "A1"),
        ((0.3, 0.4, 0.5), None, None),
        ((0.0, 0.0, 0.9), None, None),  # average 0.3
    ],
)
def test_three_sessions_decide_the_suggestion(
    values: tuple[float, ...], direction: str | None, suggested: str | None
) -> None:
    s = suggest_level("A2", rates(*values))
    assert (s.direction, s.suggested_level) == (direction, suggested)
    assert s.sessions_counted == 3


def test_fewer_than_three_sessions_never_suggest() -> None:
    s = suggest_level("A2", rates(0.0, 0.0))
    assert s.direction is None
    assert (s.sessions_counted, s.sessions_needed, s.average_error_rate) == (2, 3, 0.0)
    assert suggest_level("A2", []).average_error_rate is None


def test_only_the_three_newest_sessions_count() -> None:
    s = suggest_level("B1", rates(0.0, 0.1, 0.1, 0.9, 0.9))
    assert s.direction == "up"
    assert s.session_ids == [100, 99, 98]
    assert s.average_error_rate == pytest.approx(0.0667, abs=1e-4)


def test_no_suggestion_beyond_the_ends_of_the_scale() -> None:
    assert suggest_level("C2", rates(0, 0, 0)).direction is None
    assert suggest_level("A1", rates(1, 1, 1)).direction is None
    assert suggest_level("C1", rates(0, 0, 0)).suggested_level == "C2"


# --- Calendar ------------------------------------------------------------------------

TODAY = date(2026, 11, 20)  # a Friday


def d(day: int, month: int = 11) -> date:
    return date(2026, month, day)


def test_streak_counts_back_from_today() -> None:
    assert streak_days({d(20), d(19), d(18), d(16)}, TODAY) == (3, True)


def test_streak_survives_until_today_is_over() -> None:
    assert streak_days({d(19), d(18)}, TODAY) == (2, False)


def test_streak_is_broken_by_a_missed_day() -> None:
    assert streak_days({d(18), d(17)}, TODAY) == (0, False)
    assert streak_days(set(), TODAY) == (0, False)


def test_streak_crosses_month_boundaries() -> None:
    days = {date(2026, 12, 1), date(2026, 11, 30), date(2026, 11, 29)}
    assert streak_days(days, date(2026, 12, 1)) == (3, True)


def test_weeks_start_on_monday() -> None:
    assert week_start(TODAY) == d(16)
    assert week_start(d(16)) == d(16)
    assert week_start(d(15)) == d(9)  # Sunday belongs to the week before
    assert first_week_start(TODAY, 8) == date(2026, 9, 28)


def test_sessions_per_week_fills_empty_weeks_oldest_first() -> None:
    days = [d(20), d(16), d(15), d(3), date(2026, 9, 1)]  # last one is too old
    weeks = sessions_per_week(days, TODAY, 4)
    assert weeks == [(d(26, 10), 0), (d(2), 1), (d(9), 1), (d(16), 2)]
