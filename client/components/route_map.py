from __future__ import annotations

from functools import lru_cache
from urllib.request import urlopen

import pandas as pd
import pydeck as pdk
import streamlit as st

from server.app.services import routing_service

LABEL_ENABLED_MAP_STYLES = [
    "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
]


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


@lru_cache(maxsize=8)
def _style_is_reachable(style_url: str) -> bool:
    try:
        with urlopen(style_url, timeout=3) as response:
            status = getattr(response, "status", None)
            return status is None or int(status) < 400
    except Exception:
        return False


def _resolve_map_style() -> str:
    for style in LABEL_ENABLED_MAP_STYLES:
        if _style_is_reachable(style):
            return style
    return LABEL_ENABLED_MAP_STYLES[-1]


def _build_straight_path(
    start_point: tuple[float, float] | None,
    ordered_points: pd.DataFrame,
) -> list[list[float]]:
    path_points: list[list[float]] = []
    if start_point is not None:
        path_points.append([start_point[1], start_point[0]])

    for _, row in ordered_points.iterrows():
        path_points.append([float(row["lon"]), float(row["lat"])])

    return path_points


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
        return road_geometry

    return _build_straight_path(start_point, ordered_points)


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
    store_points["route_label"] = (
        store_points["route_order"].apply(lambda value: f"{int(value)}" if pd.notna(value) else "")
    )

    layers: list[pdk.Layer] = []

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=store_points,
            get_position="[lon, lat]",
            get_fill_color=[220, 80, 65],
            get_radius=80,
            radius_min_pixels=5,
            pickable=True,
        )
    )

    layers.append(
        pdk.Layer(
            "TextLayer",
            data=store_points,
            get_position="[lon, lat]",
            get_text="route_label",
            get_size=14,
            get_color=[30, 41, 59, 230],
            get_alignment_baseline="'center'",
            get_text_anchor="'middle'",
        )
    )

    if start_point is not None:
        start_df = pd.DataFrame([{"lat": start_point[0], "lon": start_point[1], "label": "شروع"}])
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=start_df,
                get_position="[lon, lat]",
                get_fill_color=[91, 127, 255],
                get_radius=110,
                radius_min_pixels=7,
                pickable=True,
            )
        )

    ordered_points = (
        store_points.dropna(subset=["route_order"])
        .sort_values(
            ["route_order", "store_code"] if "store_code" in store_points.columns else ["route_order"]
        )
    )

    path_points = _build_route_geometry_path(start_point=start_point, ordered_points=ordered_points)
    if len(path_points) >= 2:
        layers.append(
            pdk.Layer(
                "PathLayer",
                data=[{"path": path_points}],
                get_path="path",
                get_color=[91, 127, 255, 180],
                width_scale=8,
                width_min_pixels=3,
                pickable=False,
            )
        )

    all_lats = store_points["lat"].tolist()
    all_lons = store_points["lon"].tolist()
    if start_point is not None:
        all_lats.append(start_point[0])
        all_lons.append(start_point[1])

    view_state = pdk.ViewState(
        latitude=sum(all_lats) / len(all_lats),
        longitude=sum(all_lons) / len(all_lons),
        zoom=11,
        pitch=0,
    )

    tooltip = {
        "html": (
            "<b>فروشگاه:</b> {store_code} — {store_name}<br/>"
            "<b>ترتیب مسیر:</b> {route_order}<br/>"
            "<b>وضعیت:</b> {assignment_status}"
        ),
        "style": {
            "backgroundColor": "#1F2937",
            "color": "#F9FAFB",
            "borderRadius": "10px",
            "padding": "8px 12px",
            "fontSize": "13px",
            "fontFamily": "IRANSansFaNum, IRANSans FaNum, IRAN Sans, Tahoma, Segoe UI, sans-serif",
            "direction": "rtl",
            "textAlign": "right",
        },
    }

    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            map_style=_resolve_map_style(),
            tooltip=tooltip,
        ),
        use_container_width=True,
    )

    st.markdown(
        """<div style="display:flex;gap:1.5rem;margin-top:0.5rem;font-size:0.82rem;color:#6C7A89;flex-wrap:wrap;">
            <span>🔵 نقطه شروع ویزیتور</span>
            <span>🔴 فروشگاه‌های تخصیص‌یافته</span>
            <span>🔷 مسیر پیشنهادی (مسیر جاده‌ای)</span>
        </div>""",
        unsafe_allow_html=True,
    )
