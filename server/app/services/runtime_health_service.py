# Purpose: Runtime health diagnostics for offline map and routing dependencies.
# Workflow Role: Provides cached, semantic service status for OSRM and local tile runtime.

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from glob import glob
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from server.app import config

_CACHE_LOCK = threading.Lock()
_CACHE_EXPIRES_AT = 0.0
_CACHED_STATUS: dict[str, object] = {}
_VECTOR_BASEMAP_LAYER_IDS = {"land", "water_polygons", "streets", "street_polygons"}


# Contract: _now_iso executes one deterministic step in the workflow.
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Contract: _probe_tile_url executes one deterministic step in the workflow.
def _probe_tile_url(template: str) -> str:
    return (
        str(template or "")
        .replace("{z}", "10")
        .replace("{x}", "532")
        .replace("{y}", "386")
        .strip()
    )


# Contract: _safe_latency_ms executes one deterministic step in the workflow.
def _safe_latency_ms(start: float) -> int:
    return max(0, int((time.perf_counter() - start) * 1000))


# Contract: _probe_raster_template validates a raster tile template by checking a sample tile response.
def _probe_raster_template(
    template: str,
    timeout_seconds: float,
) -> tuple[bool, int | None, str | None]:
    tile_url = _probe_tile_url(template)
    if not tile_url:
        return False, None, "tiles_unavailable"

    started = time.perf_counter()
    try:
        with urlopen(tile_url, timeout=timeout_seconds) as response:
            content_type = str(response.headers.get("content-type", "")).lower()
            latency = _safe_latency_ms(started)
            if "image/" in content_type:
                return True, latency, None
            return False, latency, "tiles_invalid_response"
    except HTTPError:
        return False, _safe_latency_ms(started), "tiles_unavailable"
    except URLError as exc:
        reason_text = str(getattr(exc, "reason", "") or "").lower()
        if "timed out" in reason_text:
            return False, _safe_latency_ms(started), "tiles_timeout"
        return False, _safe_latency_ms(started), "tiles_unavailable"
    except TimeoutError:
        return False, _safe_latency_ms(started), "tiles_timeout"
    except Exception:
        return False, _safe_latency_ms(started), "tiles_invalid_response"


# Contract: _probe_public_raster_fallback checks optional public raster basemap availability.
def _probe_public_raster_fallback(
    timeout_seconds: float,
) -> tuple[bool, int | None, str | None, str]:
    template = str(config.MAP_PUBLIC_RASTER_FALLBACK_URL or "").strip()
    if not template:
        return False, None, "public_raster_not_configured", ""

    ok, latency, error = _probe_raster_template(template, timeout_seconds)
    return ok, latency, error, template


# Contract: _tile_service_base resolves tile-service base for style/vector health probes.
def _tile_service_base() -> str:
    template = str(config.MAP_TILE_URL_TEMPLATE or "").strip()
    if template:
        parsed = urlparse(template)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    # FIX: Use dedicated tile-service base when raster template is intentionally empty
    # (vector auto-discovery mode).
    service_base = str(config.MAP_TILE_SERVICE_BASE or "").strip()
    if not service_base:
        return ""
    parsed = urlparse(service_base)
    if not parsed.scheme or not parsed.netloc:
        return ""
    base_path = str(parsed.path or "").rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{base_path}"


# Contract: _extract_style_ids extracts style IDs from /styles.json variants.
def _extract_style_ids(payload: object) -> list[str]:
    ids: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str) and item.strip():
                ids.append(item.strip())
            elif isinstance(item, dict):
                style_id = str(item.get("id") or item.get("name") or "").strip()
                if style_id:
                    ids.append(style_id)
    elif isinstance(payload, dict):
        styles = payload.get("styles")
        if styles is not None:
            ids.extend(_extract_style_ids(styles))
    # Preserve order and uniqueness.
    seen: set[str] = set()
    ordered: list[str] = []
    for style_id in ids:
        if style_id in seen:
            continue
        seen.add(style_id)
        ordered.append(style_id)
    return ordered


