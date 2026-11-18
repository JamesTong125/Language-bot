"""The SM-2 scheduler. These tests are the specification for how ratings move due dates."""

from datetime import UTC, datetime, timedelta

import pytest

from app.srs.scheduler import MIN_EASE, SrsState, new_card, next_ease, schedule

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


def state(ease: float = 2.5, interval: int = 0, reps: int = 0) -> SrsState:
    return SrsState(ease=ease, interval_days=interval, repetitions=reps, due_at=NOW)


def test_new_card_is_due_now_with_default_ease() -> None:
    card = new_card(NOW)
    assert (card.ease, card.interval_days, card.repetitions, card.due_at) == (2.5, 0, 0, NOW)


@pytest.mark.parametrize("rating", [0, 1, 2])
def test_failing_ratings_reset_to_one_day(rating: int) -> None:
    after = schedule(state(ease=2.5, interval=30, reps=5), rating, NOW)
    assert after.repetitions == 0
    assert after.interval_days == 1
    assert after.due_at == NOW + timedelta(days=1)


@pytest.mark.parametrize("rating", [3, 4, 5])
def test_first_pass_is_one_day_second_is_six(rating: int) -> None:
    first = schedule(new_card(NOW), rating, NOW)
    assert (first.repetitions, first.interval_days) == (1, 1)
    assert first.due_at == NOW + timedelta(days=1)
    second = schedule(first, rating, NOW)
    assert (second.repetitions, second.interval_days) == (2, 6)
    assert second.due_at == NOW + timedelta(days=6)


def test_later_intervals_grow_by_the_ease_factor() -> None:
    # Rating 4 keeps ease at 2.5: 1, 6, 15, 38, 95 days.
    card = new_card(NOW)
    intervals = []
    for _ in range(5):
        card = schedule(card, 4, NOW)
        intervals.append(card.interval_days)
    assert intervals == [1, 6, 15, 38, 95]
    assert card.ease == 2.5


def test_ease_changes_follow_sm2() -> None:
    assert next_ease(2.5, 5) == 2.6
    assert next_ease(2.5, 4) == 2.5
    assert next_ease(2.5, 3) == 2.36
    assert next_ease(2.5, 2) == 2.18
    assert next_ease(2.5, 1) == 1.96
    assert next_ease(2.5, 0) == 1.7


def test_ease_never_drops_below_minimum() -> None:
    card = state(ease=1.4)
    for _ in range(5):
        card = schedule(card, 0, NOW)
    assert card.ease == MIN_EASE


def test_easy_ratings_grow_faster_than_hard_ones() -> None:
    hard = easy = schedule(schedule(new_card(NOW), 4, NOW), 4, NOW)  # both at 6 days
    hard, easy = schedule(hard, 3, NOW), schedule(easy, 5, NOW)
    assert hard.interval_days < easy.interval_days
    assert (hard.interval_days, easy.interval_days) == (14, 16)


def test_a_lapse_then_recovery_starts_over() -> None:
    card = schedule(schedule(schedule(new_card(NOW), 5, NOW), 5, NOW), 5, NOW)
    assert card.interval_days > 6
    lapsed = schedule(card, 1, NOW)
    assert (lapsed.repetitions, lapsed.interval_days) == (0, 1)
    recovered = schedule(lapsed, 4, NOW)
    assert (recovered.repetitions, recovered.interval_days) == (1, 1)
    # Ease lost in the lapse is kept, so the card comes back more often than before.
    assert recovered.ease < card.ease


def test_due_date_is_relative_to_review_time() -> None:
    later = NOW + timedelta(days=10)
    assert schedule(new_card(NOW), 4, later).due_at == later + timedelta(days=1)


def test_schedule_does_not_modify_its_input() -> None:
    card = state(ease=2.5, interval=6, reps=2)
    schedule(card, 5, NOW)
    assert card == state(ease=2.5, interval=6, reps=2)


@pytest.mark.parametrize("rating", [-1, 6])
def test_out_of_range_rating_is_rejected(rating: int) -> None:
    with pytest.raises(ValueError):
        schedule(new_card(NOW), rating, NOW)
