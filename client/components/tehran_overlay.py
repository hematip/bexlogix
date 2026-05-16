"""Static Tehran geometry used as a minimal background overlay on the map.

When the local tile server is offline the Leaflet map falls back to a blank
canvas, leaving the user without any city context. We embed a small
hand-authored GeoJSON of Tehran's outer bounds plus the 22 municipal district
centroids so the route layer always renders against a recognisable backdrop.
"""

from __future__ import annotations

import json

from server.app.utils.tehran_geo import TEHRAN_DISTRICT_CENTROIDS

# A coarse hand-drawn polygon approximating Tehran's metropolitan footprint.
# Not a survey-grade boundary — its only job is to give the operator a sense
# of "this dot is inside the city" when no real basemap is available.
_TEHRAN_OUTER_BOUNDS_LATLON: list[list[float]] = [
    [35.835, 51.230],
    [35.840, 51.330],
    [35.820, 51.430],
    [35.800, 51.515],
    [35.770, 51.580],
    [35.720, 51.605],
    [35.670, 51.605],
    [35.620, 51.570],
    [35.575, 51.500],
    [35.560, 51.410],
    [35.575, 51.320],
    [35.620, 51.245],
    [35.700, 51.205],
    [35.780, 51.200],
    [35.835, 51.230],
]


def get_minimal_background_geojson() -> dict:
    """Return a FeatureCollection: the Tehran outer ring + district centroids.

    The output is Leaflet-friendly (coordinates are [lon, lat]) and is meant
    to be added as a low-opacity overlay so the route never sits on an empty
    canvas.
    """
    features: list[dict] = []

    features.append(
        {
            "type": "Feature",
            "properties": {
                "kind": "city_outline",
                "name": "تهران (تقریبی)",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [lon, lat] for lat, lon in _TEHRAN_OUTER_BOUNDS_LATLON
                ],
            },
        }
    )

    for district_id, (lat, lon) in TEHRAN_DISTRICT_CENTROIDS.items():
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "kind": "district_centroid",
                    "district_id": int(district_id),
                    "label": f"منطقه {district_id}",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def get_minimal_background_geojson_str() -> str:
    """JSON-encoded form for direct embedding into the Leaflet HTML payload."""
    return json.dumps(get_minimal_background_geojson(), ensure_ascii=False)
