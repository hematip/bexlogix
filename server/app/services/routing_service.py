from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from math import asin, cos, radians, sin, sqrt
from urllib.parse import quote
from urllib.request import urlopen

from sqlalchemy.orm import Session

from server.app import config
from server.app.errors import DomainError
from server.app.repositories import assignment_repository, visitor_repository


@dataclass
class RouteStop:
    assignment_id: int
    route_order: int
    route_distance_km: float | None


class RoutePlanner:
    def plan_route(
        self,
        start_lat: float | None,
        start_lon: float | None,
        stops: list[dict],
    ) -> list[RouteStop]:
        raise NotImplementedError


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


def _build_osrm_coordinate_segment(points: list[tuple[float, float]]) -> str:
    coordinates = [f"{lon:.8f},{lat:.8f}" for lat, lon in points]
    coord_segment = ";".join(coordinates)
    return quote(coord_segment, safe=";,.-0123456789")


def _request_osrm_payload(url: str, timeout_seconds: float) -> dict:
    with urlopen(url, timeout=timeout_seconds) as response:
        status_code = getattr(response, "status", None)
        if status_code is not None and int(status_code) >= 400:
            raise ValueError(f"OSRM HTTP status: {status_code}")
        return json.loads(response.read().decode("utf-8"))


class NearestNeighborRoutePlanner(RoutePlanner):
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


class OSRMRoutePlanner(RoutePlanner):
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        fallback_planner: RoutePlanner | None = None,
    ) -> None:
        self.base_url = (base_url or config.OSRM_BASE_URL or "").strip().rstrip("/")
        self.timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(config.OSRM_TIMEOUT_SECONDS)
        )
        self.fallback_planner = fallback_planner or NearestNeighborRoutePlanner()

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
            "?source=first&roundtrip=false&overview=false&steps=false&geometries=geojson"
        )

    def _request_trip_payload(self, url: str) -> dict:
        return _request_osrm_payload(url=url, timeout_seconds=self.timeout_seconds)

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

    def plan_route(
        self,
        start_lat: float | None,
        start_lon: float | None,
        stops: list[dict],
    ) -> list[RouteStop]:
        if not stops:
            return []

        if start_lat is None or start_lon is None:
            return self.fallback_planner.plan_route(start_lat, start_lon, stops)
        if not self.base_url:
            return self.fallback_planner.plan_route(start_lat, start_lon, stops)

        try:
            url = self._build_trip_url(float(start_lat), float(start_lon), stops)
            payload = self._request_trip_payload(url)
            planned = self._to_route_stops_from_payload(payload, stops)
            if not planned or len(planned) != len(stops):
                raise ValueError("OSRM planning was incomplete.")
            return planned
        except Exception:
            return self.fallback_planner.plan_route(start_lat, start_lon, stops)


def fetch_osrm_route_geometry(
    start_lat: float | None,
    start_lon: float | None,
    ordered_stops: list[dict],
    base_url: str | None = None,
    timeout_seconds: float | None = None,
) -> list[list[float]]:
    if start_lat is None or start_lon is None or not ordered_stops:
        return []

    resolved_base_url = (base_url or config.OSRM_BASE_URL or "").strip().rstrip("/")
    if not resolved_base_url:
        return []

    try:
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

        encoded_coords = _build_osrm_coordinate_segment(points)
        url = (
            f"{resolved_base_url}/route/v1/driving/{encoded_coords}"
            "?overview=full&steps=false&geometries=geojson"
        )
        payload = _request_osrm_payload(url=url, timeout_seconds=timeout)

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
    except Exception:
        return []


def _get_start_point(db: Session, work_date: date, visitor_id: int) -> tuple[float | None, float | None]:
    return visitor_repository.get_start_point_for_date(
        db=db,
        work_date=work_date,
        visitor_id=visitor_id,
    )


def apply_route_order_for_visitor(
    db: Session,
    work_date: date,
    visitor_id: int,
    planner: RoutePlanner,
) -> int:
    published_exists = assignment_repository.count_published_assignments_for_visitor_date(
        db=db,
        work_date=work_date,
        visitor_id=visitor_id,
    )
    if published_exists > 0:
        raise DomainError(
            "Published assignments detected. MVP policy blocks route regeneration after publish."
        )

    assignments = assignment_repository.list_draft_assignments_with_store_for_visitor_date(
        db=db,
        work_date=work_date,
        visitor_id=visitor_id,
    )
    if not assignments:
        return 0

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
        return len(planned_stops)
    except Exception:
        db.rollback()
        raise


def apply_routes_for_work_date(db: Session, work_date: date, planner: RoutePlanner) -> int:
    visitor_ids = assignment_repository.list_visitor_ids_with_draft_assignments(
        db=db,
        work_date=work_date,
    )

    processed_count = 0
    for visitor_id in visitor_ids:
        processed_count += apply_route_order_for_visitor(
            db=db,
            work_date=work_date,
            visitor_id=visitor_id,
            planner=planner,
        )

    return processed_count
