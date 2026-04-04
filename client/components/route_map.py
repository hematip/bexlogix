# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

import html
import json
from uuid import uuid4

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from server.app.services import routing_service


# Contract: _to_py_scalar executes one deterministic step in the workflow.
def _to_py_scalar(value):
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    return str(value)


# Contract: _extract_start_point executes one deterministic step in the workflow.
def _extract_start_point(
    stops_df: pd.DataFrame,
    start_lat: float | None,
    start_lon: float | None,
) -> tuple[float, float] | None:
    if start_lat is not None and start_lon is not None:
        return float(start_lat), float(start_lon)

    if {"start_lat", "start_lon"}.issubset(stops_df.columns):
        candidates = (
            stops_df[["start_lat", "start_lon"]]
            .dropna(subset=["start_lat", "start_lon"])
            .head(1)
        )
        if not candidates.empty:
            row = candidates.iloc[0]
            return float(row["start_lat"]), float(row["start_lon"])
    return None


# Contract: _build_straight_path executes one deterministic step in the workflow.
def _build_straight_path(
    start_point: tuple[float, float] | None,
    ordered_points: pd.DataFrame,
) -> list[list[float]]:
    path_points: list[list[float]] = []
    if start_point is not None:
        path_points.append([float(start_point[1]), float(start_point[0])])  # lon, lat

    for _, row in ordered_points.iterrows():
        path_points.append([float(row["lon"]), float(row["lat"])])  # lon, lat
    return path_points


# Contract: _build_route_geometry_path executes one deterministic step in the workflow.
def _build_route_geometry_path(
    start_point: tuple[float, float] | None,
    ordered_points: pd.DataFrame,
) -> list[list[float]]:
    if start_point is None or ordered_points.empty:
        return _build_straight_path(start_point, ordered_points)

    stops = [
        {
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "store_code": str(row.get("store_code") or ""),
        }
        for _, row in ordered_points.iterrows()
    ]

    road_geometry = routing_service.fetch_osrm_route_geometry(
        start_lat=float(start_point[0]),
        start_lon=float(start_point[1]),
        ordered_stops=stops,
    )
    if len(road_geometry) >= 2:
        return [[float(pair[0]), float(pair[1])] for pair in road_geometry]

    return _build_straight_path(start_point, ordered_points)


