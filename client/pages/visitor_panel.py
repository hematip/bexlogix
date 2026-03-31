from datetime import date

import pandas as pd
import streamlit as st

from client.components.route_map import render_route_map
from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.visit_result import VisitResult
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.store import Store
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import visit_service
from server.db.database import get_db_session


def _get_visitor_profile_by_user_id(user_id: int) -> VisitorProfile | None:
    db = get_db_session()
    try:
        return (
            db.query(VisitorProfile)
            .filter(VisitorProfile.user_id == user_id)
            .first()
        )
    finally:
        db.close()


def _load_visitor_assignments(visitor_id: int, work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            a.id AS assignment_id,
            a.work_date,
            s.store_code,
            s.store_name,
            s.address,
            s.lat,
            s.lon,
            a.route_order,
            a.route_distance_km,
            a.assignment_status,
            COALESCE(dvs.start_lat, vp.default_start_lat) AS start_lat,
            COALESCE(dvs.start_lon, vp.default_start_lon) AS start_lon,
            vi.id AS visit_id,
            vi.result AS visit_result,
            vi.note AS visit_note
        FROM daily_assignments a
        JOIN visitor_profiles vp ON vp.id = a.visitor_id
        JOIN stores s ON s.id = a.store_id
        LEFT JOIN daily_visitor_statuses dvs
            ON dvs.visitor_id = a.visitor_id
           AND dvs.work_date = a.work_date
        LEFT JOIN visits vi ON vi.assignment_id = a.id
        WHERE a.visitor_id = :visitor_id
          AND a.work_date = :work_date
        ORDER BY a.route_order IS NULL, a.route_order, s.store_code
        """
        return pd.read_sql_query(
            query,
            db.bind,
            params={"visitor_id": visitor_id, "work_date": work_date.isoformat()},
        )
    finally:
        db.close()


def render_visitor_panel(current_user: dict) -> None:
    st.title("Visitor Panel")
    st.caption(f"Logged in as: {current_user['username']}")

    visitor_profile = _get_visitor_profile_by_user_id(current_user["id"])
    if not visitor_profile:
        st.error("Visitor profile not found for this account.")
        return

    work_date = st.date_input("Work Date", value=date.today())
    assignments_df = _load_visitor_assignments(visitor_profile.id, work_date)

    if assignments_df.empty:
        st.info("No assignments found for this date.")
        return

    st.subheader("Route Map")
    render_route_map(assignments_df)

    st.subheader("My Route")
    st.dataframe(
        assignments_df[
            [
                "assignment_id",
                "route_order",
                "store_code",
                "store_name",
                "route_distance_km",
                "assignment_status",
                "visit_result",
            ]
        ],
        use_container_width=True,
    )

    for row in assignments_df.to_dict(orient="records"):
        title = (
            f"Stop {row['route_order'] if pd.notna(row['route_order']) else '-'} - "
            f"{row['store_code']} | {row['store_name']}"
        )
        with st.expander(title):
            st.write(f"Address: {row['address']}")
            st.write(f"Coordinates: {row['lat']}, {row['lon']}")
            st.write(f"Assignment Status: {row['assignment_status']}")

            if pd.notna(row["visit_result"]):
                st.success(f"Submitted result: {row['visit_result']}")
                if row["visit_note"]:
                    st.caption(f"Note: {row['visit_note']}")
                continue

            if row["assignment_status"] != AssignmentStatus.PUBLISHED.value:
                st.info("Visit submission is enabled only for published assignments.")
                continue

            form_key = f"visit_form_{row['assignment_id']}"
            with st.form(form_key):
                result = st.selectbox(
                    "Visit Result",
                    options=[item.value for item in VisitResult],
                    key=f"visit_result_{row['assignment_id']}",
                )
                note = st.text_area(
                    "Visit Note",
                    key=f"visit_note_{row['assignment_id']}",
                )
                submitted = st.form_submit_button("Submit Visit Result")

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
                    st.success("Visit result submitted successfully.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Submit failed: {exc}")
                finally:
                    db.close()
