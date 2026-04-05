# Purpose: Route planning service with OSRM optimization and deterministic fallback.
# Workflow Role: Computes route order and map geometry for daily visitor assignments.

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from datetime import date
from math import asin, cos, radians, sin, sqrt
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from sqlalchemy.orm import Session

from server.app import config
from server.app.errors import DomainError, err
from server.app.repositories import assignment_repository, visitor_repository
from server.app.services import runtime_health_service


# Contract: RouteStop defines a typed boundary and should remain behavior-stable.
@dataclass
class RouteStop:
    assignment_id: int
    route_order: int
    route_distance_km: float | None


# Contract: RoutePlanner defines a typed boundary and should remain behavior-stable.
class RoutePlanner:
    # Contract: plan_route executes one deterministic step in the workflow.
    def plan_route(
        self,
        start_lat: float | None,
        start_lon: float | None,
        stops: list[dict],
    ) -> list[RouteStop]:
        raise NotImplementedError

    @property
    def last_plan_mode(self) -> str:
        # FIX: [UX-07] Expose planner mode metadata for transparency (osrm vs fallback).
        return "nn"

    @property
    def last_fallback_reason(self) -> str | None:
        return None


# Contract: _haversine_km executes one deterministic step in the workflow.
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0

    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return radius_km * c


# Contract: _build_osrm_coordinate_segment executes one deterministic step in the workflow.
def _build_osrm_coordinate_segment(points: list[tuple[float, float]]) -> str:
    coordinates = [f"{lon:.8f},{lat:.8f}" for lat, lon in points]
    coord_segment = ";".join(coordinates)
    return quote(coord_segment, safe=";,.-0123456789")


# Contract: _request_osrm_payload executes one deterministic step in the workflow.
def _request_osrm_payload(url: str, timeout_seconds: float) -> dict:
    with urlopen(url, timeout=timeout_seconds) as response:
        status_code = getattr(response, "status", None)
        if status_code is not None and int(status_code) >= 400:
            raise ValueError(f"OSRM HTTP status: {status_code}")
        return json.loads(response.read().decode("utf-8"))


# Contract: NearestNeighborRoutePlanner defines a typed boundary and should remain behavior-stable.
class NearestNeighborRoutePlanner(RoutePlanner):
    # Contract: plan_route executes one deterministic step in the workflow.
    def plan_route(
        self,
        start_lat: float | None,
        start_lon: float | None,
        stops: list[dict],
    ) -> list[RouteStop]:
        if not stops:
            return []

        if start_lat is None or start_lon is None:
            ordered_stops = sorted(stops, key=lambda stop: stop["store_code"])
            return [
                RouteStop(
                    assignment_id=stop["assignment_id"],
                    route_order=index + 1,
                    route_distance_km=None,
                )
                for index, stop in enumerate(ordered_stops)
            ]

        unvisited = stops.copy()
        current_lat = float(start_lat)
        current_lon = float(start_lon)
        cumulative_distance = 0.0
        planned: list[RouteStop] = []

        order = 1
        while unvisited:
            nearest = min(
                unvisited,
                key=lambda stop: _haversine_km(
                    current_lat,
                    current_lon,
                    float(stop["lat"]),
                    float(stop["lon"]),
                ),
            )
            step_distance = _haversine_km(
                current_lat,
                current_lon,
                float(nearest["lat"]),
                float(nearest["lon"]),
            )
            cumulative_distance += step_distance
            planned.append(
                RouteStop(
                    assignment_id=nearest["assignment_id"],
                    route_order=order,
                    route_distance_km=round(cumulative_distance, 3),
                )
            )
            current_lat = float(nearest["lat"])
            current_lon = float(nearest["lon"])
            unvisited.remove(nearest)
            order += 1

        return planned

    @property
    def last_plan_mode(self) -> str:
        return "nn"

    @property
    def last_fallback_reason(self) -> str | None:
        return "osrm_unavailable"


