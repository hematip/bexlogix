"""Geographic distance utilities."""

# Purpose: Pure geometry helpers shared across services.
# Workflow Role: Single source of truth for great-circle distance.

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_KM * c


def cumulative_path_distance_km(
    start_lat: float | None,
    start_lon: float | None,
    ordered_points: list[tuple[float, float]],
) -> list[float]:
    """Cumulative haversine distance from start through each point in order.

    Returns an empty list if start is missing.
    """
    if start_lat is None or start_lon is None or not ordered_points:
        return []

    cumulative: list[float] = []
    total = 0.0
    current_lat = float(start_lat)
    current_lon = float(start_lon)
    for lat, lon in ordered_points:
        total += haversine_km(current_lat, current_lon, float(lat), float(lon))
        cumulative.append(round(total, 3))
        current_lat = float(lat)
        current_lon = float(lon)
    return cumulative