# Contract: _build_marker_rows executes one deterministic step in the workflow.
def _build_marker_rows(store_points: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, row in store_points.iterrows():
        route_order_value = _to_py_scalar(row.get("route_order"))
        rows.append(
            {
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "store_code": str(_to_py_scalar(row.get("store_code")) or ""),
                "store_name": str(_to_py_scalar(row.get("store_name")) or ""),
                "assignment_status": str(_to_py_scalar(row.get("assignment_status")) or ""),
                "route_order": int(route_order_value) if route_order_value is not None else None,
                "route_label": f"{int(route_order_value)}" if route_order_value is not None else "",
            }
        )
    return rows


# Contract: _render_leaflet_map executes one deterministic step in the workflow.
def _render_leaflet_map(
    marker_rows: list[dict],
    path_points_lon_lat: list[list[float]],
    start_point: tuple[float, float] | None,
) -> None:
    if not marker_rows:
        st.info("داده‌ای برای نمایش روی نقشه وجود ندارد.")
        return

    map_id = f"route-map-{uuid4().hex}"

    lats = [float(m["lat"]) for m in marker_rows]
    lons = [float(m["lon"]) for m in marker_rows]
    if start_point is not None:
        lats.append(float(start_point[0]))
        lons.append(float(start_point[1]))

    payload = {
        "center": [sum(lats) / len(lats), sum(lons) / len(lons)],  # lat, lon
        "zoom": 11,
        "start": [float(start_point[0]), float(start_point[1])] if start_point is not None else None,
        "markers": marker_rows,
        "path": [[float(pair[1]), float(pair[0])] for pair in path_points_lon_lat],  # lat, lon
    }
    payload_json = json.dumps(payload, ensure_ascii=False)

    html_block = f"""
    <link
      rel="stylesheet"
      href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
      crossorigin=""
    />
    <style>
      #{map_id} {{
        width: 100%;
        height: 500px;
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 3px 3px 8px rgba(204, 208, 216, 0.85), -3px -3px 8px rgba(255, 255, 255, 0.95);
      }}
      .route-order-tooltip {{
        background: rgba(255, 255, 255, 0.95) !important;
        border: none !important;
        border-radius: 8px !important;
        color: #1F2937 !important;
        font-weight: 700 !important;
        box-shadow: 1px 1px 4px rgba(0, 0, 0, 0.15);
      }}
      .route-order-tooltip:before {{
        display: none !important;
      }}
    </style>
    <div id="{map_id}"></div>
    <script
      src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
      integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
      crossorigin="">
    </script>
    <script>
      (function() {{
        const payload = {payload_json};
        const map = L.map("{map_id}", {{ zoomControl: true }});
        map.setView(payload.center, payload.zoom || 11);

        L.tileLayer(
          "https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
          {{
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap contributors"
          }}
        ).addTo(map);

        if (Array.isArray(payload.path) && payload.path.length > 1) {{
          L.polyline(payload.path, {{
            color: "#3D5FCC",
            weight: 4,
            opacity: 0.85
          }}).addTo(map);
        }}

        if (Array.isArray(payload.start) && payload.start.length === 2) {{
          L.circleMarker(payload.start, {{
            radius: 8,
            color: "#2563EB",
            fillColor: "#3D5FCC",
            fillOpacity: 1,
            weight: 2
          }}).addTo(map).bindPopup("نقطه شروع ویزیتور");
        }}

        const bounds = [];
        if (Array.isArray(payload.start) && payload.start.length === 2) {{
          bounds.push(payload.start);
        }}

        payload.markers.forEach((m) => {{
          const latlng = [m.lat, m.lon];
          bounds.push(latlng);
          const marker = L.circleMarker(latlng, {{
            radius: 6,
            color: "#B91C1C",
            fillColor: "#DC2626",
            fillOpacity: 0.92,
            weight: 2
          }}).addTo(map);

          if (m.route_label) {{
            marker.bindTooltip(String(m.route_label), {{
              permanent: true,
              direction: "center",
              className: "route-order-tooltip"
            }});
          }}

          const routeOrderText = m.route_order === null || m.route_order === undefined ? "—" : String(m.route_order);
          const popupHtml =
            '<div style="direction:rtl;text-align:right;font-family:Vazirmatn,IRANSansFaNum,IRANSans FaNum,IRAN Sans,Tahoma,Arial,sans-serif;line-height:1.8;">' +
            '<b>فروشگاه:</b> ' + String(m.store_code || "") + ' — ' + String(m.store_name || "") + '<br/>' +
            '<b>ترتیب مسیر:</b> ' + routeOrderText + '<br/>' +
            '<b>وضعیت:</b> ' + String(m.assignment_status || "—") +
            '</div>';
          marker.bindPopup(popupHtml);
        }});

        if (bounds.length > 1) {{
          map.fitBounds(bounds, {{ padding: [30, 30] }});
        }}
      }})();
    </script>
    """
    components.html(html_block, height=520)


# Contract: render_route_map executes one deterministic step in the workflow.
def render_route_map(
    stops_df: pd.DataFrame,
    start_lat: float | None = None,
    start_lon: float | None = None,
) -> None:
    if stops_df.empty:
        st.info("هیچ نقطه مسیری برای نمایش روی نقشه وجود ندارد.")
        return

    if not {"lat", "lon"}.issubset(stops_df.columns):
        st.warning("به دلیل نبود مختصات، نمایش نقشه ممکن نیست.")
        return

    safe_df = stops_df.copy()
    safe_df["lat"] = pd.to_numeric(safe_df["lat"], errors="coerce")
    safe_df["lon"] = pd.to_numeric(safe_df["lon"], errors="coerce")
    if "route_order" in safe_df.columns:
        safe_df["route_order"] = pd.to_numeric(safe_df["route_order"], errors="coerce")

    store_points = safe_df.dropna(subset=["lat", "lon"]).copy()
    if store_points.empty:
        st.warning("مختصات معتبر برای فروشگاه‌های تخصیص‌یافته پیدا نشد.")
        return

    start_point = _extract_start_point(store_points, start_lat, start_lon)
    marker_rows = _build_marker_rows(store_points)

    ordered_points = (
        store_points.dropna(subset=["route_order"])
        .sort_values(
            ["route_order", "store_code"] if "store_code" in store_points.columns else ["route_order"]
        )
    )
    path_points = _build_route_geometry_path(start_point=start_point, ordered_points=ordered_points)

    _render_leaflet_map(
        marker_rows=marker_rows,
        path_points_lon_lat=path_points,
        start_point=start_point,
    )

    st.markdown(
        """<div style="display:flex;gap:1.5rem;margin-top:0.5rem;font-size:0.82rem;color:#5A6878;flex-wrap:wrap;">
            <span>🔵 نقطه شروع ویزیتور</span>
            <span>🔴 فروشگاه‌های تخصیص‌یافته</span>
            <span>🔷 مسیر پیشنهادی (مسیر جاده‌ای)</span>
        </div>""",
        unsafe_allow_html=True,
    )