# Contract: OSRMRoutePlanner defines a typed boundary and should remain behavior-stable.
class OSRMRoutePlanner(RoutePlanner):
    # Contract: __init__ executes one deterministic step in the workflow.
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        fallback_planner: RoutePlanner | None = None,
        runtime_status: dict[str, object] | None = None,
    ) -> None:
        self.base_url = (base_url or config.OSRM_BASE_URL or "").strip().rstrip("/")
        self.timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(config.OSRM_TIMEOUT_SECONDS)
        )
        self.fallback_planner = fallback_planner or NearestNeighborRoutePlanner()
        self._last_plan_mode = "nn"
        self._last_fallback_reason: str | None = None
        self._runtime_status_override = dict(runtime_status) if runtime_status else None

    # Contract: _is_osrm_available executes one deterministic step in the workflow.
    def _is_osrm_available(self) -> bool:
        if self._runtime_status_override is not None:
            return bool(self._runtime_status_override.get("osrm_up", False))
        return bool(runtime_health_service.get_offline_runtime_status().get("osrm_up", False))

    # Contract: _build_trip_url executes one deterministic step in the workflow.
    def _build_trip_url(
        self,
        start_lat: float,
        start_lon: float,
        stops: list[dict],
    ) -> str:
        points = [(start_lat, start_lon)] + [
            (float(stop["lat"]), float(stop["lon"])) for stop in stops
        ]
        encoded_coords = _build_osrm_coordinate_segment(points)

        return (
            f"{self.base_url}/trip/v1/driving/{encoded_coords}"
            # FIX: [OSRM-01] destination=last is required when roundtrip=false.
            "?source=first&destination=last&roundtrip=false&overview=false&steps=false&geometries=geojson"
        )

    # Contract: _request_trip_payload executes one deterministic step in the workflow.
    def _request_trip_payload(self, url: str) -> dict:
        return _request_osrm_payload(url=url, timeout_seconds=self.timeout_seconds)

    # Contract: _to_route_stops_from_payload executes one deterministic step in the workflow.
    def _to_route_stops_from_payload(
        self,
        payload: dict,
        stops: list[dict],
    ) -> list[RouteStop]:
        if payload.get("code") != "Ok":
            raise ValueError(f"OSRM error: {payload.get('message') or payload.get('code')}")

        waypoints = payload.get("waypoints") or []
        trips = payload.get("trips") or []
        if not trips:
            raise ValueError("OSRM did not return trips.")
        if len(waypoints) != len(stops) + 1:
            raise ValueError("OSRM waypoint count mismatch.")

        optimized_order_by_stop_index: dict[int, int] = {}
        for input_index, waypoint in enumerate(waypoints):
            if input_index == 0:
                continue
            waypoint_index = waypoint.get("waypoint_index")
            if waypoint_index is None:
                raise ValueError("OSRM waypoint_index is missing.")
            optimized_order = int(waypoint_index)
            if optimized_order <= 0:
                raise ValueError("OSRM returned invalid stop order.")
            optimized_order_by_stop_index[input_index - 1] = optimized_order

        if len(optimized_order_by_stop_index) != len(stops):
            raise ValueError("OSRM did not order all route stops.")

        trip = trips[0]
        legs = trip.get("legs") or []
        if len(legs) < len(stops):
            raise ValueError("OSRM legs count is shorter than stops.")

        cumulative_km_by_order: dict[int, float] = {}
        cumulative_distance_km = 0.0
        for leg_index, leg in enumerate(legs, start=1):
            cumulative_distance_km += float(leg.get("distance") or 0.0) / 1000.0
            cumulative_km_by_order[leg_index] = round(cumulative_distance_km, 3)

        planned = [
            RouteStop(
                assignment_id=int(stops[stop_index]["assignment_id"]),
                route_order=int(route_order),
                route_distance_km=cumulative_km_by_order.get(int(route_order)),
            )
            for stop_index, route_order in optimized_order_by_stop_index.items()
        ]

        planned.sort(key=lambda item: item.route_order)
        return planned

    # Contract: plan_route executes one deterministic step in the workflow.
    def plan_route(
        self,
        start_lat: float | None,
        start_lon: float | None,
        stops: list[dict],
    ) -> list[RouteStop]:
        if not stops:
            self._last_fallback_reason = None
            return []

        if start_lat is None or start_lon is None:
            self._last_plan_mode = "nn"
            self._last_fallback_reason = "osrm_unavailable"
            return self.fallback_planner.plan_route(start_lat, start_lon, stops)
        if not self.base_url:
            self._last_plan_mode = "nn"
            self._last_fallback_reason = "osrm_unavailable"
            return self.fallback_planner.plan_route(start_lat, start_lon, stops)
        # FIX: [PERF-02] Fail-fast in offline mode when local OSRM service is unavailable.
        if not self._is_osrm_available():
            self._last_plan_mode = "nn"
            self._last_fallback_reason = "osrm_unavailable"
            return self.fallback_planner.plan_route(start_lat, start_lon, stops)

        try:
            url = self._build_trip_url(float(start_lat), float(start_lon), stops)
            payload = self._request_trip_payload(url)
            planned = self._to_route_stops_from_payload(payload, stops)
            if not planned or len(planned) != len(stops):
                raise ValueError("OSRM planning was incomplete.")
            self._last_plan_mode = "osrm"
            self._last_fallback_reason = None
            return planned
        except Exception as exc:
            self._last_plan_mode = "nn"
            self._last_fallback_reason = _map_osrm_failure_reason(exc)
            return self.fallback_planner.plan_route(start_lat, start_lon, stops)

    @property
    def last_plan_mode(self) -> str:
        return self._last_plan_mode

    @property
    def last_fallback_reason(self) -> str | None:
        return self._last_fallback_reason


