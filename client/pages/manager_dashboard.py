# Purpose: Manager dashboard with route pipeline, governance controls, and operational monitoring.
# Workflow Role: Main control plane for manager actions in the daily planning lifecycle.

from __future__ import annotations

import os
from datetime import date
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from client.components.empty_state import get_empty_state_message
from client.components.jalali_date import jalali_date_input
from client.components.rtl_table import render_rtl_table
from client.components.route_map import render_route_map
from client.styles.neumorphism import neu_section_header, render_metric_grid, render_page_title
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
from server.db.database import get_db


def _save_uploaded_excel(uploaded_file) -> str | None:
    if uploaded_file is None:
        return None
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


@st.cache_data(ttl=300, show_spinner=False)
def _cached_operational_snapshot(work_date_iso: str) -> tuple[dict, dict, list[dict]]:
    # FIX: [ARCH-03] Cache heavy read path and reduce repeated due-store recalculation cost.
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        snapshot = assignment_service.get_work_date_operational_snapshot(db, work_date)
        kpis = reporting_export_service.get_daily_kpis(db, work_date)
        pending_queue = telesales_service.list_pending_followups(db, as_of_date=work_date)
    return snapshot, kpis, pending_queue


@st.cache_data(ttl=300, show_spinner=False)
def _cached_assignments(work_date_iso: str) -> pd.DataFrame:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return dashboard_query_service.load_manager_assignments_df(db=db, work_date=work_date)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_visitor_options(work_date_iso: str) -> dict[str, int]:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return dashboard_query_service.get_visitor_options(db=db, work_date=work_date)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_route_map(work_date_iso: str, visitor_id: int) -> pd.DataFrame:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return dashboard_query_service.load_route_map_df(
            db=db,
            work_date=work_date,
            visitor_id=visitor_id,
        )


