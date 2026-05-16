"""Tests for the territory clustering service."""

from __future__ import annotations

import random

import pytest

from server.app.services.territory_service import (
    cluster_stores_to_visitors,
    territory_spread_km,
)
from server.app.utils.geo import haversine_km


def _make_visitor(visitor_id: int, lat: float, lon: float, capacity: int = 30):
    return {
        "visitor_id": visitor_id,
        "start_lat": lat,
        "start_lon": lon,
        "capacity": capacity,
    }


def _make_store(store_id: int, lat: float, lon: float):
    return {"store_id": store_id, "lat": lat, "lon": lon}


class TestClusterStoresToVisitors:
    def test_empty_inputs_return_empty(self):
        assert cluster_stores_to_visitors([], []) == []
        assert cluster_stores_to_visitors([_make_visitor(1, 35.7, 51.3)], []) != []
        # No stores: visitors get empty cluster lists
        result = cluster_stores_to_visitors([_make_visitor(1, 35.7, 51.3)], [])
        assert result[0].store_ids == []

    def test_visitor_without_start_is_excluded(self):
        visitors = [
            _make_visitor(1, 35.7, 51.3),
            {"visitor_id": 2, "start_lat": None, "start_lon": None, "capacity": 30},
        ]
        stores = [_make_store(100, 35.7, 51.3)]
        result = cluster_stores_to_visitors(visitors, stores)
        assert {r.visitor_id for r in result} == {1}

    def test_balances_to_capacity_limit(self):
        # Two visitors close together, six stores. With capacity 3 each, the
        # algorithm must split 3/3 even though all stores are nearer one start.
        visitors = [
            _make_visitor(1, 35.70, 51.30, capacity=3),
            _make_visitor(2, 35.71, 51.31, capacity=3),
        ]
        stores = [
            _make_store(100 + i, 35.70 + 0.001 * i, 51.30 + 0.001 * i)
            for i in range(6)
        ]
        result = cluster_stores_to_visitors(visitors, stores)
        counts = {r.visitor_id: r.used_capacity for r in result}
        assert counts[1] == 3
        assert counts[2] == 3

    def test_assignment_is_deterministic(self):
        visitors = [
            _make_visitor(1, 35.65, 51.25, capacity=10),
            _make_visitor(2, 35.80, 51.45, capacity=10),
        ]
        stores = [
            _make_store(i + 1, 35.5 + (i % 5) * 0.05, 51.2 + (i // 5) * 0.05)
            for i in range(20)
        ]
        r1 = cluster_stores_to_visitors(visitors, stores)
        r2 = cluster_stores_to_visitors(visitors, stores)
        for a, b in zip(r1, r2):
            assert a.store_ids == b.store_ids

    def test_each_store_assigned_to_exactly_one_visitor(self):
        rng = random.Random(42)
        visitors = [
            _make_visitor(i + 1, 35.65 + i * 0.02, 51.30 + i * 0.02, capacity=15)
            for i in range(4)
        ]
        stores = [
            _make_store(
                i + 1,
                35.55 + rng.random() * 0.30,
                51.20 + rng.random() * 0.40,
            )
            for i in range(50)
        ]
        result = cluster_stores_to_visitors(visitors, stores)
        all_ids: list[int] = []
        for r in result:
            all_ids.extend(r.store_ids)
        assert sorted(all_ids) == [s["store_id"] for s in stores]
        # No duplicates
        assert len(set(all_ids)) == 50

    def test_clustering_beats_global_assignment_on_clustered_starts(self):
        """When visitor starts are clustered, the global VRP would let
        per-visitor tours sprawl across the city. The territory clustering
        must produce a tight per-visitor radius."""
        rng = random.Random(123)
        # 10 visitors clustered in a tight 1x1 km area near city center.
        visitors = [
            _make_visitor(
                i + 1,
                35.700 + rng.random() * 0.01,
                51.350 + rng.random() * 0.01,
                capacity=30,
            )
            for i in range(10)
        ]
        # 300 stores spread across a 30x30 km area.
        stores = [
            _make_store(
                i + 1,
                35.55 + rng.random() * 0.30,
                51.20 + rng.random() * 0.40,
            )
            for i in range(300)
        ]
        result = cluster_stores_to_visitors(visitors, stores)
        stores_by_id = {s["store_id"]: s for s in stores}

        radii = [territory_spread_km(r, stores_by_id) for r in result]
        mean_radius = sum(radii) / len(radii)
        # With a 30x30 km region split into 10 territories, the mean radius
        # of an ideal split is around 5-8 km. Allow a generous ceiling that
        # still proves the territory is not the full city.
        assert mean_radius < 15.0, (
            f"mean territory radius {mean_radius:.1f}km too large; "
            "clustering is not partitioning effectively"
        )

    def test_capacity_zero_visitor_gets_no_stores(self):
        visitors = [
            _make_visitor(1, 35.7, 51.3, capacity=0),
            _make_visitor(2, 35.8, 51.4, capacity=10),
        ]
        stores = [_make_store(i + 1, 35.75, 51.35) for i in range(3)]
        result = cluster_stores_to_visitors(visitors, stores)
        counts = {r.visitor_id: r.used_capacity for r in result}
        assert counts[1] == 0
        assert counts[2] == 3
