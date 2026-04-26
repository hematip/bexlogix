# Purpose: Supervisor dashboard for monitoring and route approval workflow.
# Workflow Role: Read-heavy operational oversight with controlled pre-publish approvals.

from __future__ import annotations

from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from client.components.empty_state import get_empty_state_message
from client.components.jalali_date import jalali_date_input
from client.i18n import align, t
from client.components.rtl_table import render_rtl_table
from client.components.route_map import render_route_map
from client.styles.neumorphism import neu_section_header, render_metric_grid, render_page_title
from server.app.services import (
    dashboard_query_service,
    reporting_export_service,
    runtime_health_service,
    telesales_service,
)
from server.db.database import get_db

def _all_visitors_option() -> str:
    return t("— همه ویزیتورها —", "— All Visitors —")


@st.cache_data(ttl=300, show_spinner=False)
def _cached_assignments(work_date_iso: str) -> pd.DataFrame:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return dashboard_query_service.load_supervisor_assignments_df(db=db, work_date=work_date)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_visits(work_date_iso: str) -> pd.DataFrame:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return dashboard_query_service.load_supervisor_visits_df(db=db, work_date=work_date)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_route_map_data(work_date_iso: str, visitor_id: int) -> pd.DataFrame:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return dashboard_query_service.load_route_map_df(
            db=db,
            work_date=work_date,
            visitor_id=visitor_id,
        )


@st.cache_data(ttl=300, show_spinner=False)
def _cached_visitor_options(work_date_iso: str) -> dict[str, int]:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return dashboard_query_service.get_visitor_options(db=db, work_date=work_date)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_daily_kpis_and_queue(work_date_iso: str) -> tuple[dict, list[dict]]:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return (
            reporting_export_service.get_daily_kpis(db, work_date),
            telesales_service.list_pending_followups(db, as_of_date=work_date),
        )


def _export_all_routes(work_date: date, visitor_options: dict[str, int]) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for visitor_code, visitor_id in visitor_options.items():
            with get_db() as db:
                route_buffer = reporting_export_service.export_visitor_route_excel(
                    db=db,
                    work_date=work_date,
                    visitor_id=visitor_id,
                )
            route_df = pd.read_excel(BytesIO(route_buffer.getvalue()), sheet_name="route")
            route_df.to_excel(writer, sheet_name=visitor_code[:31], index=False)
    output.seek(0)
    return output


def render_supervisor_dashboard(current_user: dict) -> None:
    render_page_title(t("داشبورد سرپرست", "Supervisor Dashboard"))

    work_date = jalali_date_input(
        label=t("📅 تاریخ کاری", "📅 Work Date"),
        key_prefix="supervisor_work_date",
        default_gregorian=date.today(),
    )
    work_date_iso = work_date.isoformat()

    kpis, pending_queue = _cached_daily_kpis_and_queue(work_date_iso)
    visitor_options = _cached_visitor_options(work_date_iso)
    assignment_df = _cached_assignments(work_date_iso)

    neu_section_header(t("شاخص‌های روزانه", "Daily KPIs"))
    render_metric_grid(
        [
            (t("صف تامین‌پذیر", "Due Stores"), kpis["due_stores"]),
            (t("تخصیص‌شده", "Assigned"), kpis["assigned_stores"]),
            (t("ویزیت تکمیل‌شده", "Completed Visits"), kpis["completed_visits"]),
            (t("سبز / زرد / قرمز", "Green / Yellow / Red"), f"{kpis['green']} / {kpis['yellow']} / {kpis['red']}"),
            (t("صف فروش تلفنی", "Telesales Queue"), kpis["telesales_queue_size"]),
        ]
    )

    neu_section_header(t("بررسی مسیر ویزیتورها", "Visitor Route Review"))
    st.markdown(
        f'<div class="panel-description" style="text-align:{align()} !important;margin:0.1rem 0 0.35rem;">'
        + t("راهنما: در همین کادر انتخاب ویزیتور می‌توانید جست‌وجو کنید.", "Tip: use this visitor box to search quickly.")
        + "</div>",
        unsafe_allow_html=True,
    )
    all_visitors_option = _all_visitors_option()
    selected_code = st.selectbox(
        t("انتخاب ویزیتور", "Select Visitor"),
        options=[all_visitors_option] + list(visitor_options.keys()),
        index=0,
        placeholder=t("ویزیتور را انتخاب یا جست‌وجو کنید...", "Select or search a visitor..."),
        key=f"supervisor_select_{work_date_iso}",
    )

    if selected_code == all_visitors_option:
        if assignment_df.empty:
            st.info(get_empty_state_message(role="supervisor", context="no_assignments"))
        else:
            render_rtl_table(
                assignment_df,
                key_prefix=f"supervisor_assignments_all_{work_date_iso}",
            )
    else:
        selected_id = visitor_options[selected_code]
        filtered_df = assignment_df[assignment_df["visitor_code"] == selected_code]
        if filtered_df.empty:
            st.info(get_empty_state_message(role="supervisor", context="no_assignments"))
        else:
            render_rtl_table(
                filtered_df,
                key_prefix=f"supervisor_assignments_{selected_code}_{work_date_iso}",
            )

        route_df = _cached_route_map_data(work_date_iso, selected_id)
        if not route_df.empty:
            runtime_state = runtime_health_service.get_offline_runtime_status()
            render_route_map(
                route_df,
                runtime_status=runtime_state,
                show_runtime_messages=False,
            )

    neu_section_header(t("خروجی‌ها", "Exports"))
    d1, d2 = st.columns(2)
    with d1:
        if selected_code != all_visitors_option and selected_code in visitor_options:
            with get_db() as db:
                route_buf = reporting_export_service.export_visitor_route_excel(
                    db=db,
                    work_date=work_date,
                    visitor_id=visitor_options[selected_code],
                )
            st.download_button(
                label=t(f"📥 دانلود مسیر {selected_code}", f"📥 Download Route {selected_code}"),
                data=route_buf.getvalue(),
                file_name=f"route_{work_date_iso}_{selected_code}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with d2:
        if visitor_options:
            all_buf = _export_all_routes(work_date, visitor_options)
            st.download_button(
                label=t("📥 دانلود همه مسیرها", "📥 Download All Routes"),
                data=all_buf.getvalue(),
                file_name=f"all_routes_{work_date_iso}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    neu_section_header(t("نتایج ویزیت", "Visit Results"))
    visit_df = _cached_visits(work_date_iso)
    if visit_df.empty:
        st.info(get_empty_state_message(role="supervisor", context="no_visits"))
    else:
        render_rtl_table(
            visit_df,
            key_prefix=f"supervisor_visits_{work_date_iso}",
        )

    neu_section_header(t("صف فروش تلفنی", "Telesales Queue"))
    if pending_queue:
        pending_df = pd.DataFrame(pending_queue)
        pending_df = pending_df.drop(columns=["store_lat", "store_lon"], errors="ignore")
        render_rtl_table(
            pending_df,
            key_prefix=f"supervisor_telesales_{work_date_iso}",
        )
    else:
        st.info(get_empty_state_message(role="supervisor", context="no_telesales"))