# Contract: _map_osrm_failure_reason executes one deterministic step in the workflow.
def _map_osrm_failure_reason(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return "osrm_invalid_response"
    if isinstance(exc, TimeoutError):
        return "osrm_timeout"
    if isinstance(exc, socket.timeout):
        return "osrm_timeout"
    if isinstance(exc, HTTPError):
        return "osrm_invalid_response"
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError) or isinstance(reason, socket.timeout):
            return "osrm_timeout"
        if reason and "timed out" in str(reason).lower():
            return "osrm_timeout"
        return "osrm_unavailable"
    return "osrm_invalid_response"


# Contract: fetch_osrm_route_geometry executes one deterministic step in the workflow.
def _extract_route_geometry(payload: dict) -> list[list[float]]:
    if payload.get("code") != "Ok":
        return []
    routes = payload.get("routes") or []
    if not routes:
        return []
    geometry = routes[0].get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    if not coordinates:
        return []

    normalized: list[list[float]] = []
    for pair in coordinates:
        if not isinstance(pair, list) or len(pair) < 2:
            continue
        normalized.append([float(pair[0]), float(pair[1])])
    return normalized


# Contract: fetch_osrm_route_geometry executes one deterministic step in the workflow.
def fetch_osrm_route_geometry(
    start_lat: float | None,
    start_lon: float | None,
    ordered_stops: list[dict],
    base_url: str | None = None,
    timeout_seconds: float | None = None,
    runtime_status: dict[str, object] | None = None,
    allow_segment_fallback: bool = False,
) -> list[list[float]]:
    if start_lat is None or start_lon is None or not ordered_stops:
        return []

    resolved_base_url = (base_url or config.OSRM_BASE_URL or "").strip().rstrip("/")
    if not resolved_base_url:
        return []

    resolved_runtime_status = (
        dict(runtime_status) if runtime_status is not None else runtime_health_service.get_offline_runtime_status()
    )
    # FIX: [PERF-02] Do not issue any OSRM HTTP request when health circuit reports service down.
    if not bool(resolved_runtime_status.get("osrm_up", False)):
        return []

    timeout = (
        float(timeout_seconds)
        if timeout_seconds is not None
        else float(config.OSRM_TIMEOUT_SECONDS)
    )
    points = [(float(start_lat), float(start_lon))] + [
        (float(stop["lat"]), float(stop["lon"])) for stop in ordered_stops
    ]
    if len(points) < 2:
        return []

    try:
        encoded_coords = _build_osrm_coordinate_segment(points)
        url = (
            f"{resolved_base_url}/route/v1/driving/{encoded_coords}"
            "?overview=full&steps=false&geometries=geojson"
        )
        payload = _request_osrm_payload(url=url, timeout_seconds=timeout)
        geometry = _extract_route_geometry(payload)
        if len(geometry) >= 2:
            return geometry
        if not allow_segment_fallback:
            return []
    except Exception:
        if not allow_segment_fallback:
            return []

    # FIX: [PERF-02] Optional per-leg fallback is disabled by default to avoid heavy latency.
    segment_geometry: list[list[float]] = []
    for idx in range(len(points) - 1):
        leg_points = [points[idx], points[idx + 1]]
        leg_encoded = _build_osrm_coordinate_segment(leg_points)
        leg_url = (
            f"{resolved_base_url}/route/v1/driving/{leg_encoded}"
            "?overview=full&steps=false&geometries=geojson"
        )
        try:
            leg_payload = _request_osrm_payload(url=leg_url, timeout_seconds=timeout)
            leg_geometry = _extract_route_geometry(leg_payload)
        except Exception:
            leg_geometry = []
        if not leg_geometry:
            continue
        if segment_geometry and segment_geometry[-1] == leg_geometry[0]:
            segment_geometry.extend(leg_geometry[1:])
        else:
            segment_geometry.extend(leg_geometry)

    return segment_geometry


