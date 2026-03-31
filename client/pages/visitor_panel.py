from datetime import date

import pandas as pd
import streamlit as st

from client.components.route_map import render_route_map
from client.styles.neumorphism import (
    neu_metric,
    neu_section_header,
    status_badge,
)
from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.visit_result import VisitResult
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import reporting_export_service, visit_service
from server.db.database import get_db_session


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def _get_visitor_profile(user_id: int) -> VisitorProfile | None:
    db = get_db_session()
    try:
        return db.query(VisitorProfile).filter(VisitorProfile.user_id == user_id).first()
    finally:
        db.close()


def _load_assignments(visitor_id: int, work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            a.id AS assignment_id, a.work_date,
            s.store_code, s.store_name, s.address, s.lat, s.lon,
            a.route_order, a.route_distance_km, a.assignment_status,
            COALESCE(dvs.start_lat, vp.default_start_lat) AS start_lat,
            COALESCE(dvs.start_lon, vp.default_start_lon) AS start_lon,
            vi.id AS visit_id, vi.result AS visit_result, vi.note AS visit_note
        FROM daily_assignments a
        JOIN visitor_profiles vp ON vp.id = a.visitor_id
        JOIN stores s ON s.id = a.store_id
        LEFT JOIN daily_visitor_statuses dvs
            ON dvs.visitor_id = a.visitor_id AND dvs.work_date = a.work_date
        LEFT JOIN visits vi ON vi.assignment_id = a.id
        WHERE a.visitor_id = :vid AND a.work_date = :wd
        ORDER BY a.route_order IS NULL, a.route_order, s.store_code
        """
        return pd.read_sql_query(
            query, db.bind, params={"vid": visitor_id, "wd": work_date.isoformat()}
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RESULT_COLORS = {
    "green": "#27AE60",
    "yellow": "#F39C12",
    "red": "#E74C3C",
}


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def render_visitor_panel(current_user: dict) -> None:
    st.markdown(
        '<h2 style="margin-bottom:0.2rem;">My Route</h2>',
        unsafe_allow_html=True,
    )

    profile = _get_visitor_profile(current_user["id"])
    if not profile:
        st.error("Visitor profile not found for this account.")
        return

    work_date = st.date_input("📅  Work Date", value=date.today())
    assignments_df = _load_assignments(profile.id, work_date)

    if assignments_df.empty:
        st.info("No assignments found for this date.")
        return

    # ── Route summary ─────────────────────────────────────────
    total_stops = len(assignments_df)
    completed = assignments_df["visit_result"].notna().sum()
    total_km = assignments_df["route_distance_km"].dropna().sum()

    s1, s2, s3 = st.columns(3)
    with s1:
        neu_metric("Total Stops", total_stops)
    with s2:
        neu_metric("Completed", int(completed))
    with s3:
        neu_metric("Distance (km)", f"{total_km:.1f}")

    # ── Route map ─────────────────────────────────────────────
    neu_section_header("Route Map")
    render_route_map(assignments_df)

    # ── Download ──────────────────────────────────────────────
    db = get_db_session()
    try:
        route_buf = reporting_export_service.export_visitor_route_excel(
            db=db, work_date=work_date, visitor_id=profile.id,
        )
    finally:
        db.close()

    st.download_button(
        label="📥  Download My Route",
        data=route_buf.getvalue(),
        file_name=f"my_route_{work_date.isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # ── Store visit cards ─────────────────────────────────────
    neu_section_header("Store Visits")

    for row in assignments_df.to_dict(orient="records"):
        order_label = int(row["route_order"]) if pd.notna(row["route_order"]) else "—"
        title = f"Stop {order_label}  •  {row['store_code']} — {row['store_name']}"

        with st.expander(title, expanded=False):
            # Store info
            info_html = f"""
            <div class="neu-card-flat">
                <div style="display:flex;gap:2rem;flex-wrap:wrap;">
                    <div><strong>Address:</strong> {row['address'] or '—'}</div>
                    <div><strong>Coords:</strong> {row['lat']}, {row['lon']}</div>
                    <div><strong>Status:</strong> {status_badge(row['assignment_status'])}</div>
                </div>
            </div>
            """
            st.markdown(info_html, unsafe_allow_html=True)

            # Already submitted
            if pd.notna(row["visit_result"]):
                result = row["visit_result"]
                color = _RESULT_COLORS.get(result, "#6C7A89")
                st.markdown(
                    f"""<div class="neu-card-flat" style="border-left:4px solid {color};padding-left:1rem;">
                        <strong>Result:</strong> {status_badge(result)}
                        {"<br/><em>" + row['visit_note'] + "</em>" if row.get('visit_note') else ""}
                    </div>""",
                    unsafe_allow_html=True,
                )
                continue

            # Not published yet
            if row["assignment_status"] != AssignmentStatus.PUBLISHED.value:
                st.info("Visit submission available only for published assignments.")
                continue

            # Visit submission form
            form_key = f"visit_{row['assignment_id']}"
            with st.form(form_key):
                st.markdown("**Submit Visit Result**")
                result = st.selectbox(
                    "Result",
                    options=[v.value for v in VisitResult],
                    key=f"res_{row['assignment_id']}",
                )
                note = st.text_area(
                    "Comment / Note",
                    key=f"note_{row['assignment_id']}",
                    placeholder="Optional note about this visit...",
                )
                submitted = st.form_submit_button("Submit", use_container_width=True)

            if submitted:
                db = get_db_session()
                try:
                    visit_service.submit_visit_result(
                        db=db,
                        assignment_id=int(row["assignment_id"]),
                        visitor_user_id=current_user["id"],
                        result=result,
                        note=note,
                    )
                    st.success("Visit result submitted.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Submit failed: {exc}")
                finally:
                    db.close()
