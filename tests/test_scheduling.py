"""Tests for scheduling state transitions."""

from __future__ import annotations

from datetime import date

import pytest

from server.app.models.store import Store
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.services.scheduling_service import (
    apply_telesales_event_to_state,
    apply_visit_event_to_state,
    compute_overdue_days,
    get_store_visit_interval_days,
)


def _make_store(grade="A+", confectionery=True, oil=False, pasta=False):
    return Store(
        store_code="STR-TEST",
        store_name="Test",
        region="مرکز",
        lat=35.7,
        lon=51.3,
        grade=grade,
        has_confectionery=confectionery,
        has_oil=oil,
        has_pasta=pasta,
    )


def _make_state(store_id=1):
    return StoreScheduleState(
        store_id=store_id,
        next_visit_date=date(2026, 5, 15),
        overdue_days=0,
        in_telesales_queue=False,
    )


class TestGetStoreVisitIntervalDays:
    @pytest.mark.parametrize(
        "grade,confectionery,oil,pasta,expected",
        [
            ("VIP", True, False, False, 6),
            ("A+", False, True, False, 6),
            ("A", True, False, False, 9),
            ("A", False, False, True, 10),
            ("A", True, False, True, 9),  # min of 9 and 10
            ("B", False, False, True, 8),
            ("C", True, True, True, 8),  # min of 20, 20, 8
        ],
    )
    def test_interval_uses_minimum_of_active_categories(
        self, grade, confectionery, oil, pasta, expected
    ):
        store = _make_store(grade=grade, confectionery=confectionery, oil=oil, pasta=pasta)
        assert get_store_visit_interval_days(store) == expected

    def test_unsupported_grade_raises(self):
        store = _make_store(grade="ZZZ", confectionery=True)
        with pytest.raises(ValueError):
            get_store_visit_interval_days(store)

    def test_no_active_category_raises(self):
        store = _make_store(confectionery=False, oil=False, pasta=False)
        with pytest.raises(ValueError):
            get_store_visit_interval_days(store)


class TestComputeOverdueDays:
    def test_none_next_visit_is_not_overdue(self):
        assert compute_overdue_days(None, date(2026, 5, 15)) == 0

    def test_future_next_visit_is_not_overdue(self):
        assert compute_overdue_days(date(2026, 5, 20), date(2026, 5, 15)) == 0

    def test_past_next_visit_is_overdue(self):
        assert compute_overdue_days(date(2026, 5, 10), date(2026, 5, 15)) == 5

    def test_same_day_is_not_overdue(self):
        assert compute_overdue_days(date(2026, 5, 15), date(2026, 5, 15)) == 0


class TestApplyVisitEventToState:
    def test_green_sets_next_visit_to_interval_in_future(self):
        store = _make_store(grade="A+", confectionery=True)  # interval=6
        state = _make_state()
        apply_visit_event_to_state(state, store, date(2026, 5, 15), "green")
        assert state.last_visit_result == "green"
        assert state.next_visit_date == date(2026, 5, 21)
        assert state.in_telesales_queue is False
        assert state.overdue_days == 0

    def test_yellow_retries_after_3_days(self):
        store = _make_store(grade="A+", confectionery=True)
        state = _make_state()
        apply_visit_event_to_state(state, store, date(2026, 5, 15), "yellow")
        assert state.next_visit_date == date(2026, 5, 18)
        assert state.in_telesales_queue is False

    def test_red_clears_next_visit_and_queues_telesales(self):
        store = _make_store(grade="A+", confectionery=True)
        state = _make_state()
        apply_visit_event_to_state(state, store, date(2026, 5, 15), "red")
        assert state.next_visit_date is None
        assert state.in_telesales_queue is True

    def test_invalid_result_raises(self):
        store = _make_store(grade="A+", confectionery=True)
        state = _make_state()
        with pytest.raises(ValueError):
            apply_visit_event_to_state(state, store, date(2026, 5, 15), "blue")

    def test_case_insensitive_result(self):
        store = _make_store(grade="A+", confectionery=True)
        state = _make_state()
        apply_visit_event_to_state(state, store, date(2026, 5, 15), "GREEN")
        assert state.last_visit_result == "green"


class TestApplyTelesalesEventToState:
    def test_sale_done_uses_visit_interval(self):
        store = _make_store(grade="A+", confectionery=True)  # interval=6
        state = _make_state()
        apply_telesales_event_to_state(state, store, date(2026, 5, 15), "sale_done")
        assert state.next_visit_date == date(2026, 5, 21)
        assert state.in_telesales_queue is False

    def test_postpone_keeps_in_queue(self):
        store = _make_store(grade="A+", confectionery=True)
        state = _make_state()
        apply_telesales_event_to_state(state, store, date(2026, 5, 15), "postpone")
        assert state.next_visit_date is None
        assert state.in_telesales_queue is True

    def test_no_need_clears_queue(self):
        store = _make_store(grade="A+", confectionery=True)
        state = _make_state()
        apply_telesales_event_to_state(state, store, date(2026, 5, 15), "no_need")
        assert state.in_telesales_queue is False
        assert state.next_visit_date is not None

    def test_invalid_outcome_raises(self):
        store = _make_store(grade="A+", confectionery=True)
        state = _make_state()
        with pytest.raises(ValueError):
            apply_telesales_event_to_state(state, store, date(2026, 5, 15), "wat")