# Contract: _get_start_point executes one deterministic step in the workflow.
def _get_start_point(db: Session, work_date: date, visitor_id: int) -> tuple[float | None, float | None]:
    return visitor_repository.get_start_point_for_date(
        db=db,
        work_date=work_date,
        visitor_id=visitor_id,
    )


# Contract: apply_route_order_for_visitor executes one deterministic step in the workflow.
def apply_route_order_for_visitor(
    db: Session,
    work_date: date,
    visitor_id: int,
    planner: RoutePlanner,
) -> tuple[int, str, str | None]:
    published_exists = assignment_repository.count_published_assignments_for_visitor_date(
        db=db,
        work_date=work_date,
        visitor_id=visitor_id,
    )
    if published_exists > 0:
        raise DomainError(err("route_regen_blocked_published"))

    assignments = assignment_repository.list_draft_assignments_with_store_for_visitor_date(
        db=db,
        work_date=work_date,
        visitor_id=visitor_id,
    )
    if not assignments:
        return 0, "nn", None

    start_lat, start_lon = _get_start_point(db, work_date, visitor_id)
    stops = [
        {
            "assignment_id": assignment.id,
            "store_id": store.id,
            "store_code": store.store_code,
            "lat": store.lat,
            "lon": store.lon,
        }
        for assignment, store in assignments
    ]
    planned_stops = planner.plan_route(start_lat, start_lon, stops)
    planned_by_assignment_id = {stop.assignment_id: stop for stop in planned_stops}

    try:
        for assignment, _ in assignments:
            planned = planned_by_assignment_id.get(assignment.id)
            if not planned:
                continue
            assignment.route_order = planned.route_order
            assignment.route_distance_km = planned.route_distance_km

        db.commit()
        return (
            len(planned_stops),
            str(getattr(planner, "last_plan_mode", "nn")),
            getattr(planner, "last_fallback_reason", None),
        )
    except Exception:
        db.rollback()
        raise


# Contract: apply_routes_for_work_date executes one deterministic step in the workflow.
def apply_routes_for_work_date(db: Session, work_date: date, planner: RoutePlanner) -> dict:
    visitor_ids = assignment_repository.list_visitor_ids_with_draft_assignments(
        db=db,
        work_date=work_date,
    )

    processed_count = 0
    osrm_routed = 0
    nn_routed = 0
    fallback_reasons: dict[str, int] = {
        "osrm_unavailable": 0,
        "osrm_timeout": 0,
        "osrm_invalid_response": 0,
    }
    for visitor_id in visitor_ids:
        visitor_count, mode, fallback_reason = apply_route_order_for_visitor(
            db=db,
            work_date=work_date,
            visitor_id=visitor_id,
            planner=planner,
        )
        processed_count += visitor_count
        if mode == "osrm":
            osrm_routed += 1
        else:
            nn_routed += 1
            if fallback_reason in fallback_reasons:
                fallback_reasons[str(fallback_reason)] += 1
            elif fallback_reason:
                fallback_reasons["osrm_invalid_response"] += 1

    fallback_reason = None
    if nn_routed > 0:
        fallback_reason = max(fallback_reasons.items(), key=lambda item: item[1])[0]
        if fallback_reasons.get(fallback_reason, 0) <= 0:
            fallback_reason = "osrm_unavailable"

    return {
        "total_assignments": int(processed_count),
        "total_visitors": int(len(visitor_ids)),
        "osrm_routed": int(osrm_routed),
        "nn_routed": int(nn_routed),
        "osrm_used": bool(osrm_routed > 0),
        "fallback_reason": fallback_reason,
        "fallback_reason_counts": fallback_reasons,
    }
