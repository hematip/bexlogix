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
from client.i18n import align, direction, t
from client.components.rtl_table import render_rtl_table
from client.components.route_map import render_route_map
from client.styles.neumorphism import (
    neu_section_header,
    render_metric_grid,
    render_page_title,
)
from server.app.services import (
    assignment_service,
    dashboard_query_service,
    import_service,
    reporting_export_service,
    routing_service,
    runtime_health_service,
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


def _fallback_reason_text(reason: str | None) -> str:
    if reason == "vroom_timeout":
        return t("پاسخ VROOM در زمان مقرر دریافت نشد.", "VROOM response timed out.")
    if reason == "vroom_invalid_response":
        return t("پاسخ VROOM معتبر نبود.", "VROOM response was invalid.")
    if reason == "vroom_unavailable":
        return t("سرویس VROOM محلی در دسترس نبود.", "Local VROOM service was unavailable.")
    if reason == "osrm_timeout":
        return t("پاسخ OSRM در زمان مقرر دریافت نشد.", "OSRM response timed out.")
    if reason == "osrm_invalid_response":
        return t("پاسخ OSRM معتبر نبود.", "OSRM response was invalid.")
    if reason == "osrm_unavailable":
        return t("سرویس OSRM محلی در دسترس نبود.", "Local OSRM service was unavailable.")
    return t("دلیل دقیق fallback مشخص نیست.", "Exact fallback reason is unknown.")


def _runtime_health_caption(runtime_state: dict[str, object]) -> str:
    osrm_text = t("فعال", "UP") if bool(runtime_state.get("osrm_up", False)) else t("غیرفعال", "DOWN")
    tiles_text = t("فعال", "UP") if bool(runtime_state.get("tiles_up", False)) else t("غیرفعال", "DOWN")
    osrm_latency = runtime_state.get("osrm_latency_ms")
    tiles_latency = runtime_state.get("tiles_latency_ms")
    osrm_latency_text = f"{osrm_latency}ms" if osrm_latency is not None else "—"
    tiles_latency_text = f"{tiles_latency}ms" if tiles_latency is not None else "—"
    return t(
        f"پیش‌بررسی سرویس‌ها: OSRM={osrm_text} ({osrm_latency_text}) | Tile={tiles_text} ({tiles_latency_text})",
        f"Service precheck: OSRM={osrm_text} ({osrm_latency_text}) | Tile={tiles_text} ({tiles_latency_text})",
    )


@st.cache_data(ttl=300, show_spinner=False)
def _cached_operational_snapshot(work_date_iso: str) -> tuple[dict, dict, list[dict]]:
    # FIX: [ARCH-03] Cache heavy read path and reduce repeated due-store recalculation cost.
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        snapshot = assignment_service.get_work_date_operational_snapshot(db, work_date)
        kpis = reporting_export_service.get_daily_kpis(db, work_date)
        pending_queue = telesales_service.list_pending_followups(
            db, as_of_date=work_date
        )
    return snapshot, kpis, pending_queue


@st.cache_data(ttl=300, show_spinner=False)
def _cached_assignments(work_date_iso: str) -> pd.DataFrame:
    work_date = date.fromisoformat(work_date_iso)
    with get_db() as db:
        return dashboard_query_service.load_manager_assignments_df(
            db=db, work_date=work_date
        )


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
        raise ValueError(t("برای ساخت مسیر، بارگذاری فایل وضعیت روزانه الزامی است.", "Daily status file upload is required to build routes."))

    stores_path = _save_uploaded_excel(stores_file)
    daily_path = _save_uploaded_excel(daily_file)

    try:
        with st.status(t("در حال اجرای پایپلاین ساخت مسیر...", "Running route build pipeline..."), expanded=True) as status:
            checklist_box = st.empty()
            progress_box = st.empty()
            progress_note_box = st.empty()
            total_steps = 5
            completed_steps = 0
            assigned_count = 0
            unassigned_count = 0
            progress_reason = (
                t("این نوار پیشرفت مربوط به فرآیند تولید تخصیص و ساخت مسیر است.", "This progress bar tracks assignment generation and route building.")
            )
            step_order = [
                ("stores", t("بارگذاری فایل فروشگاه‌ها", "Upload store file")),
                ("daily", t("ثبت وضعیت روزانه ویزیتورها", "Register daily visitor status")),
                ("assign", t("تولید تخصیص‌ها", "Generate assignments")),
                ("route", t("مرتب‌سازی مسیرها", "Route ordering")),
                ("quality", t("ارزیابی کیفیت مسیر", "Route quality evaluation")),
            ]
            step_state = {step_id: "pending" for step_id, _ in step_order}
            step_text = {step_id: label for step_id, label in step_order}

            def _render_progress() -> None:
                pct = min(100, int((completed_steps / total_steps) * 100))
                progress_box.markdown(
                    f"""
                    <div class="pipeline-progress-wrap">
                        <div class="pipeline-progress-label">{t("درصد پیشرفت ساخت مسیر و تخصیص", "Assignment & route progress")}: {pct}%</div>
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
                        + t(
                            f"نکته: از {assigned_count + unassigned_count} فروشگاه قابل ویزیت، "
                            f"{assigned_count} فروشگاه تخصیص یافته و {unassigned_count} فروشگاه تخصیص نیافته است.",
                            f"Note: out of {assigned_count + unassigned_count} due stores, "
                            f"{assigned_count} were assigned and {unassigned_count} remained unassigned.",
                        )
                        + "<br/>"
                        + t(f"دلیل: {progress_reason}", f"Reason: {progress_reason}")
                        + "</div>"
                    ),
                    unsafe_allow_html=True,
                )

            def _render_steps() -> None:
                status_map = {
                    "pending": t("در انتظار", "Pending"),
                    "running": t('<span class="hourglass-spin">⏳</span> در حال اجرا', '<span class="hourglass-spin">⏳</span> Running'),
                    "done": t("انجام شد", "Done"),
                    "warn": t("پایان با هشدار", "Completed with warning"),
                }
                lines: list[str] = []
                for index, (step_id, _) in enumerate(step_order, start=1):
                    lines.append(
                        f"{index}. {step_text[step_id]} — {status_map.get(step_state.get(step_id, 'pending'), t('در انتظار', 'Pending'))}"
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
                    stores_processed = import_service.import_stores_from_excel(
                        stores_path, db
                    )
                    _set_step(
                        "stores",
                        "done",
                        t(f"فروشگاه‌ها بارگذاری شدند ({stores_processed} ردیف)", f"Store file imported ({stores_processed} rows)"),
                        mark_complete=True,
                    )
                else:
                    # Optional input still counts as finished step for progress continuity.
                    _set_step(
                        "stores",
                        "done",
                        t("فایل فروشگاه جدیدی بارگذاری نشد.", "No new store file was uploaded."),
                        mark_complete=True,
                    )

                daily_processed = import_daily_visitor_statuses_from_excel(
                    daily_path, db
                )
                _set_step(
                    "daily",
                    "done",
                    t(f"وضعیت روزانه ویزیتورها ثبت شد ({daily_processed} نفر)", f"Daily visitor status imported ({daily_processed} users)"),
                    mark_complete=True,
                )

                status_count_for_selected_date = (
                    dashboard_query_service.get_daily_status_row_count(
                        db=db,
                        work_date=work_date,
                    )
                )
                if status_count_for_selected_date <= 0:
                    raise ValueError(
                        t(
                            "فایل وضعیت روزانه برای تاریخ انتخاب‌شده ردیفی ندارد. تاریخ کاری را با work_date فایل یکسان کنید.",
                            "The daily status file has no rows for the selected date. Match the work date with the file's work_date.",
                        )
                    )

                _set_step("assign", "running", t("در حال تولید تخصیص‌ها...", "Generating assignments..."))
                draft_summary = assignment_service.generate_draft_assignments(
                    db=db,
                    work_date=work_date,
                    manager_user_id=current_user["id"],
                    replace_existing_draft=True,
                )
                _set_step(
                    "assign",
                    "done",
                    t(
                        f"{draft_summary.get('created_assignments', 0)} تخصیص ساخته شد | "
                        f"{draft_summary.get('unassigned_due_stores', 0)} فروشگاه تخصیص نیافت",
                        f"{draft_summary.get('created_assignments', 0)} assignments created | "
                        f"{draft_summary.get('unassigned_due_stores', 0)} stores unassigned",
                    ),
                    mark_complete=True,
                )
                assigned_count = int(draft_summary.get("created_assignments", 0))
                unassigned_count = int(draft_summary.get("unassigned_due_stores", 0))
                if unassigned_count > 0:
                    progress_reason = t(
                        "مجموع ظرفیت روزانه ویزیتورهای فعال کمتر از تعداد فروشگاه‌های قابل ویزیت بوده است.",
                        "Total daily capacity of active visitors is lower than the number of due stores.",
                    )
                else:
                    progress_reason = t(
                        "همه فروشگاه‌های قابل ویزیت در ظرفیت روزانه پوشش داده شدند.",
                        "All due stores were covered within daily visitor capacity.",
                    )
                _render_progress()

                # FIX: [PERF-05] Preflight local runtime health once and keep route step fail-fast.
                runtime_state = runtime_health_service.get_offline_runtime_status(
                    force_refresh=True
                )
                st.markdown(
                    f'<div class="panel-description" style="text-align:{align()} !important;margin:.25rem 0;">{_runtime_health_caption(runtime_state)}</div>',
                    unsafe_allow_html=True,
                )
                if not bool(runtime_state.get("osrm_data_ready", False)):
                    st.warning(
                        t(
                            "فایل داده OSRM پیدا نشد. مسیر مورد انتظار: offline/osrm/data/tehran-latest.osrm",
                            "OSRM data file not found. Expected path: offline/osrm/data/tehran-latest.osrm",
                        )
                    )
                if not bool(runtime_state.get("tiles_data_ready", False)):
                    st.info(
                        t(
                            "فایل MBTiles پیدا نشد. مسیر مورد انتظار: offline/tiles/data/*.mbtiles",
                            "MBTiles file not found. Expected path: offline/tiles/data/*.mbtiles",
                        )
                    )
                route_summary: dict
                routes_precomputed = bool(draft_summary.get("routes_precomputed"))
                if routes_precomputed:
                    route_summary = dict(draft_summary.get("route_summary") or {})
                    route_summary.setdefault(
                        "total_assignments",
                        int(draft_summary.get("created_assignments", 0)),
                    )
                    route_summary.setdefault("total_visitors", 0)
                    route_summary.setdefault("osrm_routed", 0)
                    route_summary.setdefault("nn_routed", 0)
                    route_summary.setdefault("vroom_routed", 0)
                    route_summary.setdefault("vroom_used", True)
                    route_summary.setdefault("osrm_used", False)
                    route_summary.setdefault(
                        "solver_mode",
                        str(draft_summary.get("solver_mode") or "vroom"),
                    )
                    route_summary.setdefault(
                        "fallback_stage",
                        draft_summary.get("fallback_stage"),
                    )
                    route_summary.setdefault(
                        "solver_reason",
                        draft_summary.get("solver_reason"),
                    )
                    route_summary.setdefault("fallback_reason", None)
                    _set_step(
                        "route",
                        "done",
                        t("مسیرها با VROOM+OSRM آفلاین ساخته شدند.", "Routes were built by offline VROOM+OSRM."),
                        mark_complete=True,
                    )
                else:
                    if runtime_state.get("osrm_up", False):
                        route_planner = routing_service.OSRMRoutePlanner(
                            fallback_planner=routing_service.NearestNeighborRoutePlanner(),
                            runtime_status=runtime_state,
                        )
                        _set_step(
                            "route", "running", t("در حال مرتب‌سازی مسیرها با OSRM محلی...", "Ordering routes with local OSRM...")
                        )
                    else:
                        route_planner = routing_service.NearestNeighborRoutePlanner()
                        _set_step(
                            "route",
                            "running",
                            t(
                                "OSRM محلی در دسترس نیست؛ مرتب‌سازی با الگوریتم پشتیبان انجام می‌شود...",
                                "Local OSRM is unavailable; route ordering will use fallback algorithm...",
                            ),
                        )

                    route_summary = routing_service.apply_routes_for_work_date(
                        db=db,
                        work_date=work_date,
                        planner=route_planner,
                    )
                    if draft_summary.get("fallback_stage"):
                        route_summary["fallback_stage"] = draft_summary.get(
                            "fallback_stage"
                        )
                    if draft_summary.get("solver_reason"):
                        route_summary["solver_reason"] = draft_summary.get(
                            "solver_reason"
                        )
                    route_summary["solver_mode"] = str(
                        route_summary.get("solver_mode")
                        or draft_summary.get("solver_mode")
                        or "legacy"
                    )

                    if route_summary["osrm_used"]:
                        _set_step(
                            "route",
                            "done",
                            t("مسیرها با OSRM بهینه شدند.", "Routes were optimized with OSRM."),
                            mark_complete=True,
                        )
                    else:
                        fallback_reason = (
                            route_summary.get("fallback_reason")
                            or route_summary.get("solver_reason")
                        )
                        _set_step(
                            "route",
                            "warn",
                            t(
                                f"از الگوریتم پشتیبان استفاده شد. ({_fallback_reason_text(fallback_reason)})",
                                f"Fallback algorithm used. ({_fallback_reason_text(fallback_reason)})",
                            ),
                            mark_complete=True,
                        )

                quality = assignment_service.evaluate_route_quality_vs_round_robin(
                    db=db,
                    work_date=work_date,
                )
                _set_step(
                    "quality",
                    "done",
                    t(
                        f"کیفیت مسیر: بهبود {quality['improvement_pct']}٪ نسبت به تخصیص مبنا",
                        f"Route quality: {quality['improvement_pct']}% improvement vs baseline assignment",
                    ),
                    mark_complete=True,
                )
                status.update(label=t("پایپلاین با موفقیت انجام شد.", "Pipeline completed successfully."), state="complete")

            return {
                "stores_processed": stores_processed,
                "daily_processed": daily_processed,
                "draft_summary": draft_summary,
                "route_summary": route_summary,
                "quality": quality,
                "osrm_used": bool(route_summary["osrm_used"]),
                "shadow": draft_summary.get("shadow"),
                "runtime_status": runtime_state,
            }
    finally:
        for path in [stores_path, daily_path]:
            if path and os.path.exists(path):
                os.remove(path)


def _render_pipeline_result(result: dict) -> None:
    draft_summary = result.get("draft_summary", {})
    quality = result.get(
        "quality",
        {
            "baseline_km": 0.0,
            "current_km": 0.0,
            "improvement_pct": 0.0,
            "passes_gate": False,
        },
    )
    route_summary = result.get(
        "route_summary",
        {
            "total_assignments": int(result.get("routed_count", 0)),
            "osrm_routed": 0,
            "nn_routed": 0,
            "vroom_routed": 0,
            "vroom_used": False,
            "osrm_used": False,
            "solver_mode": "legacy",
            "fallback_stage": None,
            "solver_reason": None,
            "fallback_reason": None,
        },
    )
    solver_mode = str(
        route_summary.get("solver_mode") or draft_summary.get("solver_mode") or "legacy"
    ).strip()
    fallback_stage = route_summary.get("fallback_stage") or draft_summary.get(
        "fallback_stage"
    )
    solver_reason = route_summary.get("solver_reason") or draft_summary.get(
        "solver_reason"
    )

    st.success(
        t(
            "فایل‌ها اعمال شد و مسیرها ساخته شدند. "
            f"فروشگاه پردازش‌شده: {result['stores_processed']} | "
            f"وضعیت روزانه پردازش‌شده: {result['daily_processed']} | "
            f"تخصیص ساخته‌شده: {draft_summary.get('created_assignments', 0)} | "
            f"مرتب‌سازی مسیر: {route_summary.get('total_assignments', 0)}",
            "Files were applied and routes were built. "
            f"Stores processed: {result['stores_processed']} | "
            f"Daily status processed: {result['daily_processed']} | "
            f"Assignments created: {draft_summary.get('created_assignments', 0)} | "
            f"Routes ordered: {route_summary.get('total_assignments', 0)}",
        )
    )

    comparable = not (
        int(route_summary.get("osrm_routed", 0)) == 0
        and int(route_summary.get("nn_routed", 0)) > 0
        and solver_mode != "vroom"
    )
    gate_text = (
        t("قابل مقایسه نیست", "Not comparable")
        if not comparable
        else (t("قبول", "Pass") if quality["passes_gate"] else t("رد", "Fail"))
    )

    render_metric_grid(
        [
            (t("مسافت مسیر مبنا (قبل از بهینه‌سازی) (km)", "Baseline Route Distance (Before Optimization) (km)"), quality["baseline_km"]),
            (t("مسافت مسیر فعلی (بعد از بهینه‌سازی) (km)", "Current Route Distance (After Optimization) (km)"), quality["current_km"]),
            (t("درصد بهبود مسیر", "Route Improvement (%)"), f"{quality['improvement_pct']}%"),
            (t("وضعیت", "Status"), gate_text),
        ]
    )
    if solver_mode == "vroom":
        route_mode_text = t(
            f"مسیر {route_summary.get('vroom_routed', 0)} ویزیتور با VROOM+OSRM آفلاین",
            f"Routed {route_summary.get('vroom_routed', 0)} visitors with offline VROOM+OSRM",
        )
    else:
        route_mode_text = t(
            f"مسیر {route_summary.get('osrm_routed', 0)} ویزیتور با OSRM | "
            f"{route_summary.get('nn_routed', 0)} ویزیتور با الگوریتم پشتیبان",
            f"Routed {route_summary.get('osrm_routed', 0)} visitors with OSRM | "
            f"{route_summary.get('nn_routed', 0)} visitors with fallback algorithm",
        )
    st.markdown(
        (
            f'<div style="direction:{direction()};text-align:{align()};color:#6B7280;font-size:.85rem;margin-top:.1rem;">'
            f"{route_mode_text}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    if fallback_stage == "vroom_to_legacy":
        st.markdown(
            (
                f'<div style="direction:{direction()};text-align:{align()};color:#6B7280;font-size:.85rem;margin-top:.05rem;">'
                + t("fallback مرحله اول: ", "First-stage fallback: ")
                + f"VROOM -> Legacy ({_fallback_reason_text(solver_reason)})"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    if int(route_summary.get("nn_routed", 0)) > 0:
        st.markdown(
            (
                f'<div style="direction:{direction()};text-align:{align()};color:#6B7280;font-size:.85rem;margin-top:.05rem;">'
                + t("دلیل fallback: ", "Fallback reason: ")
                + f"{_fallback_reason_text(route_summary.get('fallback_reason'))}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    if (
        int(route_summary.get("osrm_routed", 0)) == 0
        and int(route_summary.get("nn_routed", 0)) > 0
        and solver_mode != "vroom"
    ):
        runtime_state = result.get("runtime_status") or {}
        reason_text = _fallback_reason_text(route_summary.get("fallback_reason"))
        if bool(runtime_state.get("osrm_up", False)):
            st.warning(
                t(
                    f"OSRM پاسخ قابل استفاده نداد و مسیرها با الگوریتم پشتیبان ساخته شدند. {reason_text}",
                    f"OSRM did not return usable responses, so routes were built with fallback algorithm. {reason_text}",
                )
            )
        else:
            st.warning(
                t(
                    f"OSRM محلی در دسترس نبوده و مسیرها با الگوریتم پشتیبان ساخته شده‌اند. {reason_text}",
                    f"Local OSRM was unavailable, so routes were built with fallback algorithm. {reason_text}",
                )
            )
    if fallback_stage == "vroom_to_legacy":
        st.info(
            t(
                "حل‌گر VROOM در دسترس نبود و سیستم به‌صورت خودکار از پایپلاین Legacy استفاده کرده است. "
                f"{_fallback_reason_text(solver_reason)}",
                "VROOM solver was unavailable and the system automatically switched to the Legacy pipeline. "
                f"{_fallback_reason_text(solver_reason)}",
            )
        )
    shadow = result.get("shadow")
    if isinstance(shadow, dict) and bool(shadow.get("enabled")):
        shadow_status = t("موفق", "Success") if str(shadow.get("status")) == "ok" else t("ناموفق", "Failed")
        shadow_reason = _fallback_reason_text(shadow.get("solver_reason"))
        st.caption(
            t("خروجی Shadow VROOM: ", "Shadow VROOM Output: ")
            + 
            f"{shadow_status} | "
            f"assigned={shadow.get('assigned_count', 0)} | "
            f"unassigned={shadow.get('unassigned_count', 0)} | "
            f"reason={shadow_reason}"
        )
    if comparable and not quality["passes_gate"]:
        st.warning(
            t(
                "وضعیت ارزیابی رد شد. بهبود مسیر باید حداقل ۲۰٪ نسبت به مقدار مبنا باشد.",
                "Quality gate failed. Route improvement must be at least 20% over baseline.",
            )
        )


def render_manager_dashboard(current_user: dict) -> None:
    render_page_title(t("داشبورد مدیر", "Manager Dashboard"))

    work_date = jalali_date_input(
        label=t("📅 تاریخ کاری", "📅 Work Date"),
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
    draft_count = int(snapshot.get("draft_count", 0))
    non_draft_count = int(snapshot.get("non_draft_count", 0))
    assignment_count = int(snapshot.get("assignment_count", 0))

    # FIX: Allow upload/flush when only publish lock exists and no operational records are created yet.
    is_hard_locked = visit_count > 0 or followup_count > 0
    is_soft_locked = (not is_hard_locked) and non_draft_count > 0

    if is_hard_locked or is_soft_locked:
        st.warning(
            t(
                "این تاریخ قفل است: "
                f"{visit_count} ویزیت ثبت‌شده | "
                f"{followup_count} پیگیری فعال | "
                f"{published_count} تخصیص منتشرشده",
                "This date is locked: "
                f"{visit_count} recorded visits | "
                f"{followup_count} active follow-ups | "
                f"{published_count} published assignments",
            )
        )
    if is_soft_locked:
        st.info(
            t(
                "برای این تاریخ هنوز ویزیت/پیگیری ثبت نشده است. می‌توانید پاک‌سازی کامل انجام دهید و دوباره فایل آپلود کنید.",
                "No visits/follow-ups are recorded yet for this date. You can flush this date and upload files again.",
            )
        )
    if (not is_hard_locked) and draft_count <= 0:
        st.info(
            t(
                "برای این تاریخ پیش‌نویسی برای انتشار وجود ندارد. اگر قبلاً منتشر شده، برای ساخت مسیر جدید ابتدا پاک‌سازی کامل همان تاریخ را انجام دهید.",
                "No draft exists for publishing on this date. If it was previously published, flush this date before rebuilding routes.",
            )
        )

    with st.expander(t("اعمال فایل‌ها و ساخت مسیر", "Apply Files & Build Routes"), expanded=not is_hard_locked):
        st.markdown(
            f"""
            <div class="panel-description">
                {t(
                    "با آپلود فایل فروشگاه‌ها، اطلاعات فروشگاه‌ها به‌روزرسانی می‌شود.<br/>"
                    "با آپلود فایل وضعیت روزانه ویزیتورها، ظرفیت و نقطه شروع هر ویزیتور ثبت می‌شود و مسیرها برای همان تاریخ دوباره طراحی می‌شوند.",
                    "Uploading the store file updates store data.<br/>"
                    "Uploading daily visitor status registers each visitor capacity/start point and rebuilds routes for the selected date."
                )}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="panel-description-columns">
                {t("ستون‌های الزامی فایل وضعیت روزانه:", "Required columns in daily status file:")}
                <span class="ltr-inline">work_date, username, visitor_code, full_name, start_lat, start_lon, capacity, is_active_today</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            stores_file = st.file_uploader(
                t("فایل فروشگاه‌ها (اختیاری)", "Store File (Optional)"),
                type=["xlsx"],
                key=f"stores_apply_{work_date_iso}",
                disabled=is_hard_locked,
            )
        with c2:
            daily_file = st.file_uploader(
                t("فایل وضعیت روزانه ویزیتورها (اجباری)", "Daily Visitor Status File (Required)"),
                type=["xlsx"],
                key=f"daily_apply_{work_date_iso}",
                disabled=is_hard_locked,
            )

        if st.button(
            t("اعمال فایل‌ها و ساخت مسیر", "Apply Files & Build Routes"),
            key=f"build_pipeline_{work_date_iso}",
            use_container_width=True,
            disabled=is_hard_locked,
        ):
            if is_soft_locked:
                st.error(
                    t(
                        "برای این تاریخ تخصیص منتشرشده وجود دارد. ابتدا «پاک‌سازی کامل همین تاریخ» را انجام دهید، سپس مسیر جدید بسازید.",
                        "Published assignments already exist for this date. First run 'Flush This Date', then rebuild routes.",
                    )
                )
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
                st.error(t(f"خطا در ساخت مسیر: {exc}", f"Error while building routes: {exc}"))

        last_result = st.session_state.get("manager_last_pipeline_result")
        if isinstance(last_result, dict):
            _render_pipeline_result(last_result)

    with st.expander(t("پاک‌سازی کامل داده‌های همین تاریخ", "Flush All Data For This Date"), expanded=False):
        has_operational_data = visit_count > 0 or followup_count > 0
        has_any_daily_data = assignment_count > 0 or has_operational_data
        st.markdown(
            f"""
            <div class="panel-description">
                {t(
                    "این عملیات همه داده‌های تخصیص، ویزیت و پیگیری فروش تلفنی مربوط به همین تاریخ را حذف می‌کند "
                    "و باعث از دست رفتن سوابق عملیاتی همان روز می‌شود.",
                    "This operation deletes all assignments, visits, and telesales follow-ups for this date "
                    "and will remove that day's operational history."
                )}
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not has_any_daily_data:
            st.info(t("برای این تاریخ داده عملیاتی یا تخصیصی ثبت نشده است.", "No assignment or operational data exists for this date."))
        elif not has_operational_data and has_any_daily_data:
            st.info(
                t(
                    "برای این تاریخ هنوز ویزیت یا پیگیری عملیاتی ثبت نشده است؛ پاک‌سازی کامل بدون از دست‌رفتن سابقه ویزیت انجام می‌شود.",
                    "No operational visits/follow-ups are recorded yet for this date; full flush can run without losing visit history.",
                )
            )
        confirm_flush = st.checkbox(
            t("تأیید می‌کنم پاکسازی کامل فقط برای همین تاریخ انجام شود.", "I confirm full flush must run only for this date."),
            key=f"confirm_flush_{work_date_iso}",
        )
        if st.button(
            t("پاک‌سازی کامل همین تاریخ", "Flush This Date"),
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
                    t("پاک‌سازی انجام شد: ", "Flush completed: ")
                    + 
                    f"assignments={result['assignments_deleted']} | "
                    f"visits={result['visits_deleted']} | "
                    f"followups={result['followups_deleted']}"
                )
                st.session_state.pop("manager_last_pipeline_result", None)
                st.session_state.pop("manager_last_pipeline_date", None)
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(t(f"خطا در پاک‌سازی: {exc}", f"Flush error: {exc}"))

    neu_section_header(t("عملیات مدیریتی", "Manager Operations"))
    op1, op2 = st.columns(2)

    with op1:
        if st.button(
            t("📤 انتشار مسیرها", "📤 Publish Routes"),
            key=f"publish_{work_date_iso}",
            use_container_width=True,
            disabled=is_hard_locked or (draft_count <= 0),
        ):
            try:
                with get_db() as db:
                    count = assignment_service.publish_assignments(
                        db=db,
                        work_date=work_date,
                        manager_user_id=current_user["id"],
                        include_draft_override=True,
                    )
                st.success(t(f"{count} تخصیص منتشر شد.", f"{count} assignments were published."))
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(t(f"خطا در انتشار مسیرها: {exc}", f"Publish error: {exc}"))

    with op2:
        if st.button(
            t("🔒 نهایی‌سازی موارد ثبت‌نشده", "🔒 Finalize Unsubmitted Items"),
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
                st.success(t(f"{count} تخصیص ثبت‌نشده به‌صورت خودکار قرمز شد.", f"{count} unsubmitted assignments were auto-finalized as red."))
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(t(f"خطا در نهایی‌سازی: {exc}", f"Finalize error: {exc}"))

    neu_section_header(t("شاخص‌های روزانه", "Daily KPIs"))
    render_metric_grid(
        [
            (t("صف تامین‌پذیر", "Due Stores"), kpis["due_stores"]),
            (t("سبز / زرد / قرمز", "Green / Yellow / Red"), f"{kpis['green']} / {kpis['yellow']} / {kpis['red']}"),
            (t("ویزیت تکمیل‌شده", "Completed Visits"), kpis["completed_visits"]),
            (t("تخصیص‌شده", "Assigned"), kpis["assigned_stores"]),
            (t("در انتظار تماس تلفنی", "Pending Telesales"), kpis["telesales_queue_size"]),
        ]
    )
    if int(kpis.get("due_stores", 0)) == 0:
        st.info(get_empty_state_message(role="manager", context="no_due_stores"))

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    neu_section_header(t("جدول تخصیص‌ها", "Assignments Table"))
    assignment_df = _cached_assignments(work_date_iso)
    if assignment_df.empty:
        st.info(get_empty_state_message(role="manager", context="no_assignments"))
    else:
        assignment_view_df = assignment_df.copy()
        # FIX: Show store grade in manager-generated assignment list for route review.
        if "store_grade" in assignment_view_df.columns:
            assignment_view_df["store_grade"] = assignment_view_df[
                "store_grade"
            ].fillna(t("نامشخص", "Unknown"))
        if "assignment_id" in assignment_view_df.columns:
            assignment_view_df["assignment_id"] = range(1, len(assignment_view_df) + 1)
        render_rtl_table(
            assignment_view_df,
            key_prefix=f"manager_assignments_{work_date_iso}",
        )

    neu_section_header(t("صف در انتظار تماس تلفنی", "Pending Telesales Queue"))
    if pending_queue:
        pending_df = pd.DataFrame(pending_queue)
        pending_df = pending_df.drop(
            columns=["store_lat", "store_lon"], errors="ignore"
        )
        render_rtl_table(
            pending_df,
            key_prefix=f"manager_pending_telesales_{work_date_iso}",
        )
    else:
        st.info(get_empty_state_message(role="manager", context="no_pending_telesales"))

    visitor_options = _cached_visitor_options(work_date_iso)
    neu_section_header(t("نقشه مسیر", "Route Map"))
    runtime_state = runtime_health_service.get_offline_runtime_status()
    if (not bool(runtime_state.get("osrm_up", False))) or (
        not bool(runtime_state.get("tiles_up", False))
    ):
        st.info(
            t(
                "حالت کاهشی فعال است: اگر OSRM یا Tile در دسترس نباشد، نقشه مینیمال سریع نمایش داده می‌شود.",
                "Degraded mode is active: if OSRM or tile service is unavailable, a fast minimal map will be shown.",
            )
        )
    if not bool(runtime_state.get("osrm_data_ready", False)):
        st.warning(t("فایل داده OSRM پیدا نشد (offline/osrm/data/tehran-latest.osrm).", "OSRM data file not found (offline/osrm/data/tehran-latest.osrm)."))
    if not bool(runtime_state.get("tiles_data_ready", False)):
        st.warning(t("فایل MBTiles پیدا نشد (offline/tiles/data/*.mbtiles).", "MBTiles file not found (offline/tiles/data/*.mbtiles)."))
    st.markdown(
        f'<div class="panel-description" style="text-align:{align()} !important;margin:0.1rem 0 0.35rem;">'
        + t(
            "راهنما: در همین کادر انتخاب ویزیتور می‌توانید جست‌وجو کنید (نمونه: VIS-001 یا visitor1).",
            "Tip: you can search in this visitor selector (example: VIS-001 or visitor1).",
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    selected_code = st.selectbox(
        t("انتخاب ویزیتور برای نمایش نقشه و دانلود مسیر", "Select Visitor For Map & Route Download"),
        options=list(visitor_options.keys()),
        index=None,
        placeholder=t("ویزیتور را انتخاب یا جست‌وجو کنید...", "Select or search a visitor..."),
        key=f"manager_map_visitor_{work_date_iso}",
    )

    if selected_code:
        selected_id = visitor_options[selected_code]
        route_df = _cached_route_map(work_date_iso, selected_id)
        if route_df.empty:
            st.info(
                get_empty_state_message(role="manager", context="no_route_for_visitor")
            )
        else:
            # FIX: [PERF-04] Pass one pre-read runtime state to map component and avoid duplicate probes/messages.
            render_route_map(
                route_df,
                runtime_status=runtime_state,
                show_runtime_messages=False,
            )

    neu_section_header(t("خروجی‌ها", "Exports"))
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
                label=t(f"📥 دانلود مسیر {selected_code}", f"📥 Download Route {selected_code}"),
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
            label=t("📥 دانلود گزارش کامل روزانه", "📥 Download Full Daily Report"),
            data=summary_buf.getvalue(),
            file_name=f"summary_{work_date_iso}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