def _run_apply_files_and_build_route(
    work_date: date,
    current_user: dict,
    stores_file,
    daily_file,
) -> dict:
    # FIX: [UX-06] Expose granular pipeline progress with checklist + progress bar.
    if daily_file is None:
        raise ValueError("برای ساخت مسیر، بارگذاری فایل وضعیت روزانه الزامی است.")

    stores_path = _save_uploaded_excel(stores_file)
    daily_path = _save_uploaded_excel(daily_file)

    try:
        with st.status("در حال اجرای پایپلاین ساخت مسیر...", expanded=True) as status:
            checklist_box = st.empty()
            progress_box = st.empty()
            progress_note_box = st.empty()
            total_steps = 5
            completed_steps = 0
            assigned_count = 0
            unassigned_count = 0
            progress_reason = "این نوار پیشرفت مربوط به فرآیند تولید تخصیص و ساخت مسیر است."
            step_order = [
                ("stores", "بارگذاری فایل فروشگاه‌ها"),
                ("daily", "ثبت وضعیت روزانه ویزیتورها"),
                ("assign", "تولید تخصیص‌ها"),
                ("route", "مرتب‌سازی مسیرها"),
                ("quality", "ارزیابی کیفیت مسیر"),
            ]
            step_state = {step_id: "pending" for step_id, _ in step_order}
            step_text = {step_id: label for step_id, label in step_order}

            def _render_progress() -> None:
                pct = min(100, int((completed_steps / total_steps) * 100))
                progress_box.markdown(
                    f"""
                    <div class="pipeline-progress-wrap">
                        <div class="pipeline-progress-label">درصد پیشرفت ساخت مسیر و تخصیص: {pct}٪</div>
                        <div class="pipeline-progress-track">
                            <div class="pipeline-progress-fill" style="width:{pct}%;"></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                progress_note_box.markdown(
                    (
                        '<div class="pipeline-progress-note">'
                        f'نکته: از {assigned_count + unassigned_count} فروشگاه قابل ویزیت، '
                        f'{assigned_count} فروشگاه تخصیص یافته و {unassigned_count} فروشگاه تخصیص نیافته است.'
                        "<br/>"
                        f'دلیل: {progress_reason}'
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )

            def _render_steps() -> None:
                status_map = {
                    "pending": "در انتظار",
                    "running": '<span class="hourglass-spin">⏳</span> در حال اجرا',
                    "done": "انجام شد",
                    "warn": "پایان با هشدار",
                }
                lines: list[str] = []
                for index, (step_id, _) in enumerate(step_order, start=1):
                    lines.append(
                        f"{index}. {step_text[step_id]} — {status_map.get(step_state.get(step_id, 'pending'), 'در انتظار')}"
                    )
                checklist_box.markdown(
                    f'<div class="pipeline-checklist-right">{"<br/>".join(lines)}</div>',
                    unsafe_allow_html=True,
                )

            def _set_step(
                step_id: str,
                state: str,
                message: str | None = None,
                mark_complete: bool = False,
            ) -> None:
                nonlocal completed_steps
                step_state[step_id] = state
                if message is not None:
                    step_text[step_id] = message
                _render_steps()
                if mark_complete:
                    completed_steps += 1
                _render_progress()

            _render_steps()
            _render_progress()

            with get_db() as db:
                stores_processed = 0
                if stores_path:
                    stores_processed = import_service.import_stores_from_excel(stores_path, db)
                    _set_step("stores", "done", f"فروشگاه‌ها بارگذاری شدند ({stores_processed} ردیف)", mark_complete=True)
                else:
                    # Optional input still counts as finished step for progress continuity.
                    _set_step("stores", "done", "فایل فروشگاه جدیدی بارگذاری نشد.", mark_complete=True)

                daily_processed = import_daily_visitor_statuses_from_excel(daily_path, db)
                _set_step("daily", "done", f"وضعیت روزانه ویزیتورها ثبت شد ({daily_processed} نفر)", mark_complete=True)

                status_count_for_selected_date = dashboard_query_service.get_daily_status_row_count(
                    db=db,
                    work_date=work_date,
                )
                if status_count_for_selected_date <= 0:
                    raise ValueError(
                        "فایل وضعیت روزانه برای تاریخ انتخاب‌شده ردیفی ندارد. تاریخ کاری را با work_date فایل یکسان کنید."
                    )

                _set_step("assign", "running", "در حال تولید تخصیص‌ها...")
                draft_summary = assignment_service.generate_draft_assignments(
                    db=db,
                    work_date=work_date,
                    manager_user_id=current_user["id"],
                    replace_existing_draft=True,
                )
                _set_step(
                    "assign",
                    "done",
                    (
                        f"{draft_summary.get('created_assignments', 0)} تخصیص ساخته شد | "
                        f"{draft_summary.get('unassigned_due_stores', 0)} فروشگاه تخصیص نیافت"
                    ),
                    mark_complete=True,
                )
                assigned_count = int(draft_summary.get("created_assignments", 0))
                unassigned_count = int(draft_summary.get("unassigned_due_stores", 0))
                if unassigned_count > 0:
                    progress_reason = (
                        "مجموع ظرفیت روزانه ویزیتورهای فعال کمتر از تعداد فروشگاه‌های قابل ویزیت بوده است."
                    )
                else:
                    progress_reason = "همه فروشگاه‌های قابل ویزیت در ظرفیت روزانه پوشش داده شدند."
                _render_progress()

                route_summary = routing_service.apply_routes_for_work_date(
                    db=db,
                    work_date=work_date,
                    planner=routing_service.OSRMRoutePlanner(
                        fallback_planner=routing_service.NearestNeighborRoutePlanner(),
                    ),
                )
                if route_summary["osrm_used"]:
                    _set_step("route", "done", "مسیرها با OSRM بهینه شدند.", mark_complete=True)
                else:
                    _set_step("route", "warn", "OSRM در دسترس نبود؛ از الگوریتم پشتیبان استفاده شد.", mark_complete=True)

                quality = assignment_service.evaluate_route_quality_vs_round_robin(
                    db=db,
                    work_date=work_date,
                )
                _set_step(
                    "quality",
                    "done",
                    f"کیفیت مسیر: بهبود {quality['improvement_pct']}٪ نسبت به تخصیص مبنا",
                    mark_complete=True,
                )
                status.update(label="پایپلاین با موفقیت انجام شد.", state="complete")

            return {
                "stores_processed": stores_processed,
                "daily_processed": daily_processed,
                "draft_summary": draft_summary,
                "route_summary": route_summary,
                "quality": quality,
                "osrm_used": bool(route_summary["osrm_used"]),
            }
    finally:
        for path in [stores_path, daily_path]:
            if path and os.path.exists(path):
                os.remove(path)


def _render_pipeline_result(result: dict) -> None:
    draft_summary = result.get("draft_summary", {})
    quality = result.get("quality", {"baseline_km": 0.0, "current_km": 0.0, "improvement_pct": 0.0, "passes_gate": False})
    route_summary = result.get(
        "route_summary",
        {
            "total_assignments": int(result.get("routed_count", 0)),
            "osrm_routed": 0,
            "nn_routed": 0,
            "osrm_used": False,
        },
    )

    st.success(
        "فایل‌ها اعمال شد و مسیرها ساخته شدند. "
        f"فروشگاه پردازش‌شده: {result['stores_processed']} | "
        f"وضعیت روزانه پردازش‌شده: {result['daily_processed']} | "
        f"تخصیص ساخته‌شده: {draft_summary.get('created_assignments', 0)} | "
        f"مرتب‌سازی مسیر: {route_summary.get('total_assignments', 0)}"
    )

    comparable = not (
        int(route_summary.get("osrm_routed", 0)) == 0 and int(route_summary.get("nn_routed", 0)) > 0
    )
    gate_text = "قابل مقایسه نیست" if not comparable else ("قبول" if quality["passes_gate"] else "رد")

    render_metric_grid(
        [
            ("مسافت مسیر مبنا (قبل از بهینه‌سازی) (km)", quality["baseline_km"]),
            ("مسافت مسیر فعلی (بعد از بهینه‌سازی) (km)", quality["current_km"]),
            ("درصد بهبود مسیر", f"{quality['improvement_pct']}%"),
            ("گیت کیفیت", gate_text),
        ]
    )
    st.caption(
        f"مسیر {route_summary.get('osrm_routed', 0)} ویزیتور با OSRM | "
        f"{route_summary.get('nn_routed', 0)} ویزیتور با الگوریتم پشتیبان"
    )
    if comparable and not quality["passes_gate"]:
        st.warning("گیت کیفیت عبور نکرده است. بهبود مسیر باید حداقل ۲۰٪ نسبت به مقدار مبنا باشد.")


def render_manager_dashboard(current_user: dict) -> None:
    render_page_title("داشبورد مدیر")

    work_date = jalali_date_input(
        label="📅 تاریخ کاری",
        key_prefix="manager_work_date",
        default_gregorian=date.today(),
    )
    work_date_iso = work_date.isoformat()

    # FIX: [BIZ-02] Avoid stale pipeline result after work-date change.
    stored_date = st.session_state.get("manager_last_pipeline_date")
    if stored_date and stored_date != work_date_iso:
        st.session_state.pop("manager_last_pipeline_result", None)
        st.session_state.pop("manager_last_pipeline_date", None)

    snapshot, kpis, pending_queue = _cached_operational_snapshot(work_date_iso)
    visit_count = int(snapshot.get("visit_count", 0))
    followup_count = int(snapshot.get("followup_count", 0))
    published_count = int(snapshot.get("published_count", 0))
    non_draft_count = int(snapshot.get("non_draft_count", 0))
    assignment_count = int(snapshot.get("assignment_count", 0))

    # FIX: Allow upload/flush when only publish lock exists and no operational records are created yet.
    is_hard_locked = visit_count > 0 or followup_count > 0
    is_soft_locked = (not is_hard_locked) and non_draft_count > 0

    if is_hard_locked or is_soft_locked:
        st.warning(
            "این تاریخ قفل است: "
            f"{visit_count} ویزیت ثبت‌شده | "
            f"{followup_count} پیگیری فعال | "
            f"{published_count} تخصیص منتشرشده"
        )
    if is_soft_locked:
        st.info("برای این تاریخ هنوز ویزیت/پیگیری ثبت نشده است. می‌توانید پاک‌سازی کامل انجام دهید و دوباره فایل آپلود کنید.")

    with st.expander("اعمال فایل‌ها و ساخت مسیر", expanded=not is_hard_locked):
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
                key=f"stores_apply_{work_date_iso}",
                disabled=is_hard_locked,
            )
        with c2:
            daily_file = st.file_uploader(
                "فایل وضعیت روزانه ویزیتورها (اجباری)",
                type=["xlsx"],
                key=f"daily_apply_{work_date_iso}",
                disabled=is_hard_locked,
            )

        if st.button(
            "اعمال فایل‌ها و ساخت مسیر",
            key=f"build_pipeline_{work_date_iso}",
            use_container_width=True,
            disabled=is_hard_locked,
        ):
            if is_soft_locked:
                st.error("برای این تاریخ تخصیص منتشرشده وجود دارد. ابتدا «پاک‌سازی کامل همین تاریخ» را انجام دهید، سپس مسیر جدید بسازید.")
                st.stop()
            try:
                result = _run_apply_files_and_build_route(
                    work_date=work_date,
                    current_user=current_user,
                    stores_file=stores_file,
                    daily_file=daily_file,
                )
                st.session_state["manager_last_pipeline_result"] = result
                st.session_state["manager_last_pipeline_date"] = work_date_iso
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"خطا در ساخت مسیر: {exc}")

        last_result = st.session_state.get("manager_last_pipeline_result")
        if isinstance(last_result, dict):
            _render_pipeline_result(last_result)

    if visit_count == 0 and followup_count == 0:
        if st.button(
            "بازنشانی پیش‌نویس",
            key=f"reset_draft_only_{work_date_iso}",
            use_container_width=True,
            disabled=int(snapshot.get("draft_count", 0)) == 0,
        ):
            try:
                with get_db() as db:
                    result = assignment_service.reset_draft_assignments_for_date(
                        db=db,
                        work_date=work_date,
                        manager_user_id=current_user["id"],
                    )
                st.success(f"{result['deleted_draft_count']} تخصیص پیش‌نویس حذف شد.")
                st.session_state.pop("manager_last_pipeline_result", None)
                st.session_state.pop("manager_last_pipeline_date", None)
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"خطا در بازنشانی پیش‌نویس: {exc}")

    with st.expander("پاک‌سازی کامل داده‌های همین تاریخ", expanded=False):
        has_operational_data = visit_count > 0 or followup_count > 0
        has_any_daily_data = assignment_count > 0 or has_operational_data
        st.markdown(
            """
            <div class="panel-description">
                این عملیات همه داده‌های تخصیص، ویزیت و پیگیری فروش تلفنی مربوط به همین تاریخ را حذف می‌کند
                و باعث از دست رفتن سوابق عملیاتی همان روز می‌شود.
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not has_any_daily_data:
            st.info("برای این تاریخ داده عملیاتی یا تخصیصی ثبت نشده است.")
        elif not has_operational_data and has_any_daily_data:
            st.info("برای این تاریخ هنوز ویزیت یا پیگیری عملیاتی ثبت نشده است؛ پاک‌سازی کامل بدون از دست‌رفتن سابقه ویزیت انجام می‌شود.")
        confirm_flush = st.checkbox(
            "تأیید می‌کنم پاکسازی کامل فقط برای همین تاریخ انجام شود.",
            key=f"confirm_flush_{work_date_iso}",
        )
        if st.button(
            "پاک‌سازی کامل همین تاریخ",
            key=f"flush_{work_date_iso}",
            use_container_width=True,
            disabled=(not confirm_flush) or (not has_any_daily_data),
        ):
            try:
                with get_db() as db:
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
                st.session_state.pop("manager_last_pipeline_date", None)
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"خطا در پاک‌سازی: {exc}")

    neu_section_header("عملیات مدیریتی")
    op1, op2 = st.columns(2)

    with op1:
        if st.button(
            "📤 انتشار مسیرها",
            key=f"publish_{work_date_iso}",
            use_container_width=True,
            disabled=is_hard_locked,
        ):
            try:
                with get_db() as db:
                    count = assignment_service.publish_assignments(
                        db=db,
                        work_date=work_date,
                        manager_user_id=current_user["id"],
                        include_draft_override=True,
                    )
                st.success(f"{count} تخصیص منتشر شد.")
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"خطا در انتشار مسیرها: {exc}")

    with op2:
        if st.button(
            "🔒 نهایی‌سازی موارد ثبت‌نشده",
            key=f"finalize_{work_date_iso}",
            use_container_width=True,
            disabled=is_hard_locked,
        ):
            try:
                with get_db() as db:
                    count = visit_service.finalize_unsubmitted_assignments(
                        db=db,
                        work_date=work_date,
                        actor_user_id=current_user["id"],
                    )
                st.success(f"{count} تخصیص ثبت‌نشده به‌صورت خودکار قرمز شد.")
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"خطا در نهایی‌سازی: {exc}")

    neu_section_header("شاخص‌های روزانه")
    render_metric_grid(
        [
            ("صف تامین‌پذیر", kpis["due_stores"]),
            ("سبز / زرد / قرمز", f"{kpis['green']} / {kpis['yellow']} / {kpis['red']}"),
            ("ویزیت تکمیل‌شده", kpis["completed_visits"]),
            ("تخصیص‌شده", kpis["assigned_stores"]),
            ("در انتظار تماس تلفنی", kpis["telesales_queue_size"]),
        ]
    )
    if int(kpis.get("due_stores", 0)) == 0:
        st.info(get_empty_state_message(role="manager", context="no_due_stores"))

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    neu_section_header("جدول تخصیص‌ها")
    assignment_df = _cached_assignments(work_date_iso)
    if assignment_df.empty:
        st.info(get_empty_state_message(role="manager", context="no_assignments"))
    else:
        assignment_view_df = assignment_df.copy()
        # FIX: Show store grade in manager-generated assignment list for route review.
        if "store_grade" in assignment_view_df.columns:
            assignment_view_df["store_grade"] = assignment_view_df["store_grade"].fillna("نامشخص")
        render_rtl_table(
            assignment_view_df,
            key_prefix=f"manager_assignments_{work_date_iso}",
        )

    neu_section_header("صف در انتظار تماس تلفنی")
    if pending_queue:
        pending_df = pd.DataFrame(pending_queue)
        pending_df = pending_df.drop(columns=["store_lat", "store_lon"], errors="ignore")
        render_rtl_table(
            pending_df,
            key_prefix=f"manager_pending_telesales_{work_date_iso}",
        )
    else:
        st.info(get_empty_state_message(role="manager", context="no_pending_telesales"))

    visitor_options = _cached_visitor_options(work_date_iso)
    neu_section_header("نقشه مسیر")
    st.markdown(
        '<div class="panel-description" style="text-align:right !important;margin:0.1rem 0 0.35rem;">'
        "راهنما: در همین کادر انتخاب ویزیتور می‌توانید جست‌وجو کنید (نمونه: VIS-001 یا visitor1)."
        "</div>",
        unsafe_allow_html=True,
    )
    selected_code = st.selectbox(
        "انتخاب ویزیتور برای نمایش نقشه و دانلود مسیر",
        options=list(visitor_options.keys()),
        index=None,
        placeholder="ویزیتور را انتخاب یا جست‌وجو کنید...",
        key=f"manager_map_visitor_{work_date_iso}",
    )

    if selected_code:
        selected_id = visitor_options[selected_code]
        route_df = _cached_route_map(work_date_iso, selected_id)
        if route_df.empty:
            st.info(get_empty_state_message(role="manager", context="no_route_for_visitor"))
        else:
            render_route_map(route_df)

    neu_section_header("خروجی‌ها")
    ex1, ex2 = st.columns(2)
    with ex1:
        if selected_code:
            with get_db() as db:
                route_buf = reporting_export_service.export_visitor_route_excel(
                    db=db,
                    work_date=work_date,
                    visitor_id=visitor_options[selected_code],
                )
            st.download_button(
                label=f"📥 دانلود مسیر {selected_code}",
                data=route_buf.getvalue(),
                file_name=f"route_{work_date_iso}_{selected_code}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with ex2:
        with get_db() as db:
            summary_buf = reporting_export_service.export_manager_daily_summary_excel(
                db=db,
                work_date=work_date,
            )
        st.download_button(
            label="📥 دانلود گزارش کامل روزانه",
            data=summary_buf.getvalue(),
            file_name=f"summary_{work_date_iso}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
