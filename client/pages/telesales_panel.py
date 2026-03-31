from datetime import date

import pandas as pd
import streamlit as st

from client.styles.neumorphism import neu_metric, neu_section_header
from server.app.enums.contact_status import ContactStatus
from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.services import telesales_service
from server.db.database import get_db_session


def render_telesales_panel(current_user: dict) -> None:
    st.markdown(
        '<h2 style="margin-bottom:0.2rem;">Telesales Panel</h2>',
        unsafe_allow_html=True,
    )

    as_of_date = st.date_input("📅  Show Pending Up To", value=date.today())

    db = get_db_session()
    try:
        pending = telesales_service.list_pending_followups(db=db, as_of_date=as_of_date)
    finally:
        db.close()

    # ── Summary ───────────────────────────────────────────────
    s1, s2 = st.columns([1, 3])
    with s1:
        neu_metric("Pending Items", len(pending))

    if not pending:
        st.markdown(
            """<div class="neu-card" style="text-align:center;padding:2rem;">
                <p style="font-size:1.1rem;color:#6C7A89;">
                    ✅  No pending follow-ups. You're all caught up!
                </p>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # ── Pending queue table ───────────────────────────────────
    neu_section_header("Pending Follow-up Queue")
    st.dataframe(pd.DataFrame(pending), use_container_width=True)

    # ── Follow-up cards ───────────────────────────────────────
    neu_section_header("Submit Follow-up Results")

    for item in pending:
        fid = item["followup_id"]
        title = f"{item['store_code']} — {item['store_name']}  |  Follow-up #{fid}"

        with st.expander(title):
            st.markdown(
                f"""<div class="neu-card-flat">
                    <strong>Follow-up Date:</strong> {item['followup_date']}<br/>
                    {"<strong>Note:</strong> " + item['note'] if item.get('note') else ""}
                </div>""",
                unsafe_allow_html=True,
            )

            with st.form(f"followup_{fid}"):
                contact = st.selectbox(
                    "Contact Status",
                    options=[s.value for s in ContactStatus],
                    key=f"cs_{fid}",
                )
                result = st.selectbox(
                    "Outcome",
                    options=[o.value for o in TelesalesOutcome],
                    key=f"out_{fid}",
                )
                note = st.text_area(
                    "Note",
                    key=f"tn_{fid}",
                    placeholder="Optional follow-up note...",
                )
                submitted = st.form_submit_button("Save Result", use_container_width=True)

            if submitted:
                db = get_db_session()
                try:
                    telesales_service.submit_followup_result(
                        db=db,
                        followup_id=fid,
                        telesales_user_id=current_user["id"],
                        contact_status=contact,
                        result=result,
                        note=note,
                    )
                    st.success("Follow-up saved.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Save failed: {exc}")
                finally:
                    db.close()
