# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

import pytest

from server.app.services import routing_service


# Contract: _build_sample_stops executes one deterministic step in the workflow.
def _build_sample_stops() -> list[dict]:
    return [
        {"assignment_id": 101, "store_code": "STR-A", "lat": 35.701, "lon": 51.401},
        {"assignment_id": 102, "store_code": "STR-B", "lat": 35.711, "lon": 51.411},
        {"assignment_id": 103, "store_code": "STR-C", "lat": 35.721, "lon": 51.421},
    ]


# Contract: test_osrm_success executes one deterministic step in the workflow.
@pytest.mark.unit
def test_osrm_success() -> None:
    planner = routing_service.OSRMRoutePlanner(
        base_url="https://mock.osrm.local",
        fallback_planner=routing_service.NearestNeighborRoutePlanner(),
    )

    # Contract: fake_request_payload executes one deterministic step in the workflow.
    def fake_request_payload(_: str) -> dict:
        return {
            "code": "Ok",
            "waypoints": [
                {"waypoint_index": 0},
                {"waypoint_index": 2},  # stop A
                {"waypoint_index": 1},  # stop B
                {"waypoint_index": 3},  # stop C
            ],
            "trips": [
                {
                    "legs": [
                        {"distance": 1200},
                        {"distance": 800},
                        {"distance": 1500},
                    ]
                }
            ],
        }

    planner._request_trip_payload = fake_request_payload  # type: ignore[attr-defined]

    planned = planner.plan_route(
        start_lat=35.690,
        start_lon=51.390,
        stops=_build_sample_stops(),
    )

    assert len(planned) == 3
    by_assignment = {item.assignment_id: item for item in planned}
    assert by_assignment[102].route_order == 1
    assert by_assignment[102].route_distance_km == 1.2
    assert by_assignment[101].route_order == 2
    assert by_assignment[101].route_distance_km == 2.0
    assert by_assignment[103].route_order == 3
    assert by_assignment[103].route_distance_km == 3.5


# Contract: test_osrm_fallback executes one deterministic step in the workflow.
@pytest.mark.unit
def test_osrm_fallback() -> None:
    planner = routing_service.OSRMRoutePlanner(
        base_url="https://mock.osrm.local",
        fallback_planner=routing_service.NearestNeighborRoutePlanner(),
    )

    # Contract: fake_raise executes one deterministic step in the workflow.
    def fake_raise(_: str) -> dict:
        raise TimeoutError("Simulated OSRM timeout")

    planner._request_trip_payload = fake_raise  # type: ignore[attr-defined]

    planned = planner.plan_route(
        start_lat=35.690,
        start_lon=51.390,
        stops=_build_sample_stops(),
    )

    assert len(planned) == 3
    route_orders = sorted(item.route_order for item in planned)
    assert route_orders == [1, 2, 3]
    assert all(item.route_distance_km is not None for item in planned)


# Contract: test_route_geometry_success executes one deterministic step in the workflow.
@pytest.mark.unit
def test_route_geometry_success() -> None:
    original_request = routing_service._request_osrm_payload

    # Contract: fake_request executes one deterministic step in the workflow.
    def fake_request(url: str, timeout_seconds: float) -> dict:
        del url, timeout_seconds
        return {
            "code": "Ok",
            "routes": [
                {
                    "geometry": {
                        "coordinates": [
                            [51.390, 35.690],
                            [51.395, 35.695],
                            [51.401, 35.701],
                        ]
                    }
                }
            ],
        }

    try:
        routing_service._request_osrm_payload = fake_request  # type: ignore[assignment]
        geometry = routing_service.fetch_osrm_route_geometry(
            start_lat=35.690,
            start_lon=51.390,
            ordered_stops=[{"lat": 35.701, "lon": 51.401}],
            base_url="https://mock.osrm.local",
        )
    finally:
        routing_service._request_osrm_payload = original_request  # type: ignore[assignment]

    assert geometry == [[51.39, 35.69], [51.395, 35.695], [51.401, 35.701]]


# Contract: test_route_geometry_failure_returns_empty executes one deterministic step in the workflow.
@pytest.mark.unit
def test_route_geometry_failure_returns_empty() -> None:
    original_request = routing_service._request_osrm_payload

    # Contract: fake_raise executes one deterministic step in the workflow.
    def fake_raise(url: str, timeout_seconds: float) -> dict:
        del url, timeout_seconds
        raise TimeoutError("Simulated timeout")

    try:
        routing_service._request_osrm_payload = fake_raise  # type: ignore[assignment]
        geometry = routing_service.fetch_osrm_route_geometry(
            start_lat=35.690,
            start_lon=51.390,
            ordered_stops=[{"lat": 35.701, "lon": 51.401}],
            base_url="https://mock.osrm.local",
        )
    finally:
        routing_service._request_osrm_payload = original_request  # type: ignore[assignment]

    assert geometry == []
