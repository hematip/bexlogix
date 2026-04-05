# Purpose: Runtime configuration registry for BexLogix services.
# Workflow Role: Centralizes environment-driven settings for offline deployment.

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse


# Contract: _to_float executes one deterministic step in the workflow.
def _to_float(raw_value: str | None, default: float) -> float:
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


# Contract: _is_local_or_private_host executes one deterministic step in the workflow.
def _is_local_or_private_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    normalized = hostname.strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip_obj = ipaddress.ip_address(normalized)
        return bool(ip_obj.is_private or ip_obj.is_loopback)
    except ValueError:
        return False


# Contract: _offline_only_url executes one deterministic step in the workflow.
def _offline_only_url(raw_value: str | None, default: str) -> str:
    candidate = (raw_value or "").strip()
    if not candidate:
        return default
    parsed = urlparse(candidate)
    if _is_local_or_private_host(parsed.hostname):
        return candidate
    # FIX: [OFFLINE-01] Block internet hosts and fall back to local default.
    return default


# Base URL for OSRM route optimization API (offline-first default).
# Example: http://127.0.0.1:5000
OSRM_BASE_URL = _offline_only_url(os.getenv("OSRM_BASE_URL"), "http://127.0.0.1:5000")

# Timeout (seconds) for OSRM HTTP calls before fallback planner is used.
OSRM_TIMEOUT_SECONDS = _to_float(os.getenv("OSRM_TIMEOUT_SECONDS"), 2.5)

# Preferred map render engine for offline vector/raster pipelines.
# Allowed: auto | leaflet_minimal | maplibre_vector
MAP_RENDER_ENGINE = os.getenv("MAP_RENDER_ENGINE", "auto").strip().lower()
if MAP_RENDER_ENGINE not in {"auto", "leaflet_minimal", "maplibre_vector"}:
    MAP_RENDER_ENGINE = "auto"

# Local tile URL template used by the map iframe.
# Example: http://127.0.0.1:8080/styles/basic/{z}/{x}/{y}.png
MAP_TILE_URL_TEMPLATE = _offline_only_url(
    os.getenv("MAP_TILE_URL_TEMPLATE"),
    "http://127.0.0.1:8080/styles/basic/{z}/{x}/{y}.png",
)

# Attribution string for local tile providers.
MAP_TILE_ATTRIBUTION = os.getenv("MAP_TILE_ATTRIBUTION", "Local Tiles").strip()

# FIX: [PERF-01] Fail-fast probe timeout for offline runtime dependencies.
OFFLINE_HEALTH_TIMEOUT_SECONDS = _to_float(
    os.getenv("OFFLINE_HEALTH_TIMEOUT_SECONDS"),
    0.2,
)

# FIX: [PERF-01] Short-lived health cache TTL (seconds) to avoid repeated probes per rerun.
OFFLINE_HEALTH_TTL_SECONDS = _to_float(
    os.getenv("OFFLINE_HEALTH_TTL_SECONDS"),
    20.0,
)

# Local OSRM graph path used by operational checks/scripts.
OFFLINE_OSRM_GRAPH_PATH = os.getenv(
    "OFFLINE_OSRM_GRAPH_PATH",
    "offline/osrm/data/tehran-latest.osrm",
).strip()

# Local MBTiles glob pattern used by operational checks/scripts.
OFFLINE_TILES_MB_TILES_GLOB = os.getenv(
    "OFFLINE_TILES_MB_TILES_GLOB",
    "offline/tiles/data/*.mbtiles",
).strip()
