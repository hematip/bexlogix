"""Capacitated geographic clustering for visitor territory assignment.

Given a list of visitors (each with a start point and a daily capacity) and a
list of due stores, partition the stores so each visitor gets a geographically
compact subset within their capacity limit. This is the preprocessing step
before per-visitor route ordering: without it, the solver minimizes total
kilometres but can produce visitor tours that sprawl across the entire city
when visitor start points are clustered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from server.app.utils.geo import haversine_km

_DEFAULT_MAX_ITERATIONS = 25
_DEFAULT_CONVERGENCE_KM = 0.1  # stop when centroids move less than 100 m


@dataclass
class _Centroid:
    visitor_id: int
    lat: float
    lon: float
    capacity: int


@dataclass
class TerritoryAssignment:
    visitor_id: int
    store_ids: list[int]
    centroid_lat: float
    centroid_lon: float
    total_capacity: int
    used_capacity: int


def _initial_centroids(visitors: Sequence[dict]) -> list[_Centroid]:
    centroids: list[_Centroid] = []
    for v in visitors:
        start_lat = v.get("start_lat")
        start_lon = v.get("start_lon")
        if start_lat is None or start_lon is None:
            # Visitor without a known start point cannot anchor a territory.
            continue
        centroids.append(
            _Centroid(
                visitor_id=int(v["visitor_id"]),
                lat=float(start_lat),
                lon=float(start_lon),
                capacity=max(0, int(v.get("capacity") or 0)),
            )
        )
    return centroids


def _assign_stores_to_centroids(
    stores: Sequence[dict],
    centroids: Sequence[_Centroid],
) -> dict[int, list[dict]]:
    """One iteration of capacitated k-means assignment.

    Stores are assigned in order of "regret" — the gap between the nearest and
    the second-nearest centroid — so that stores with strong preference for
    one cluster are seated first.
    """
    if not centroids:
        return {}

    capacity_left = {c.visitor_id: c.capacity for c in centroids}
    centroid_by_id = {c.visitor_id: c for c in centroids}

    scored: list[tuple[float, dict, list[tuple[float, int]]]] = []
    for store in stores:
        store_lat = float(store["lat"])
        store_lon = float(store["lon"])
        distances = sorted(
            (haversine_km(c.lat, c.lon, store_lat, store_lon), c.visitor_id)
            for c in centroids
        )
        # Higher regret => stronger preference for the nearest centroid.
        if len(distances) >= 2:
            regret = distances[1][0] - distances[0][0]
        else:
            regret = distances[0][0]
        scored.append((regret, store, distances))

    # Sort by regret descending, then by store id for determinism.
    scored.sort(key=lambda item: (-item[0], int(item[1]["store_id"])))

    clusters: dict[int, list[dict]] = {c.visitor_id: [] for c in centroids}
    for _regret, store, distances in scored:
        for _distance, visitor_id in distances:
            if capacity_left.get(visitor_id, 0) > 0:
                clusters[visitor_id].append(store)
                capacity_left[visitor_id] -= 1
                break
        else:
            # All centroids full — drop into the visitor whose centroid is
            # nearest regardless of capacity. The caller can decide whether
            # to over-fill or move to a deferral queue.
            nearest_visitor_id = distances[0][1]
            clusters[nearest_visitor_id].append(store)

    # Touch unused entries so caller always gets a key per visitor.
    for c in centroids:
        clusters.setdefault(c.visitor_id, [])
    return clusters


def _recompute_centroids(
    clusters: dict[int, list[dict]],
    previous: Sequence[_Centroid],
) -> list[_Centroid]:
    updated: list[_Centroid] = []
    previous_by_id = {c.visitor_id: c for c in previous}
    for c in previous:
        members = clusters.get(c.visitor_id, [])
        if not members:
            # Keep previous centroid so an empty cluster does not collapse.
            updated.append(c)
            continue
        avg_lat = sum(float(s["lat"]) for s in members) / len(members)
        avg_lon = sum(float(s["lon"]) for s in members) / len(members)
        updated.append(
            _Centroid(
                visitor_id=c.visitor_id,
                lat=avg_lat,
                lon=avg_lon,
                capacity=c.capacity,
            )
        )
    return updated


def _centroid_drift_km(
    before: Sequence[_Centroid], after: Sequence[_Centroid]
) -> float:
    before_by_id = {c.visitor_id: c for c in before}
    drift = 0.0
    for c in after:
        b = before_by_id.get(c.visitor_id)
        if b is None:
            continue
        drift = max(drift, haversine_km(b.lat, b.lon, c.lat, c.lon))
    return drift


def cluster_stores_to_visitors(
    visitors: Sequence[dict],
    stores: Sequence[dict],
    *,
    max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    convergence_km: float = _DEFAULT_CONVERGENCE_KM,
) -> list[TerritoryAssignment]:
    """Run capacitated k-means and return the final visitor → stores partition.

    `visitors` items must have keys `visitor_id`, `start_lat`, `start_lon`,
    `capacity`. `stores` items must have keys `store_id`, `lat`, `lon`.

    Visitors without a start point are excluded; their stores fall into the
    nearest centroid via the regret-based assignment step.
    """
    centroids = _initial_centroids(visitors)
    if not centroids or not stores:
        return [
            TerritoryAssignment(
                visitor_id=c.visitor_id,
                store_ids=[],
                centroid_lat=c.lat,
                centroid_lon=c.lon,
                total_capacity=c.capacity,
                used_capacity=0,
            )
            for c in centroids
        ]

    clusters: dict[int, list[dict]] = {c.visitor_id: [] for c in centroids}
    for _iteration in range(max_iterations):
        clusters = _assign_stores_to_centroids(stores, centroids)
        new_centroids = _recompute_centroids(clusters, centroids)
        drift = _centroid_drift_km(centroids, new_centroids)
        centroids = new_centroids
        if drift < convergence_km:
            break

    # Final assignment with the converged centroids.
    clusters = _assign_stores_to_centroids(stores, centroids)

    return [
        TerritoryAssignment(
            visitor_id=c.visitor_id,
            store_ids=[int(s["store_id"]) for s in clusters.get(c.visitor_id, [])],
            centroid_lat=c.lat,
            centroid_lon=c.lon,
            total_capacity=c.capacity,
            used_capacity=len(clusters.get(c.visitor_id, [])),
        )
        for c in centroids
    ]


def territory_spread_km(
    assignment: TerritoryAssignment, stores_by_id: dict[int, dict]
) -> float:
    """Maximum distance from the centroid to any assigned store. Useful as a
    KPI to compare territory tightness."""
    if not assignment.store_ids:
        return 0.0
    return max(
        haversine_km(
            assignment.centroid_lat,
            assignment.centroid_lon,
            float(stores_by_id[sid]["lat"]),
            float(stores_by_id[sid]["lon"]),
        )
        for sid in assignment.store_ids
        if sid in stores_by_id
    )
