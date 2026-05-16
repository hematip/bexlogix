"""Tests for the routing service."""

from __future__ import annotations

import pytest

from server.app.services.routing_service import (
    NearestNeighborRoutePlanner,
    OSRMRoutePlanner,
    VroomRoutePlanner,
)


class TestNearestNeighborRoutePlanner:
    def test_empty_stops_returns_empty(self):
        planner = NearestNeighborRoutePlanner()
        assert planner.plan_route(35.7, 51.3, []) == []

    def test_missing_start_falls_back_to_alphabetical(self):
        planner = NearestNeighborRoutePlanner()
        stops = [
            {"assignment_id": 1, "store_code": "C", "lat": 35.7, "lon": 51.3},
            {"assignment_id": 2, "store_code": "A", "lat": 35.8, "lon": 51.4},
            {"assignment_id": 3, "store_code": "B", "lat": 35.6, "lon": 51.2},
        ]
        planned = planner.plan_route(None, None, stops)
        assert [p.assignment_id for p in planned] == [2, 3, 1]

    def test_greedy_picks_nearest_first(self):
        planner = NearestNeighborRoutePlanner()
        # Start at (35.70, 51.30). Nearest is (35.71, 51.31), then (35.72, 51.32),
        # then (35.80, 51.40).
        stops = [
            {"assignment_id": 1, "store_code": "FAR", "lat": 35.80, "lon": 51.40},
            {"assignment_id": 2, "store_code": "MID", "lat": 35.72, "lon": 51.32},
            {"assignment_id": 3, "store_code": "NEAR", "lat": 35.71, "lon": 51.31},
        ]
        planned = planner.plan_route(35.70, 51.30, stops)
        assert [p.assignment_id for p in planned] == [3, 2, 1]
        # route_order is contiguous starting at 1
        assert [p.route_order for p in planned] == [1, 2, 3]
        # cumulative distance is non-decreasing
        for prev, curr in zip(planned, planned[1:]):
            assert curr.route_distance_km >= prev.route_distance_km

    def test_each_stop_appears_exactly_once(self):
        planner = NearestNeighborRoutePlanner()
        stops = [
            {"assignment_id": i, "store_code": f"S{i:02d}",
             "lat": 35.7 + 0.001 * i, "lon": 51.3 + 0.001 * i}
            for i in range(10)
        ]
        planned = planner.plan_route(35.70, 51.30, stops)
        assert sorted(p.assignment_id for p in planned) == sorted(s["assignment_id"] for s in stops)
        assert len(planned) == len(stops)