# Contract: _normalize_remote_template resolves absolute URL templates from data.json payloads.
def _normalize_remote_template(base_url: str, template: str | None) -> str:
    candidate = str(template or "").strip()
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme and parsed.netloc:
        return candidate
    base = str(base_url or "").rstrip("/")
    if not base:
        return candidate
    return f"{base}/{candidate.lstrip('/')}"


# Contract: _extract_vector_sources parses vector dataset entries from /data.json payload.
def _extract_vector_sources(payload: object) -> list[dict[str, object]]:
    raw_items: list[dict] = []
    if isinstance(payload, list):
        raw_items = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        data_items = payload.get("data")
        if data_items is not None:
            return _extract_vector_sources(data_items)
        if isinstance(payload.get("tiles"), list):
            raw_items = [payload]

    parsed_items: list[dict[str, object]] = []
    for item in raw_items:
        raw_tiles = item.get("tiles")
        if not isinstance(raw_tiles, list):
            continue

        tile_template = ""
        for raw_tile in raw_tiles:
            tile_text = str(raw_tile or "").strip()
            if tile_text:
                tile_template = tile_text
                break
        if not tile_template:
            continue

        layer_ids: list[str] = []
        raw_vector_layers = item.get("vector_layers")
        if isinstance(raw_vector_layers, list):
            for layer in raw_vector_layers:
                if not isinstance(layer, dict):
                    continue
                layer_id = str(layer.get("id") or "").strip()
                if layer_id:
                    layer_ids.append(layer_id)

        bounds: list[float] | None = None
        raw_bounds = item.get("bounds")
        if isinstance(raw_bounds, (list, tuple)) and len(raw_bounds) == 4:
            try:
                bounds = [
                    float(raw_bounds[0]),
                    float(raw_bounds[1]),
                    float(raw_bounds[2]),
                    float(raw_bounds[3]),
                ]
            except (TypeError, ValueError):
                bounds = None

        parsed_items.append(
            {
                "dataset_id": str(item.get("id") or item.get("name") or "").strip(),
                "template": tile_template,
                "layer_ids": layer_ids,
                "bounds": bounds,
            }
        )
    return parsed_items


# Contract: _select_vector_source chooses one dataset from vector candidates.
def _select_vector_source(
    vector_sources: list[dict[str, object]],
) -> dict[str, object] | None:
    if not vector_sources:
        return None

    preferred_dataset = str(config.MAP_VECTOR_DATASET_ID or "").strip().lower()
    if preferred_dataset:
        for source in vector_sources:
            source_id = str(source.get("dataset_id") or "").strip().lower()
            if source_id == preferred_dataset:
                return source

    return vector_sources[0]


