import os
from datetime import date
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from client.components.jalali_date import jalali_date_input
from client.components.route_map import render_route_map
from client.styles.neumorphism import neu_metric, neu_section_header, render_page_title
from server.app.services import (
    assignment_service,
    dashboard_query_service,
    import_service,
    reporting_export_service,
    routing_service,
    telesales_service,
    visit_service,
)
from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.db.database import get_db_session


def _save_uploaded_excel(uploaded_file) -> str | None:
    if uploaded_file is None:
        return None

    with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def _load_assignments(work_date: date) -> pd.DataFrame:
    db = get_db_session()
    try:
        return dashboard_query_service.load_manager_assignments_df(db=db, work_date=work_date)
    finally:
        db.close()


def _load_visitor_route_map(work_date: date, visitor_id: int) -> pd.DataFrame:
    db = get_db_session()
    try:
        return dashboard_query_service.load_route_map_df(
            db=db,
            work_date=work_date,
            visitor_id=visitor_id,
        )
    finally:
        db.close()


def _get_visitor_options(work_date: date) -> dict[str, int]:
    db = get_db_session()
    try:
        return dashboard_query_service.get_visitor_options(db=db, work_date=work_date)
    finally:
        db.close()


def _get_operational_snapshot_and_kpis(work_date: date) -> tuple[dict, dict, list[dict]]:
    db = get_db_session()
    try:
        snapshot = assignment_service.get_work_date_operational_snapshot(db, work_date)
        kpis = reporting_export_service.get_daily_kpis(db, work_date)
        pending_queue = telesales_service.list_pending_followups(db, as_of_date=work_date)
        return snapshot, kpis, pending_queue
    finally:
        db.close()


def _run_apply_files_and_build_route(
    work_date: date,
    current_user: dict,
    stores_file,
    daily_file,
) -> dict:
    if daily_file is None:
        raise ValueError("برای ساخت مسیر، بارگذاری فایل وضعیت روزانه الزامی است.")

    stores_path = _save_uploaded_excel(stores_file)
    daily_path = _save_uploaded_excel(daily_file)

    try:
        db = get_db_session()
        try:
            stores_processed = 0
            if stores_path:
                stores_processed = import_service.import_stores_from_excel(stores_path, db)

            daily_processed = import_daily_visitor_statuses_from_excel(daily_path, db)
            status_count_for_selected_date = dashboard_query_service.get_daily_status_row_count(
                db=db,
                work_date=work_date,
            )
            if status_count_for_selected_date <= 0:
                raise ValueError(
                    "فایل وضعیت روزانه برای تاریخ انتخاب‌شده ردیفی ندارد. "
                    "تاریخ کاری را با work_date فایل یکسان کنید."
                )

            draft_summary = assignment_service.generate_draft_assignments(
                db=db,
                work_date=work_date,
                manager_user_id=current_user["id"],
                replace_existing_draft=True,
            )

            routed_count = routing_service.apply_routes_for_work_date(
                db=db,
                work_date=work_date,
                planner=routing_service.OSRMRoutePlanner(
                    fallback_planner=routing_service.NearestNeighborRoutePlanner(),
                ),
            )

            quality = assignment_service.evaluate_route_quality_vs_round_robin(
                db=db,
                work_date=work_date,
            )

            return {
                "stores_processed": stores_processed,
                "daily_processed": daily_processed,
                "draft_summary": draft_summary,
                "routed_count": routed_count,
                "quality": quality,
            }
        finally:
            db.close()
    finally:
        for path in [stores_path, daily_path]:
            if path and os.path.exists(path):
                os.remove(path)


def _render_pipeline_result(result: dict) -> None:
    draft_summary = result["draft_summary"]
    quality = result["quality"]

    st.success(
        "فایل‌ها اعمال شد و مسیرها ساخته شدند. "
        f"فروشگاه پردازش‌شده: {result['stores_processed']} | "
        f"وضعیت روزانه پردازش‌شده: {result['daily_processed']} | "
        f"تخصیص ساخته‌شده: {draft_summary.get('created_assignments', 0)} | "
        f"مرتب‌سازی مسیر: {result['routed_count']}"
    )

    q1, q2, q3, q4 = st.columns(4)
    with q1:
        neu_metric("مسافت مبنای قبلی (km)", quality["baseline_km"])
    with q2:
        neu_metric("مسافت فعلی (km)", quality["current_km"])
    with q3:
        neu_metric("درصد بهبود", f"{quality['improvement_pct']}%")
    with q4:
        gate_text = "قبول" if quality["passes_gate"] else "رد"
        neu_metric("گیت کیفیت", gate_text)

    if not quality["passes_gate"]:
        st.warning(
            "گیت کیفیت عبور نکرده است. "
            "بهبود مسیر باید حداقل ۲۰٪ نسبت به مقدار مبنا باشد."
        )


