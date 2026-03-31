import os
from datetime import date
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from client.components.route_map import render_route_map
from server.app.services import assignment_service, import_service, import_users_service
from server.app.services import import_visitors_service, reporting_export_service
from server.app.services import routing_service, telesales_service, visit_service
from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.visitor_profile import VisitorProfile
from server.db.database import get_db_session


def _import_uploaded_excel(uploaded_file, import_func, label: str) -> None:
    if uploaded_file is None:
        st.warning(f"Please upload an Excel file for {label}.")
        return

    temp_path = None
    try:
        with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(uploaded_file.getbuffer())
            temp_path = tmp.name

        db = get_db_session()
        try:
            processed_count = import_func(temp_path, db)
        finally:
            db.close()

        st.success(f"{processed_count} rows processed successfully for {label}.")
    except Exception as exc:
        st.error(f"{label} import failed: {exc}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _load_assignment_rows(work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            a.id AS assignment_id,
            a.work_date,
            v.visitor_code,
            s.store_code,
            s.store_name,
            a.route_order,
            a.route_distance_km,
            a.assignment_status,
            vi.result AS visit_result
        FROM daily_assignments a
        JOIN visitor_profiles v ON v.id = a.visitor_id
        JOIN stores s ON s.id = a.store_id
        LEFT JOIN visits vi ON vi.assignment_id = a.id
        WHERE a.work_date = :work_date
        ORDER BY v.visitor_code, a.route_order, s.store_code
        """
        return pd.read_sql_query(query, db.bind, params={"work_date": work_date.isoformat()})
    finally:
        db.close()


def _load_visitor_route_map_rows(work_date: date, visitor_id: int) -> pd.DataFrame:
    db = get_db_session()
    try:
        query = """
        SELECT
            a.id AS assignment_id,
            a.work_date,
            v.visitor_code,
            s.store_code,
            s.store_name,
            s.lat,
            s.lon,
            a.route_order,
            a.assignment_status,
            COALESCE(dvs.start_lat, v.default_start_lat) AS start_lat,
            COALESCE(dvs.start_lon, v.default_start_lon) AS start_lon
        FROM daily_assignments a
        JOIN visitor_profiles v ON v.id = a.visitor_id
        JOIN stores s ON s.id = a.store_id
        LEFT JOIN daily_visitor_statuses dvs
            ON dvs.visitor_id = a.visitor_id
           AND dvs.work_date = a.work_date
        WHERE a.work_date = :work_date
          AND a.visitor_id = :visitor_id
        ORDER BY a.route_order IS NULL, a.route_order, s.store_code
        """
        return pd.read_sql_query(
            query,
            db.bind,
            params={"work_date": work_date.isoformat(), "visitor_id": visitor_id},
        )
    finally:
        db.close()


def render_manager_dashboard(current_user: dict) -> None:
    st.title("Manager Dashboard")
    st.caption(f"Logged in as: {current_user['username']}")

    work_date = st.date_input("Work Date", value=date.today())

    with st.expander("Data Imports", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            stores_file = st.file_uploader("Stores Excel", type=["xlsx"], key="stores_import")
            users_file = st.file_uploader("Users Excel", type=["xlsx"], key="users_import")
        with col2:
            visitors_file = st.file_uploader("Visitors Excel", type=["xlsx"], key="visitors_import")
            daily_status_file = st.file_uploader(
                "Daily Visitor Status Excel",
                type=["xlsx"],
                key="daily_status_import",
            )

        action_col1, action_col2, action_col3, action_col4 = st.columns(4)
        with action_col1:
            if st.button("Import Stores"):
                _import_uploaded_excel(stores_file, import_service.import_stores_from_excel, "stores")
        with action_col2:
            if st.button("Import Users"):
                _import_uploaded_excel(users_file, import_users_service.import_users_from_excel, "users")
        with action_col3:
            if st.button("Import Visitors"):
                _import_uploaded_excel(
                    visitors_file,
                    import_visitors_service.import_visitor_profiles_from_excel,
                    "visitor profiles",
                )
        with action_col4:
            if st.button("Import Daily Status"):
                _import_uploaded_excel(
                    daily_status_file,
                    import_daily_visitor_statuses_from_excel,
                    "daily visitor status",
                )

    st.subheader("Route Operations")
    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        if st.button("Generate Draft Route"):
            db = get_db_session()
            try:
                summary = assignment_service.generate_draft_assignments(
                    db=db,
                    work_date=work_date,
                    manager_user_id=current_user["id"],
                    replace_existing_draft=True,
                )
                st.success(f"Draft generation completed: {summary}")
            except Exception as exc:
                st.error(f"Draft generation failed: {exc}")
            finally:
                db.close()

    with col_b:
        if st.button("Generate Route Order"):
            db = get_db_session()
            try:
                planned_stops = routing_service.apply_routes_for_work_date(
                    db=db,
                    work_date=work_date,
                    planner=routing_service.NearestNeighborRoutePlanner(),
                )
                st.success(f"Route order generated for {planned_stops} assignments.")
            except Exception as exc:
                st.error(f"Route generation failed: {exc}")
            finally:
                db.close()

    with col_c:
        if st.button("Publish Routes"):
            db = get_db_session()
            try:
                published_count = assignment_service.publish_assignments(
                    db=db,
                    work_date=work_date,
                    manager_user_id=current_user["id"],
                )
                st.success(f"{published_count} assignments published.")
            except Exception as exc:
                st.error(f"Publish failed: {exc}")
            finally:
                db.close()

    with col_d:
        if st.button("Finalize Unsubmitted"):
            db = get_db_session()
            try:
                finalized_count = visit_service.finalize_unsubmitted_assignments(
                    db=db,
                    work_date=work_date,
                    actor_user_id=current_user["id"],
                )
                st.success(f"{finalized_count} unsubmitted assignments finalized as red.")
            except Exception as exc:
                st.error(f"Finalize failed: {exc}")
            finally:
                db.close()

    db = get_db_session()
    try:
        kpis = reporting_export_service.get_daily_kpis(db, work_date)
        pending_queue = telesales_service.list_pending_followups(db, as_of_date=work_date)
    finally:
        db.close()

    st.subheader("Daily KPIs")
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    kpi_col1.metric("Due Stores", kpis["due_stores"])
    kpi_col2.metric("Assigned", kpis["assigned_stores"])
    kpi_col3.metric("Completed Visits", kpis["completed_visits"])
    kpi_col4.metric("Green / Yellow / Red", f"{kpis['green']} / {kpis['yellow']} / {kpis['red']}")
    kpi_col5.metric("Telesales Queue", kpis["telesales_queue_size"])

    st.subheader("Assignments")
    assignment_df = _load_assignment_rows(work_date)
    st.dataframe(assignment_df, use_container_width=True)

    st.subheader("Telesales Pending Queue")
    if pending_queue:
        st.dataframe(pd.DataFrame(pending_queue), use_container_width=True)
    else:
        st.info("No pending telesales items.")

    db = get_db_session()
    try:
        visitor_rows = (
            db.query(VisitorProfile.id, VisitorProfile.visitor_code)
            .join(DailyAssignment, DailyAssignment.visitor_id == VisitorProfile.id)
            .filter(DailyAssignment.work_date == work_date)
            .distinct()
            .order_by(VisitorProfile.visitor_code)
            .all()
        )
    finally:
        db.close()

    visitor_options = {visitor_code: visitor_id for visitor_id, visitor_code in visitor_rows}

    st.subheader("Route Map")
    selected_visitor_code = st.selectbox(
        "Select Visitor for Route Map and Export",
        options=[""] + list(visitor_options.keys()),
    )

    if selected_visitor_code:
        selected_visitor_id = visitor_options[selected_visitor_code]
        route_map_df = _load_visitor_route_map_rows(work_date, selected_visitor_id)
        if route_map_df.empty:
            st.info("No route rows found for selected visitor/date.")
        else:
            render_route_map(route_map_df)

    st.subheader("Exports")
    if selected_visitor_code:
        db = get_db_session()
        try:
            route_buffer = reporting_export_service.export_visitor_route_excel(
                db=db,
                work_date=work_date,
                visitor_id=visitor_options[selected_visitor_code],
            )
            st.download_button(
                label="Download Visitor Route Excel",
                data=route_buffer.getvalue(),
                file_name=f"route_{work_date.isoformat()}_{selected_visitor_code}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        finally:
            db.close()

    db = get_db_session()
    try:
        summary_buffer = reporting_export_service.export_manager_daily_summary_excel(
            db=db,
            work_date=work_date,
        )
    finally:
        db.close()
    st.download_button(
        label="Download Manager Daily Summary",
        data=summary_buffer.getvalue(),
        file_name=f"summary_{work_date.isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
