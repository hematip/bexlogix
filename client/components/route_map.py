from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st


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


def render_route_map(
    stops_df: pd.DataFrame,
    start_lat: float | None = None,
    start_lon: float | None = None,
) -> None:
    if stops_df.empty:
        st.info("No route points available to display on map.")
        return

    if not {"lat", "lon"}.issubset(stops_df.columns):
        st.warning("Map cannot be rendered — coordinates are missing.")
        return

    safe_df = stops_df.copy()
    safe_df["lat"] = pd.to_numeric(safe_df["lat"], errors="coerce")
    safe_df["lon"] = pd.to_numeric(safe_df["lon"], errors="coerce")
    if "route_order" in safe_df.columns:
        safe_df["route_order"] = pd.to_numeric(safe_df["route_order"], errors="coerce")

    store_points = safe_df.dropna(subset=["lat", "lon"]).copy()
    if store_points.empty:
        st.warning("All assigned stores are missing valid coordinates.")
        return

    start_point = _extract_start_point(store_points, start_lat, start_lon)

    layers: list[pdk.Layer] = []

    # Store markers
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

    # Start point
    if start_point is not None:
        start_df = pd.DataFrame(
            [{"lat": start_point[0], "lon": start_point[1], "label": "Start Point"}]
        )
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

    # Route path
    ordered = (
        store_points.dropna(subset=["route_order"])
        .sort_values(
            ["route_order", "store_code"] if "store_code" in store_points.columns
            else ["route_order"]
        )
    )

    path_points: list[list[float]] = []
    if start_point is not None:
        path_points.append([start_point[1], start_point[0]])
    for _, row in ordered.iterrows():
        path_points.append([float(row["lon"]), float(row["lat"])])

    if len(path_points) >= 2:
        layers.append(
            pdk.Layer(
                "PathLayer",
                data=[{"path": path_points}],
                get_path="path",
                get_color=[91, 127, 255, 160],
                width_scale=8,
                width_min_pixels=3,
                pickable=False,
            )
        )

    # View state
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
            "<b>Store:</b> {store_code} — {store_name}<br/>"
            "<b>Order:</b> {route_order}<br/>"
            "<b>Status:</b> {assignment_status}"
        ),
        "style": {
            "backgroundColor": "#2C3E50",
            "color": "#F2F4F7",
            "borderRadius": "8px",
            "padding": "8px 12px",
            "fontSize": "13px",
            "fontFamily": "Inter, Segoe UI, sans-serif",
        },
    }

    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            map_style="road",
            tooltip=tooltip,
        ),
        use_container_width=True,
    )

    # Legend
    st.markdown(
        """<div style="display:flex;gap:1.5rem;margin-top:0.5rem;font-size:0.82rem;color:#6C7A89;">
            <span>🔵 Visitor start</span>
            <span>🔴 Assigned stores</span>
            <span>🔷 Route path</span>
        </div>""",
        unsafe_allow_html=True,
    )
