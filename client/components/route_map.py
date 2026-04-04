# Purpose: Route map rendering component for assignment and visitor flows.
# Workflow Role: Visualizes stop markers and route geometry in operational dashboards.

from __future__ import annotations

import json
from uuid import uuid4

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from server.app.services import routing_service

_GRADE_STYLES: dict[str, dict[str, str]] = {
    # FIX: Use high-contrast but map-friendly palette so grade colors are clearly visible on cream map tiles.
    "VIP": {"fill": "#7E57C2", "stroke": "#5E35B1", "label": "VIP"},
    "A+": {"fill": "#42A5F5", "stroke": "#1E88E5", "label": "A+"},
    "A": {"fill": "#66BB6A", "stroke": "#43A047", "label": "A"},
    "B": {"fill": "#FFB74D", "stroke": "#FB8C00", "label": "B"},
    "C": {"fill": "#EF5350", "stroke": "#E53935", "label": "C"},
}
_DEFAULT_GRADE_STYLE: dict[str, str] = {"fill": "#6B7280", "stroke": "#374151", "label": "نامشخص"}


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


# Contract: _normalize_grade executes one deterministic step in the workflow.
def _normalize_grade(value: object) -> str:
    return str(value or "").strip().upper()


# Contract: _grade_style executes one deterministic step in the workflow.
def _grade_style(value: object) -> dict[str, str]:
    normalized = _normalize_grade(value)
    return _GRADE_STYLES.get(normalized, _DEFAULT_GRADE_STYLE)


# Contract: _extract_start_point executes one deterministic step in the workflow.
def _extract_start_point(
    stops_df: pd.DataFrame,
    start_lat: float | None,
    start_lon: float | None,
) -> tuple[float, float] | None:
    if start_lat is not None and start_lon is not None:
        return float(start_lat), float(start_lon)

    if {"start_lat", "start_lon"}.issubset(stops_df.columns):
        candidates = stops_df[["start_lat", "start_lon"]].dropna(subset=["start_lat", "start_lon"]).head(1)
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
) -> tuple[list[list[float]], str]:
    if start_point is None or ordered_points.empty:
        return _build_straight_path(start_point, ordered_points), "straight"

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
        return [[float(pair[0]), float(pair[1])] for pair in road_geometry], "osrm"

    return _build_straight_path(start_point, ordered_points), "straight"


# Contract: _build_marker_rows executes one deterministic step in the workflow.
def _build_marker_rows(store_points: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, row in store_points.iterrows():
        route_order_value = _to_py_scalar(row.get("route_order"))
        store_grade = _normalize_grade(_to_py_scalar(row.get("store_grade")))
        grade_style = _grade_style(store_grade)
        rows.append(
            {
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "store_code": str(_to_py_scalar(row.get("store_code")) or ""),
                "store_name": str(_to_py_scalar(row.get("store_name")) or ""),
                "store_grade": store_grade or _DEFAULT_GRADE_STYLE["label"],
                "assignment_status": str(_to_py_scalar(row.get("assignment_status")) or ""),
                "route_order": int(route_order_value) if route_order_value is not None else None,
                "route_label": f"{int(route_order_value)}" if route_order_value is not None else "",
                "marker_fill": grade_style["fill"],
                "marker_stroke": grade_style["stroke"],
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
      .bex-stop-icon {{
        background: transparent !important;
        border: none !important;
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
          const routeNumber = String(m.route_label || "•");
          const markerHtml =
            '<div style="width:26px;height:26px;border-radius:999px;display:flex;align-items:center;justify-content:center;' +
            'font-size:12px;font-weight:700;color:#fff;border:2px solid #fff;box-shadow:0 1px 6px rgba(0,0,0,.35);' +
            'background:' + String(m.marker_fill || "#6B7280") + ';">' + routeNumber + "</div>";
          const marker = L.marker(latlng, {{
            icon: L.divIcon({{
              className: "bex-stop-icon",
              html: markerHtml,
              iconSize: [26, 26],
              iconAnchor: [13, 13]
            }})
          }}).addTo(map);

          const routeOrderText = m.route_order === null || m.route_order === undefined ? "—" : String(m.route_order);
          const popupHtml =
            '<div style="direction:rtl;text-align:right;font-family:Vazirmatn,IRANSansFaNum,IRANSans FaNum,IRAN Sans,Tahoma,Arial,sans-serif;line-height:1.8;">' +
            '<b>فروشگاه:</b> ' + String(m.store_code || "") + ' — ' + String(m.store_name || "") + '<br/>' +
            '<b>گرید:</b> ' + String(m.store_grade || "نامشخص") + '<br/>' +
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

    ordered_points = store_points.dropna(subset=["route_order"]).sort_values(
        ["route_order", "store_code"] if "store_code" in store_points.columns else ["route_order"]
    )
    path_points, geometry_source = _build_route_geometry_path(start_point=start_point, ordered_points=ordered_points)

    _render_leaflet_map(
        marker_rows=marker_rows,
        path_points_lon_lat=path_points,
        start_point=start_point,
    )

    grade_legend = "".join(
        [
            (
                '<span style="display:inline-flex;align-items:center;gap:.35rem;">'
                f'<span style="width:12px;height:12px;border-radius:999px;display:inline-block;background:{style["fill"]};border:1px solid {style["stroke"]};"></span>'
                f'گرید {grade}'
                "</span>"
            )
            for grade, style in _GRADE_STYLES.items()
        ]
    )
    st.markdown(
        f"""<div style="display:flex;gap:1.2rem;margin-top:0.5rem;font-size:0.82rem;color:#5A6878;flex-wrap:wrap;direction:rtl;">
            <span>🔵 نقطه شروع ویزیتور</span>
            <span>🔷 مسیر پیشنهادی (مسیر جاده‌ای)</span>
            {grade_legend}
        </div>""",
        unsafe_allow_html=True,
    )
    if geometry_source == "osrm":
        st.caption("مبنای ترسیم مسیر: مسیر جاده‌ای OSRM")
    else:
        st.caption("مبنای ترسیم مسیر: خط مستقیم بین نقاط (به‌دلیل در دسترس نبودن OSRM)")
