from __future__ import annotations

from datetime import date

import pytest

from server.app.models.store import Store
from server.app.services import scheduling_service


def _store_for_interval(grade: str, confectionery: bool, oil: bool, pasta: bool) -> Store:
    return Store(
        store_code=f"S-{grade}-{int(confectionery)}{int(oil)}{int(pasta)}",
        store_name="Test Store",
        region="مرکز",
        address="آدرس تست",
        lat=35.7,
        lon=51.4,
        grade=grade,
        has_confectionery=confectionery,
        has_oil=oil,
        has_pasta=pasta,
        is_active=True,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "grade,category,expected",
    [
        ("VIP", "confectionery", 6),
        ("A+", "confectionery", 6),
        ("A", "confectionery", 9),
        ("B", "confectionery", 12),
        ("C", "confectionery", 20),
        ("VIP", "oil", 6),
        ("A+", "oil", 6),
        ("A", "oil", 9),
        ("B", "oil", 12),
        ("C", "oil", 20),
        ("VIP", "pasta", 6),
        ("A+", "pasta", 6),
        ("A", "pasta", 10),
        ("B", "pasta", 8),
        ("C", "pasta", 8),
    ],
)
def test_get_store_visit_interval_days_matrix(grade: str, category: str, expected: int) -> None:
    store = _store_for_interval(
        grade=grade,
        confectionery=category == "confectionery",
        oil=category == "oil",
        pasta=category == "pasta",
    )
    assert scheduling_service.get_store_visit_interval_days(store) == expected


@pytest.mark.unit
def test_get_store_visit_interval_days_uses_shortest_for_multi_category() -> None:
    store = _store_for_interval(grade="B", confectionery=True, oil=False, pasta=True)
    assert scheduling_service.get_store_visit_interval_days(store) == 8


@pytest.mark.unit
def test_compute_overdue_days_edge_cases() -> None:
    target = date(2026, 4, 3)
    assert scheduling_service.compute_overdue_days(None, target) == 0
    assert scheduling_service.compute_overdue_days(date(2026, 4, 3), target) == 0
    assert scheduling_service.compute_overdue_days(date(2026, 4, 5), target) == 0
    assert scheduling_service.compute_overdue_days(date(2026, 3, 28), target) == 6

