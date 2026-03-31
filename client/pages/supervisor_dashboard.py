from datetime import date

import pandas as pd
import streamlit as st

from server.app.services import reporting_export_service, telesales_service
from server.db.database import get_db_session


def _load_supervisor_view(work_date: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    db = get_db_session()
    try:
        assignments_query = """
        SELECT
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
        visits_query = """
        SELECT
            vi.id AS visit_id,
            vi.visit_date,
            vp.visitor_code,
            s.store_code,
            vi.result,
            vi.note
        FROM visits vi
        JOIN visitor_profiles vp ON vp.id = vi.visitor_id
        JOIN stores s ON s.id = vi.store_id
        WHERE vi.visit_date = :work_date
        ORDER BY vp.visitor_code, s.store_code
        """
        assignment_df = pd.read_sql_query(
            assignments_query, db.bind, params={"work_date": work_date.isoformat()}
        )
        visit_df = pd.read_sql_query(
            visits_query, db.bind, params={"work_date": work_date.isoformat()}
        )
        return assignment_df, visit_df
    finally:
        db.close()


def render_supervisor_dashboard(current_user: dict) -> None:
    st.title("Supervisor Dashboard")
    st.caption(f"Logged in as: {current_user['username']}")

    work_date = st.date_input("Work Date", value=date.today())

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

    assignment_df, visit_df = _load_supervisor_view(work_date)

    st.subheader("Assignments and Route Visibility")
    st.dataframe(assignment_df, use_container_width=True)

    st.subheader("Visit Visibility")
    st.dataframe(visit_df, use_container_width=True)

    st.subheader("Telesales Queue Visibility")
    if pending_queue:
        st.dataframe(pd.DataFrame(pending_queue), use_container_width=True)
    else:
        st.info("No pending telesales follow-ups.")

    st.info("Supervisor mode is monitoring-only. Generation and publish actions are disabled.")
