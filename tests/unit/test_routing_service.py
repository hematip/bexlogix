"""Unit tests for deterministic nearest-neighbor route planning."""

# Purpose: Validate stable route ordering for known coordinate inputs.
# Workflow Role: Protects fallback planner behavior used when OSRM is unavailable.

from __future__ import annotations

import pytest

from server.app.services.routing_service import NearestNeighborRoutePlanner


@pytest.mark.unit
def test_nearest_neighbor_route_is_deterministic_for_fixed_coordinates() -> None:
    # Contract: Given fixed start/stops, NN planner should return deterministic order.
    planner = NearestNeighborRoutePlanner()
    stops = [
        {"assignment_id": 1, "store_code": "STR-1", "lat": 35.7010, "lon": 51.4010},
        {"assignment_id": 2, "store_code": "STR-2", "lat": 35.7090, "lon": 51.4090},
        {"assignment_id": 3, "store_code": "STR-3", "lat": 35.7300, "lon": 51.4300},
    ]
    planned = planner.plan_route(start_lat=35.7000, start_lon=51.4000, stops=stops)

    assert [p.assignment_id for p in planned] == [1, 2, 3]
    assert [p.route_order for p in planned] == [1, 2, 3]
    assert planned[0].route_distance_km is not None
    assert planned[-1].route_distance_km is not None
    assert float(planned[-1].route_distance_km) >= float(planned[0].route_distance_km)


@pytest.mark.unit
def test_nearest_neighbor_without_start_sorts_by_store_code() -> None:
    # Contract: Without start point, planner should preserve deterministic store-code ordering.
    planner = NearestNeighborRoutePlanner()
    stops = [
        {"assignment_id": 2, "store_code": "STR-200", "lat": 35.7090, "lon": 51.4090},
        {"assignment_id": 1, "store_code": "STR-100", "lat": 35.7010, "lon": 51.4010},
    ]
    planned = planner.plan_route(start_lat=None, start_lon=None, stops=stops)
    assert [p.assignment_id for p in planned] == [1, 2]
