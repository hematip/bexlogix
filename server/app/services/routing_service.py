from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import asin, cos, radians, sin, sqrt

from sqlalchemy.orm import Session

from server.app.enums.assignment_status import AssignmentStatus
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.store import Store
from server.app.models.visitor_profile import VisitorProfile


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


def _get_start_point(db: Session, work_date: date, visitor_id: int) -> tuple[float | None, float | None]:
    daily_row = (
        db.query(DailyVisitorStatus)
        .filter(
            DailyVisitorStatus.visitor_id == visitor_id,
            DailyVisitorStatus.work_date == work_date,
        )
        .first()
    )
    if daily_row:
        if daily_row.start_lat is not None and daily_row.start_lon is not None:
            return float(daily_row.start_lat), float(daily_row.start_lon)

    profile = db.query(VisitorProfile).filter(VisitorProfile.id == visitor_id).first()
    if not profile:
        return None, None
    if profile.default_start_lat is None or profile.default_start_lon is None:
        return None, None

    return float(profile.default_start_lat), float(profile.default_start_lon)


def apply_route_order_for_visitor(
    db: Session,
    work_date: date,
    visitor_id: int,
    planner: RoutePlanner,
) -> int:
    published_exists = (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.visitor_id == visitor_id,
            DailyAssignment.assignment_status == AssignmentStatus.PUBLISHED.value,
        )
        .count()
    )
    if published_exists > 0:
        raise ValueError(
            "Published assignments detected. MVP policy blocks route regeneration after publish."
        )

    assignments = (
        db.query(DailyAssignment, Store)
        .join(Store, Store.id == DailyAssignment.store_id)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.visitor_id == visitor_id,
            DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
        )
        .all()
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
    visitor_rows = (
        db.query(DailyAssignment.visitor_id)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
        )
        .distinct()
        .all()
    )
    visitor_ids = [visitor_id for (visitor_id,) in visitor_rows]

    processed_count = 0
    for visitor_id in visitor_ids:
        processed_count += apply_route_order_for_visitor(
            db=db,
            work_date=work_date,
            visitor_id=visitor_id,
            planner=planner,
        )

    return processed_count