# Contract: _discover_tile_template tries to resolve a valid local style path automatically.
def _discover_tile_template(timeout_seconds: float) -> list[str]:
    base = _tile_service_base()
    if not base:
        return []
    styles_url = f"{base}/styles.json"
    try:
        with urlopen(styles_url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    style_ids = _extract_style_ids(payload)
    return [f"{base}/styles/{style_id}/{{z}}/{{x}}/{{y}}.png" for style_id in style_ids]


# Contract: _extract_vector_tile_template extracts first vector tile template from data.json payload.
def _extract_vector_tile_template(payload: object) -> str | None:
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            tiles = item.get("tiles")
            if isinstance(tiles, list):
                for tile in tiles:
                    tile_text = str(tile or "").strip()
                    if tile_text:
                        return tile_text
    if isinstance(payload, dict):
        data_items = payload.get("data")
        if data_items is not None:
            return _extract_vector_tile_template(data_items)
    return None


# Contract: _extract_vector_layer_ids extracts available source-layer IDs from vector tiles metadata.
def _extract_vector_layer_ids(payload: object) -> list[str]:
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            vector_layers = item.get("vector_layers")
            if isinstance(vector_layers, list):
                layer_ids: list[str] = []
                for layer in vector_layers:
                    if not isinstance(layer, dict):
                        continue
                    layer_id = str(layer.get("id") or "").strip()
                    if layer_id:
                        layer_ids.append(layer_id)
                if layer_ids:
                    return layer_ids
    if isinstance(payload, dict):
        data_items = payload.get("data")
        if data_items is not None:
            return _extract_vector_layer_ids(data_items)
    return []


# Contract: _probe_vector_tiles tries vector tiles when raster styles are unavailable.
def _probe_vector_tiles(
    timeout_seconds: float,
) -> tuple[
    bool,
    int | None,
    str | None,
    str | None,
    list[str],
    str | None,
    list[float] | None,
]:
    base = _tile_service_base()
    if not base:
        return False, None, "tiles_unavailable", None, [], None, None

    data_url = f"{base}/data.json"
    started = time.perf_counter()
    try:
        with urlopen(data_url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
            vector_sources = _extract_vector_sources(payload)
            selected_source = _select_vector_source(vector_sources)
            latency = _safe_latency_ms(started)

            if not selected_source:
                return False, latency, "tiles_unavailable", None, [], None, None

            vector_template = _normalize_remote_template(
                base,
                str(selected_source.get("template") or "").strip(),
            )
            vector_layer_ids = [
                str(layer_id).strip()
                for layer_id in (selected_source.get("layer_ids") or [])
                if str(layer_id).strip()
            ]
            vector_dataset_id = str(selected_source.get("dataset_id") or "").strip() or None
            vector_bounds = selected_source.get("bounds")
            if not isinstance(vector_bounds, list) or len(vector_bounds) != 4:
                vector_bounds = None

            if not vector_template:
                return (
                    False,
                    latency,
                    "tiles_unavailable",
                    None,
                    vector_layer_ids,
                    vector_dataset_id,
                    vector_bounds,
                )

            tile_url = _probe_tile_url(vector_template)
            with urlopen(tile_url, timeout=timeout_seconds) as tile_response:
                status_code = int(getattr(tile_response, "status", 200) or 200)
                content_type = str(tile_response.headers.get("content-type", "")).lower()
                # 204 is valid for an empty vector tile response in sparse zoom/cell combinations.
                if status_code in (200, 204) and (
                    ("application/x-protobuf" in content_type)
                    or ("application/vnd.mapbox-vector-tile" in content_type)
                    or ("application/octet-stream" in content_type)
                    or (status_code == 204)
                ):
                    return (
                        True,
                        latency,
                        None,
                        vector_template,
                        vector_layer_ids,
                        vector_dataset_id,
                        vector_bounds,
                    )
            return (
                False,
                latency,
                "tiles_invalid_response",
                vector_template,
                vector_layer_ids,
                vector_dataset_id,
                vector_bounds,
            )
    except HTTPError:
        return False, _safe_latency_ms(started), "tiles_unavailable", None, [], None, None
    except URLError as exc:
        reason_text = str(getattr(exc, "reason", "") or "").lower()
        if "timed out" in reason_text:
            return False, _safe_latency_ms(started), "tiles_timeout", None, [], None, None
        return False, _safe_latency_ms(started), "tiles_unavailable", None, [], None, None
    except TimeoutError:
        return False, _safe_latency_ms(started), "tiles_timeout", None, [], None, None
    except Exception:
        return False, _safe_latency_ms(started), "tiles_invalid_response", None, [], None, None


# Contract: _probe_font_catalog checks whether tile server exposes glyph fonts for symbol layers.
def _probe_font_catalog(timeout_seconds: float) -> bool:
    base = _tile_service_base()
    if not base:
        return False
    fonts_url = f"{base}/fonts.json"
    try:
        with urlopen(fonts_url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, list):
                return len(payload) > 0
            if isinstance(payload, dict):
                fonts = payload.get("fonts")
                if isinstance(fonts, list):
                    return len(fonts) > 0
            return False
    except Exception:
        return False


# Contract: _probe_osrm executes one deterministic step in the workflow.
def _probe_osrm(timeout_seconds: float) -> tuple[bool, int | None, str | None]:
    probe_url = f"{str(config.OSRM_BASE_URL).rstrip('/')}/nearest/v1/driving/51.3890,35.6892?number=1"
    attempts = 2
    last_latency: int | None = None
    last_error = "osrm_unavailable"
    for _ in range(attempts):
        started = time.perf_counter()
        try:
            with urlopen(probe_url, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                latency = _safe_latency_ms(started)
                if payload.get("code") == "Ok":
                    return True, latency, None
                last_latency = latency
                last_error = "osrm_invalid_response"
        except HTTPError:
            last_latency = _safe_latency_ms(started)
            last_error = "osrm_invalid_response"
        except URLError as exc:
            last_latency = _safe_latency_ms(started)
            reason_text = str(getattr(exc, "reason", "") or "").lower()
            if "timed out" in reason_text:
                last_error = "osrm_timeout"
            else:
                last_error = "osrm_unavailable"
        except TimeoutError:
            last_latency = _safe_latency_ms(started)
            last_error = "osrm_timeout"
        except Exception:
            last_latency = _safe_latency_ms(started)
            last_error = "osrm_invalid_response"
        time.sleep(0.05)
    return False, last_latency, last_error


# Contract: _probe_tiles executes one deterministic step in the workflow.
def _probe_tiles(
    timeout_seconds: float,
) -> tuple[
    bool,
    int | None,
    str | None,
    str | None,
    str,
    str | None,
    bool,
    list[str],
    str | None,
    list[float] | None,
    bool,
]:
    configured_template = str(config.MAP_TILE_URL_TEMPLATE or "").strip()
    discovered_templates = _discover_tile_template(timeout_seconds)
    candidates: list[str] = []
    if configured_template:
        candidates.append(configured_template)
    for discovered_template in discovered_templates:
        if discovered_template not in candidates:
            candidates.append(discovered_template)
    if not candidates:
        (
            vector_ok,
            vector_latency,
            vector_error,
            vector_template,
            vector_layer_ids,
            vector_dataset_id,
            vector_bounds,
        ) = _probe_vector_tiles(timeout_seconds)
        if vector_ok:
            fonts_available = _probe_font_catalog(timeout_seconds)
            # Prefer readable raster basemap (street names) when vector fonts are unavailable.
            if not fonts_available:
                public_ok, public_latency, _, public_template = _probe_public_raster_fallback(
                    timeout_seconds
                )
                if public_ok:
                    resolved_latency = (
                        public_latency if public_latency is not None else vector_latency
                    )
                    return (
                        True,
                        resolved_latency,
                        None,
                        public_template,
                        "raster",
                        vector_template,
                        False,
                        vector_layer_ids,
                        vector_dataset_id,
                        vector_bounds,
                        True,
                    )

            return (
                True,
                vector_latency,
                None,
                "",
                "vector",
                vector_template,
                fonts_available,
                vector_layer_ids,
                vector_dataset_id,
                vector_bounds,
                False,
            )
        return (
            False,
            vector_latency,
            vector_error,
            "",
            "none",
            vector_template,
            False,
            vector_layer_ids,
            vector_dataset_id,
            vector_bounds,
            False,
        )

    last_latency: int | None = None
    last_error = "tiles_unavailable"
    for candidate in candidates:
        tile_url = _probe_tile_url(candidate)
        if not tile_url:
            continue
        started = time.perf_counter()
        try:
            with urlopen(tile_url, timeout=timeout_seconds) as response:
                content_type = str(response.headers.get("content-type", "")).lower()
                latency = _safe_latency_ms(started)
                if "image/" in content_type:
                    return (
                        True,
                        latency,
                        None,
                        candidate,
                        "raster",
                        None,
                        _probe_font_catalog(timeout_seconds),
                        [],
                        None,
                        None,
                        False,
                    )
                last_latency = latency
                last_error = "tiles_invalid_response"
        except HTTPError:
            last_latency = _safe_latency_ms(started)
            last_error = "tiles_unavailable"
        except URLError:
            last_latency = _safe_latency_ms(started)
            last_error = "tiles_unavailable"
        except TimeoutError:
            last_latency = _safe_latency_ms(started)
            last_error = "tiles_timeout"
        except Exception:
            last_latency = _safe_latency_ms(started)
            last_error = "tiles_invalid_response"

    (
        vector_ok,
        vector_latency,
        vector_error,
        vector_template,
        vector_layer_ids,
        vector_dataset_id,
        vector_bounds,
    ) = _probe_vector_tiles(timeout_seconds)
    if vector_ok:
        fonts_available = _probe_font_catalog(timeout_seconds)
        # Prefer readable raster basemap (street names) when vector fonts are unavailable.
        if not fonts_available:
            public_ok, public_latency, _, public_template = _probe_public_raster_fallback(
                timeout_seconds
            )
            if public_ok:
                resolved_latency = (
                    public_latency if public_latency is not None else vector_latency
                )
                return (
                    True,
                    resolved_latency,
                    None,
                    public_template,
                    "raster",
                    vector_template,
                    False,
                    vector_layer_ids,
                    vector_dataset_id,
                    vector_bounds,
                    True,
                )

        resolved_latency = vector_latency if vector_latency is not None else last_latency
        return (
            True,
            resolved_latency,
            None,
            candidates[0],
            "vector",
            vector_template,
            fonts_available,
            vector_layer_ids,
            vector_dataset_id,
            vector_bounds,
            False,
        )

    if vector_latency is not None:
        last_latency = vector_latency
    if vector_error is not None:
        last_error = vector_error
    public_ok, public_latency, public_error, public_template = _probe_public_raster_fallback(
        timeout_seconds
    )
    if public_ok:
        resolved_latency = public_latency if public_latency is not None else last_latency
        return (
            True,
            resolved_latency,
            None,
            public_template,
            "raster",
            vector_template,
            False,
            vector_layer_ids,
            vector_dataset_id,
            vector_bounds,
            True,
        )

    resolved_error = last_error
    if public_error and public_error != "public_raster_not_configured":
        resolved_error = f"{last_error}|{public_error}"

    return (
        False,
        last_latency,
        resolved_error,
        candidates[0],
        "none",
        vector_template,
        False,
        vector_layer_ids,
        vector_dataset_id,
        vector_bounds,
        False,
    )


# Contract: _resolve_render_engine selects map render mode for predictable offline behavior.
def _resolve_render_engine(
    tile_mode: str,
    vector_ready: bool,
    vector_style_ready: bool,
) -> str:
    preferred = str(config.MAP_RENDER_ENGINE or "auto").strip().lower()
    if preferred == "leaflet_minimal":
        return "leaflet_minimal"
    if preferred == "maplibre_vector":
        if tile_mode == "raster":
            return "leaflet_raster"
        return "maplibre_vector" if vector_ready and vector_style_ready else "leaflet_minimal"

    if tile_mode == "vector":
        return "maplibre_vector" if vector_ready and vector_style_ready else "leaflet_minimal"
    if tile_mode == "raster":
        return "leaflet_raster"
    return "leaflet_minimal"


# Contract: _is_osrm_data_ready executes one deterministic step in the workflow.
def _is_osrm_data_ready() -> bool:
    return Path(str(config.OFFLINE_OSRM_GRAPH_PATH)).exists()


# Contract: _is_tiles_data_ready executes one deterministic step in the workflow.
def _is_tiles_data_ready() -> bool:
    pattern = str(config.OFFLINE_TILES_MB_TILES_GLOB or "").strip()
    if not pattern:
        return False
    return len(glob(pattern)) > 0


# Contract: _resolve_overall_state executes one deterministic step in the workflow.
def _resolve_overall_state(osrm_up: bool, tiles_up: bool) -> str:
    if osrm_up and tiles_up:
        return "UP"
    if osrm_up or tiles_up:
        return "DEGRADED"
    return "DOWN"


# Contract: _probe_runtime_status executes one deterministic step in the workflow.
def _probe_runtime_status() -> dict[str, object]:
    timeout_seconds = float(config.OFFLINE_HEALTH_TIMEOUT_SECONDS)
    osrm_data_ready = _is_osrm_data_ready()
    tiles_data_ready = _is_tiles_data_ready()

    # FIX: [PERF-01] Skip network probes when required local data files are absent.
    if osrm_data_ready:
        osrm_up, osrm_latency_ms, osrm_error = _probe_osrm(timeout_seconds)
    else:
        osrm_up, osrm_latency_ms, osrm_error = False, None, "osrm_data_missing"

    if tiles_data_ready:
        (
            tiles_up,
            tiles_latency_ms,
            tiles_error,
            resolved_tile_template,
            tile_mode,
            vector_tile_template,
            fonts_available,
            vector_layers_available,
            vector_dataset_id,
            vector_bounds,
            using_public_raster_fallback,
        ) = _probe_tiles(timeout_seconds)
    else:
        (
            tiles_up,
            tiles_latency_ms,
            tiles_error,
            resolved_tile_template,
            tile_mode,
            vector_tile_template,
            fonts_available,
            vector_layers_available,
            vector_dataset_id,
            vector_bounds,
            using_public_raster_fallback,
        ) = (
            False,
            None,
            "tiles_data_missing",
            None,
            "none",
            None,
            False,
            [],
            None,
            None,
            False,
        )

    vector_ready = bool(tiles_up and tile_mode == "vector" and vector_tile_template)
    layer_set = {str(layer).strip() for layer in vector_layers_available if str(layer).strip()}
    vector_style_ready = bool(vector_ready and (layer_set & _VECTOR_BASEMAP_LAYER_IDS))
    render_engine = _resolve_render_engine(
        tile_mode=tile_mode,
        vector_ready=vector_ready,
        vector_style_ready=vector_style_ready,
    )
    vector_render_error = None
    if tile_mode == "vector":
        if not vector_ready:
            vector_render_error = "vector_template_missing"
        elif not vector_style_ready:
            vector_render_error = "vector_layers_missing"

    overall_state = _resolve_overall_state(osrm_up=osrm_up, tiles_up=tiles_up)

    return {
        "osrm_up": bool(osrm_up),
        "tiles_up": bool(tiles_up),
        "osrm_latency_ms": osrm_latency_ms,
        "tiles_latency_ms": tiles_latency_ms,
        "osrm_error": osrm_error,
        "tiles_error": tiles_error,
        "tile_url_template": resolved_tile_template or str(config.MAP_TILE_URL_TEMPLATE or "").strip(),
        "tile_mode": tile_mode,
        "vector_tile_template": vector_tile_template,
        "vector_dataset_id": vector_dataset_id,
        "vector_bounds": vector_bounds,
        "using_public_raster_fallback": bool(using_public_raster_fallback),
        "public_raster_fallback_url": str(
            config.MAP_PUBLIC_RASTER_FALLBACK_URL or ""
        ).strip(),
        "public_raster_fallback_attribution": str(
            config.MAP_PUBLIC_RASTER_FALLBACK_ATTRIBUTION or ""
        ).strip(),
        "vector_ready": vector_ready,
        "vector_layers_available": sorted(layer_set),
        "vector_style_ready": vector_style_ready,
        "vector_render_error": vector_render_error,
        "render_engine": render_engine,
        "fonts_available": bool(fonts_available),
        "osrm_data_ready": bool(osrm_data_ready),
        "tiles_data_ready": bool(tiles_data_ready),
        "checked_at": _now_iso(),
        "overall_state": overall_state,
    }


# Contract: get_offline_runtime_status executes one deterministic step in the workflow.
def get_offline_runtime_status(force_refresh: bool = False) -> dict[str, object]:
    # FIX: [PERF-01] Global health circuit with short TTL to remove repetitive probe latency.
    global _CACHE_EXPIRES_AT, _CACHED_STATUS

    now = time.monotonic()
    with _CACHE_LOCK:
        if (not force_refresh) and _CACHED_STATUS and now < _CACHE_EXPIRES_AT:
            return dict(_CACHED_STATUS)

    refreshed = _probe_runtime_status()
    ttl_seconds = max(1.0, float(config.OFFLINE_HEALTH_TTL_SECONDS))
    with _CACHE_LOCK:
        _CACHED_STATUS = dict(refreshed)
        _CACHE_EXPIRES_AT = time.monotonic() + ttl_seconds
        return dict(_CACHED_STATUS)


# Contract: invalidate_runtime_health_cache executes one deterministic step in the workflow.
def invalidate_runtime_health_cache() -> None:
    global _CACHE_EXPIRES_AT
    with _CACHE_LOCK:
        _CACHE_EXPIRES_AT = 0.0
