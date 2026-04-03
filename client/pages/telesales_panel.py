from datetime import date

import pandas as pd
import streamlit as st

from client.components.jalali_date import jalali_date_input
from client.styles.neumorphism import neu_metric, neu_section_header, render_page_title
from server.app.enums.contact_status import ContactStatus
from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.services import telesales_service
from server.db.database import get_db_session

CONTACT_LABELS = {
    ContactStatus.REACHED.value: "تماس برقرار شد",
    ContactStatus.NOT_REACHED.value: "عدم برقراری تماس",
}

OUTCOME_LABELS = {
    TelesalesOutcome.SALE_DONE.value: "فروش انجام شد",
    TelesalesOutcome.NO_NEED.value: "نیازی نبود",
    TelesalesOutcome.POSTPONE.value: "موکول شد",
    TelesalesOutcome.INVALID.value: "نامعتبر",
}


def _safe_text(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text else "—"


def render_telesales_panel(current_user: dict) -> None:
    render_page_title("پنل فروش تلفنی")

    as_of_date = jalali_date_input(
        label="📅 نمایش موارد تا تاریخ",
        key_prefix="telesales_as_of_date",
        default_gregorian=date.today(),
    )

    db = get_db_session()
    try:
        pending_followups = telesales_service.list_pending_followups(
            db=db,
            as_of_date=as_of_date,
        )
    finally:
        db.close()

    c1, _ = st.columns([1, 3])
    with c1:
        neu_metric("آیتم‌های در انتظار", len(pending_followups))

    if not pending_followups:
        st.markdown(
            """<div class="neu-card" style="text-align:center;padding:2rem;">
                <p style="font-size:1.1rem;color:#6C7A89;">✅ هیچ موردی در صف انتظار وجود ندارد.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="section-gap-lg"></div>', unsafe_allow_html=True)
    neu_section_header("صف پیگیری در انتظار")
    table_rows = []
    for item in pending_followups:
        table_rows.append(
            {
                "پیگیری": item["followup_id"],
                "تاریخ پیگیری": item["followup_date"],
                "فروشگاه": f"{item['store_code']} — {item['store_name']}",
                "ویزیتور": _safe_text(item.get("visitor_code")),
                "علت عدم انجام ویزیت": _safe_text(item.get("unavailable_reason")),
            }
        )
    queue_df = pd.DataFrame(table_rows)
    styled_queue_df = queue_df.style.set_table_styles(
        [
            {"selector": "th", "props": [("text-align", "right"), ("direction", "rtl")]},
            {"selector": "td", "props": [("text-align", "right"), ("direction", "rtl")]},
        ]
    ).set_properties(
        **{
            "font-family": "IRANSansFaNum, IRANSans FaNum, IRAN Sans, Tahoma, Segoe UI, sans-serif",
            "text-align": "right",
            "direction": "rtl",
        }
    )
    st.table(styled_queue_df)

    neu_section_header("ثبت نتیجه پیگیری")
    for item in pending_followups:
        followup_id = item["followup_id"]
        title = f"{item['store_code']} — {item['store_name']} | پیگیری #{followup_id}"

        with st.expander(title):
            st.markdown('<div class="neu-card-flat">', unsafe_allow_html=True)
            st.markdown(
                f'<div class="telesales-detail-line"><strong>تاریخ پیگیری:</strong> {_safe_text(item.get("followup_date"))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="telesales-detail-line"><strong>تاریخ ویزیت قرمز:</strong> {_safe_text(item.get("visit_date"))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="telesales-detail-line"><strong>ویزیتور:</strong> {_safe_text(item.get("visitor_code"))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="telesales-detail-line"><strong>منطقه فروشگاه:</strong> {_safe_text(item.get("store_region"))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="telesales-detail-line"><strong>آدرس فروشگاه:</strong> {_safe_text(item.get("store_address"))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="telesales-detail-line"><strong>مختصات:</strong> <span class="ltr-inline">{_safe_text(item.get("store_lat"))}, {_safe_text(item.get("store_lon"))}</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="telesales-detail-line"><strong>علت عدم انجام ویزیت:</strong> {_safe_text(item.get("unavailable_reason"))}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

            with st.form(f"followup_{followup_id}"):
                selected_contact = st.selectbox(
                    "وضعیت تماس",
                    options=list(CONTACT_LABELS.values()),
                    key=f"contact_{followup_id}",
                )
                contact_status = next(
                    code for code, label in CONTACT_LABELS.items() if label == selected_contact
                )

                selected_outcome = st.selectbox(
                    "نتیجه پیگیری",
                    options=list(OUTCOME_LABELS.values()),
                    key=f"result_{followup_id}",
                )
                outcome = next(
                    code for code, label in OUTCOME_LABELS.items() if label == selected_outcome
                )
                note = st.text_area(
                    "یادداشت اپراتور",
                    key=f"note_{followup_id}",
                    placeholder="یادداشت اختیاری پیگیری...",
                )
                submitted = st.form_submit_button("ذخیره نتیجه", use_container_width=True)

            if submitted:
                db = get_db_session()
                try:
                    telesales_service.submit_followup_result(
                        db=db,
                        followup_id=followup_id,
                        telesales_user_id=current_user["id"],
                        contact_status=contact_status,
                        result=outcome,
                        note=note,
                    )
                    st.success("نتیجه پیگیری با موفقیت ذخیره شد.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"خطا در ذخیره نتیجه: {exc}")
                finally:
                    db.close()