class TestOSRMPayloadParsing:
    """Direct tests of the trip-payload parser with synthetic OSRM responses."""

    def _planner(self):
        # OSRM disabled — we call _to_route_stops_from_payload directly.
        return OSRMRoutePlanner(base_url="", timeout_seconds=0.1)

    def _make_payload(self, waypoint_indices: list[int | None], leg_distances_m: list[float]) -> dict:
        waypoints = [{"waypoint_index": 0}]
        for wi in waypoint_indices:
            waypoints.append({"waypoint_index": wi})
        return {
            "code": "Ok",
            "waypoints": waypoints,
            "trips": [{"legs": [{"distance": d} for d in leg_distances_m]}],
        }

    def test_full_route_parses_correctly(self):
        stops = [
            {"assignment_id": 10, "store_code": "A", "lat": 35.7, "lon": 51.3},
            {"assignment_id": 20, "store_code": "B", "lat": 35.8, "lon": 51.4},
            {"assignment_id": 30, "store_code": "C", "lat": 35.6, "lon": 51.2},
        ]
        # OSRM reorders to C -> A -> B
        payload = self._make_payload(
            waypoint_indices=[2, 3, 1],
            leg_distances_m=[1000.0, 2500.0, 1500.0],
        )
        planned = self._planner()._to_route_stops_from_payload(payload, stops)

        # Sorted by route_order: C (1), A (2), B (3)
        assert [p.route_order for p in planned] == [1, 2, 3]
        assert [p.assignment_id for p in planned] == [30, 10, 20]
        # Cumulative distance in km
        assert planned[0].route_distance_km == pytest.approx(1.0)
        assert planned[1].route_distance_km == pytest.approx(3.5)
        assert planned[2].route_distance_km == pytest.approx(5.0)

    def test_skipped_unreachable_waypoint_is_tolerated(self):
        # Regression test: OSRM may return waypoint_index=None for an
        # unreachable stop. The old parser raised a hard error; the new
        # parser must accept it and report the remaining stops.
        stops = [
            {"assignment_id": 10, "store_code": "A", "lat": 35.7, "lon": 51.3},
            {"assignment_id": 20, "store_code": "B", "lat": 35.8, "lon": 51.4},
        ]
        payload = self._make_payload(
            waypoint_indices=[1, None],
            leg_distances_m=[1234.0],
        )
        planned = self._planner()._to_route_stops_from_payload(payload, stops)
        # Only one stop is part of the trip.
        assert len(planned) == 1
        assert planned[0].assignment_id == 10
        assert planned[0].route_distance_km == pytest.approx(1.234)

    def test_extra_waypoints_is_hard_error(self):
        stops = [
            {"assignment_id": 10, "store_code": "A", "lat": 35.7, "lon": 51.3},
        ]
        payload = self._make_payload(
            waypoint_indices=[1, 2, 3],
            leg_distances_m=[1000.0, 1000.0, 1000.0],
        )
        with pytest.raises(ValueError):
            self._planner()._to_route_stops_from_payload(payload, stops)

    def test_zero_accepted_waypoints_is_hard_error(self):
        stops = [
            {"assignment_id": 10, "store_code": "A", "lat": 35.7, "lon": 51.3},
        ]
        payload = self._make_payload(
            waypoint_indices=[None],
            leg_distances_m=[],
        )
        with pytest.raises(ValueError):
            self._planner()._to_route_stops_from_payload(payload, stops)

    def test_non_ok_code_raises(self):
        stops = [
            {"assignment_id": 10, "store_code": "A", "lat": 35.7, "lon": 51.3},
        ]
        with pytest.raises(ValueError):
            self._planner()._to_route_stops_from_payload(
                {"code": "NoRoute", "message": "blocked"}, stops
            )


class TestVroomPayloadParsing:
    def _planner(self):
        return VroomRoutePlanner(base_url="http://localhost:0", timeout_seconds=0.1)

    def test_assignments_and_unassigned_are_returned(self):
        stores = [
            {"store_id": 100, "store_code": "S1", "lat": 35.7, "lon": 51.3},
            {"store_id": 200, "store_code": "S2", "lat": 35.8, "lon": 51.4},
            {"store_id": 300, "store_code": "S3", "lat": 35.6, "lon": 51.2},
        ]
        payload = {
            "routes": [
                {
                    "vehicle": 1,
                    "steps": [
                        {"type": "job", "job": 100, "distance": 1000},
                        {"type": "job", "job": 200, "distance": 2500},
                    ],
                }
            ],
            "unassigned": [{"id": 300}],
        }
        result = self._planner()._parse_solution(payload, stores)
        assert result.solver_mode == "vroom"
        assert [(a.visitor_id, a.store_id, a.route_order) for a in result.assignments] == [
            (1, 100, 1),
            (1, 200, 2),
        ]
        assert result.unassigned_store_ids == [300]

    def test_missing_unassigned_field_is_filled_in(self):
        stores = [
            {"store_id": 100, "store_code": "S1", "lat": 35.7, "lon": 51.3},
            {"store_id": 200, "store_code": "S2", "lat": 35.8, "lon": 51.4},
        ]
        payload = {
            "routes": [
                {
                    "vehicle": 7,
                    "steps": [
                        {"type": "job", "job": 100, "distance": None},
                    ],
                }
            ],
        }
        result = self._planner()._parse_solution(payload, stores)
        # The store with no route step is treated as unassigned.
        assert result.unassigned_store_ids == [200]
