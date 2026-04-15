"""
Offline routing KPI evaluation script.

Compares legacy solver (geo allocation + OSRM/NN ordering) vs VROOM for multiple work dates.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import pandas as pd
from sqlalchemy import distinct

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.services import assignment_service, routing_service, runtime_health_service
from server.db.database import get_db


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


@dataclass
class DayMetric:
    work_date: date
    due_stores: int
    legacy_assigned: int
    legacy_unassigned: int
    legacy_total_km: float
    vroom_assigned: int
    vroom_unassigned: int
    vroom_total_km: float
    vroom_status: str
    vroom_reason: str | None

    @property
    def improvement_pct(self) -> float:
        if self.legacy_total_km <= 0:
            return 0.0
        return ((self.legacy_total_km - self.vroom_total_km) / self.legacy_total_km) * 100.0


def _ordered_total_km(
    start_lat: float | None,
    start_lon: float | None,
    ordered_stops: list[dict],
) -> float:
    if not ordered_stops or start_lat is None or start_lon is None:
        return 0.0
    total = 0.0
    current_lat = float(start_lat)
    current_lon = float(start_lon)
    for stop in ordered_stops:
        lat = float(stop["lat"])
        lon = float(stop["lon"])
        total += _haversine_km(current_lat, current_lon, lat, lon)
        current_lat = lat
        current_lon = lon
    return round(total, 3)


def _legacy_metric_for_date(db, work_date: date) -> tuple[int, int, float]:
    visitors = assignment_service.get_active_visitor_day_contexts(db, work_date)
    due_stores = assignment_service._get_due_stores_sorted(db, work_date)  # noqa: SLF001
    allocations = assignment_service._geo_capacity_allocate_stores(  # noqa: SLF001
        visitors=visitors,
        due_stores=due_stores,
    )

    runtime_status = runtime_health_service.get_offline_runtime_status(force_refresh=True)
    planner = routing_service.OSRMRoutePlanner(
        fallback_planner=routing_service.NearestNeighborRoutePlanner(),
        runtime_status=runtime_status,
    )

    total_km = 0.0
    assigned_count = 0
    for visitor in visitors:
        visitor_id = int(visitor["visitor_id"])
        store_list = allocations.get(visitor_id, [])
        if not store_list:
            continue
        assigned_count += len(store_list)
        stops = [
            {
                "assignment_id": idx + 1,
                "store_code": str(store.store_code),
                "lat": float(store.lat),
                "lon": float(store.lon),
            }
            for idx, store in enumerate(store_list)
        ]
        planned = planner.plan_route(
            start_lat=visitor.get("start_lat"),
            start_lon=visitor.get("start_lon"),
            stops=stops,
        )
        by_assignment_id = {item.assignment_id: item for item in planned}
        ordered_stops = sorted(
            stops,
            key=lambda row: by_assignment_id.get(
                int(row["assignment_id"]),
                routing_service.RouteStop(
                    assignment_id=0,
                    route_order=10**9,
                    route_distance_km=None,
                ),
            ).route_order,
        )
        total_km += _ordered_total_km(
            start_lat=visitor.get("start_lat"),
            start_lon=visitor.get("start_lon"),
            ordered_stops=ordered_stops,
        )

    due_count = len(due_stores)
    return assigned_count, max(0, due_count - assigned_count), round(total_km, 3)


def _vroom_metric_for_date(db, work_date: date) -> tuple[int, int, float, str, str | None]:
    visitors = assignment_service.get_active_visitor_day_contexts(db, work_date)
    due_stores = assignment_service._get_due_stores_sorted(db, work_date)  # noqa: SLF001
    solver_store_rows = [
        {
            "store_id": int(store.id),
            "store_code": str(store.store_code),
            "lat": float(store.lat),
            "lon": float(store.lon),
        }
        for store in due_stores
    ]
    visitor_by_id = {int(v["visitor_id"]): v for v in visitors}
    store_by_id = {int(row["store_id"]): row for row in solver_store_rows}

    result = routing_service.solve_day_assignments_with_vroom(
        visitors=visitors,
        stores=solver_store_rows,
    )
    if result.solver_mode != "vroom":
        return 0, len(due_stores), 0.0, "failed", result.solver_reason

    assignments = sorted(
        result.assignments,
        key=lambda item: (item.visitor_id, item.route_order, item.store_id),
    )
    assigned_ids = {int(item.store_id) for item in assignments}
    unassigned_ids = set(int(item) for item in result.unassigned_store_ids)
    unassigned_ids.update(set(store_by_id.keys()) - assigned_ids)

    total_km = 0.0
    grouped: dict[int, list[routing_service.PlannedAssignment]] = {}
    for item in assignments:
        grouped.setdefault(int(item.visitor_id), []).append(item)

    for visitor_id, rows in grouped.items():
        visitor = visitor_by_id.get(visitor_id)
        if not visitor:
            continue
        ordered_stops = []
        for row in rows:
            stop = store_by_id.get(int(row.store_id))
            if stop:
                ordered_stops.append(stop)
        total_km += _ordered_total_km(
            start_lat=visitor.get("start_lat"),
            start_lon=visitor.get("start_lon"),
            ordered_stops=ordered_stops,
        )

    return (
        len(assigned_ids),
        len(unassigned_ids),
        round(total_km, 3),
        "ok",
        None,
    )


def _collect_dates(db, explicit_dates: list[str] | None) -> list[date]:
    if explicit_dates:
        return [date.fromisoformat(item) for item in explicit_dates]
    rows = (
        db.query(distinct(DailyVisitorStatus.work_date))
        .order_by(DailyVisitorStatus.work_date.asc())
        .all()
    )
    return [row[0] for row in rows if row[0] is not None]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate offline routing KPI for VROOM rollout.")
    parser.add_argument(
        "--work-date",
        action="append",
        dest="work_dates",
        help="Specific work_date (YYYY-MM-DD). Repeat for multiple dates.",
    )
    parser.add_argument(
        "--min-days",
        type=int,
        default=20,
        help="Minimum number of days required for strict KPI decision.",
    )
    args = parser.parse_args()

    with get_db() as db:
        dates = _collect_dates(db=db, explicit_dates=args.work_dates)
        if not dates:
            print("No work dates found for KPI evaluation.")
            return 1

        metrics: list[DayMetric] = []
        for work_date in dates:
            due_stores = len(assignment_service._get_due_stores_sorted(db, work_date))  # noqa: SLF001
            legacy_assigned, legacy_unassigned, legacy_total_km = _legacy_metric_for_date(
                db, work_date
            )
            (
                vroom_assigned,
                vroom_unassigned,
                vroom_total_km,
                vroom_status,
                vroom_reason,
            ) = _vroom_metric_for_date(db, work_date)
            metrics.append(
                DayMetric(
                    work_date=work_date,
                    due_stores=due_stores,
                    legacy_assigned=legacy_assigned,
                    legacy_unassigned=legacy_unassigned,
                    legacy_total_km=legacy_total_km,
                    vroom_assigned=vroom_assigned,
                    vroom_unassigned=vroom_unassigned,
                    vroom_total_km=vroom_total_km,
                    vroom_status=vroom_status,
                    vroom_reason=vroom_reason,
                )
            )

    df = pd.DataFrame(
        [
            {
                "work_date": item.work_date.isoformat(),
                "due_stores": item.due_stores,
                "legacy_unassigned": item.legacy_unassigned,
                "vroom_unassigned": item.vroom_unassigned,
                "legacy_total_km": item.legacy_total_km,
                "vroom_total_km": item.vroom_total_km,
                "improvement_pct": round(item.improvement_pct, 2),
                "vroom_status": item.vroom_status,
                "vroom_reason": item.vroom_reason,
            }
            for item in metrics
        ]
    )
    print(df.to_string(index=False))

    total_days = len(df)
    if total_days < max(1, int(args.min_days)):
        print(f"\nKPI FAIL: only {total_days} day(s) available, minimum required is {args.min_days}.")
        return 1

    if (df["vroom_status"] != "ok").any():
        failed = int((df["vroom_status"] != "ok").sum())
        print(f"\nKPI FAIL: VROOM failed on {failed} day(s).")
        return 1

    if (df["vroom_unassigned"] > df["legacy_unassigned"]).any():
        print("\nKPI FAIL: vroom_unassigned exceeded legacy_unassigned on at least one day.")
        return 1

    km_guard = df["vroom_total_km"] <= (df["legacy_total_km"] * 1.01)
    if not bool(km_guard.all()):
        print("\nKPI FAIL: vroom_total_km was worse than +1% guardrail on at least one day.")
        return 1

    median_improvement = float(df["improvement_pct"].median())
    p90_improvement = float(df["improvement_pct"].quantile(0.90))
    print(
        "\nSummary: "
        f"median_improvement={median_improvement:.2f}% | "
        f"p90_improvement={p90_improvement:.2f}% | "
        f"days={total_days}"
    )

    if median_improvement < 12.0:
        print("KPI FAIL: median improvement is below 12%.")
        return 1
    if p90_improvement < 5.0:
        print("KPI FAIL: p90 improvement is below 5%.")
        return 1

    print("KPI PASS: all routing quality gates satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