def render_manager_dashboard(current_user: dict) -> None:
    render_page_title("داشبورد مدیر")

    work_date = jalali_date_input(
        label="📅 تاریخ کاری",
        key_prefix="manager_work_date",
        default_gregorian=date.today(),
    )

    snapshot, kpis, pending_queue = _get_operational_snapshot_and_kpis(work_date)
    is_locked = bool(snapshot["is_locked"])

    if is_locked:
        st.warning(
            "این تاریخ قبلاً منتشر/ثبت عملیاتی شده و فعلاً در حالت فقط‌مشاهده است. "
            "برای بازتولید مسیر باید از بخش پاک‌سازی کامل همین تاریخ استفاده شود."
        )

    with st.expander("اعمال فایل‌ها و ساخت مسیر", expanded=not is_locked):
        st.markdown(
            """
            <div class="panel-description">
                با آپلود فایل فروشگاه‌ها، اطلاعات فروشگاه‌ها به‌روزرسانی می‌شود.<br/>
                با آپلود فایل وضعیت روزانه ویزیتورها، ظرفیت و نقطه شروع هر ویزیتور ثبت می‌شود و مسیرها برای همان تاریخ دوباره طراحی می‌شوند.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="panel-description-columns">
                ستون‌های الزامی فایل وضعیت روزانه:
                <span class="ltr-inline">work_date, username, visitor_code, full_name, start_lat, start_lon, capacity, is_active_today</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            stores_file = st.file_uploader(
                "فایل فروشگاه‌ها (اختیاری)",
                type=["xlsx"],
                key=f"stores_apply_{work_date.isoformat()}",
                disabled=is_locked,
            )
        with c2:
            daily_file = st.file_uploader(
                "فایل وضعیت روزانه ویزیتورها (اجباری)",
                type=["xlsx"],
                key=f"daily_apply_{work_date.isoformat()}",
                disabled=is_locked,
            )

        if st.button(
            "اعمال فایل‌ها و ساخت مسیر",
            key=f"build_pipeline_{work_date.isoformat()}",
            use_container_width=True,
            disabled=is_locked,
        ):
            with st.spinner("در حال اعمال فایل‌ها، تولید تخصیص و ساخت مسیر..."):
                try:
                    result = _run_apply_files_and_build_route(
                        work_date=work_date,
                        current_user=current_user,
                        stores_file=stores_file,
                        daily_file=daily_file,
                    )
                    st.session_state["manager_last_pipeline_result"] = result
                except Exception as exc:
                    st.error(f"خطا در ساخت مسیر: {exc}")
                else:
                    _render_pipeline_result(result)
                    st.rerun()

        last_result = st.session_state.get("manager_last_pipeline_result")
        if isinstance(last_result, dict):
            _render_pipeline_result(last_result)

    with st.expander("پاک‌سازی کامل داده‌های همین تاریخ", expanded=False):
        st.markdown(
            """
            <div class="panel-description">
                این عملیات همه داده‌های تخصیص، ویزیت و پیگیری فروش تلفنی مربوط به همین تاریخ را حذف می‌کند
                و وضعیت برنامه‌ریزی فروشگاه‌ها را از تاریخچه باقی‌مانده بازسازی می‌کند.
            </div>
            """,
            unsafe_allow_html=True,
        )
        confirm_flush = st.checkbox(
            "تأیید می‌کنم پاکسازی کامل فقط برای همین تاریخ انجام شود.",
            key=f"confirm_flush_{work_date.isoformat()}",
        )
        if st.button(
            "پاک‌سازی کامل همین تاریخ",
            key=f"flush_{work_date.isoformat()}",
            use_container_width=True,
            disabled=not confirm_flush,
        ):
            db = get_db_session()
            try:
                result = assignment_service.flush_work_date_operational_data(
                    db=db,
                    work_date=work_date,
                    manager_user_id=current_user["id"],
                )
                st.success(
                    "پاک‌سازی انجام شد: "
                    f"assignments={result['assignments_deleted']} | "
                    f"visits={result['visits_deleted']} | "
                    f"followups={result['followups_deleted']}"
                )
                st.session_state.pop("manager_last_pipeline_result", None)
                st.rerun()
            except Exception as exc:
                st.error(f"خطا در پاک‌سازی: {exc}")
            finally:
                db.close()

    neu_section_header("عملیات مدیریتی")
    op1, op2 = st.columns(2)

    with op1:
        if st.button(
            "📤 انتشار مسیرها",
            key=f"publish_{work_date.isoformat()}",
            use_container_width=True,
            disabled=is_locked,
        ):
            db = get_db_session()
            try:
                count = assignment_service.publish_assignments(
                    db=db,
                    work_date=work_date,
                    manager_user_id=current_user["id"],
                )
                st.success(f"{count} تخصیص منتشر شد.")
                st.rerun()
            except Exception as exc:
                st.error(f"خطا در انتشار مسیرها: {exc}")
            finally:
                db.close()

    with op2:
        if st.button(
            "🔒 نهایی‌سازی موارد ثبت‌نشده",
            key=f"finalize_{work_date.isoformat()}",
            use_container_width=True,
            disabled=is_locked,
        ):
            db = get_db_session()
            try:
                count = visit_service.finalize_unsubmitted_assignments(
                    db=db,
                    work_date=work_date,
                    actor_user_id=current_user["id"],
                )
                st.success(f"{count} تخصیص ثبت‌نشده به‌صورت خودکار قرمز شد.")
                st.rerun()
            except Exception as exc:
                st.error(f"خطا در نهایی‌سازی: {exc}")
            finally:
                db.close()

    neu_section_header("شاخص‌های روزانه")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        neu_metric("صف تامین‌پذیر", kpis["due_stores"])
    with k2:
        neu_metric("سبز / زرد / قرمز", f"{kpis['green']} / {kpis['yellow']} / {kpis['red']}")
    with k3:
        neu_metric("ویزیت تکمیل‌شده", kpis["completed_visits"])
    with k4:
        neu_metric("تخصیص‌شده", kpis["assigned_stores"])
    with k5:
        neu_metric("در انتظار تماس تلفنی", kpis["telesales_queue_size"])

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    neu_section_header("جدول تخصیص‌ها")
    assignment_df = _load_assignments(work_date)
    if assignment_df.empty:
        st.info("برای این تاریخ تخصیصی وجود ندارد.")
    else:
        st.dataframe(assignment_df, use_container_width=True)

    neu_section_header("صف در انتظار تماس تلفنی")
    if pending_queue:
        st.dataframe(pd.DataFrame(pending_queue), use_container_width=True)
    else:
        st.info("موردی در صف انتظار تماس تلفنی وجود ندارد.")

    visitor_options = _get_visitor_options(work_date)
    neu_section_header("نقشه مسیر")
    selected_code = st.selectbox(
        "انتخاب ویزیتور برای نمایش نقشه و دانلود مسیر",
        options=[""] + list(visitor_options.keys()),
        key=f"manager_map_visitor_{work_date.isoformat()}",
    )

    if selected_code:
        selected_id = visitor_options[selected_code]
        route_df = _load_visitor_route_map(work_date, selected_id)
        if route_df.empty:
            st.info("برای ویزیتور انتخاب‌شده مسیری ثبت نشده است.")
        else:
            render_route_map(route_df)

    neu_section_header("خروجی‌ها")
    ex1, ex2 = st.columns(2)

    with ex1:
        if selected_code:
            db = get_db_session()
            try:
                route_buf = reporting_export_service.export_visitor_route_excel(
                    db=db,
                    work_date=work_date,
                    visitor_id=visitor_options[selected_code],
                )
                st.download_button(
                    label=f"📥 دانلود مسیر {selected_code}",
                    data=route_buf.getvalue(),
                    file_name=f"route_{work_date.isoformat()}_{selected_code}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            finally:
                db.close()

    with ex2:
        db = get_db_session()
        try:
            summary_buf = reporting_export_service.export_manager_daily_summary_excel(
                db=db,
                work_date=work_date,
            )
        finally:
            db.close()

        st.download_button(
            label="📥 دانلود گزارش کامل روزانه",
            data=summary_buf.getvalue(),
            file_name=f"summary_{work_date.isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
