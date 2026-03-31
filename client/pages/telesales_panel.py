from datetime import date

import pandas as pd
import streamlit as st

from server.app.enums.contact_status import ContactStatus
from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.services import telesales_service
from server.db.database import get_db_session


def render_telesales_panel(current_user: dict) -> None:
    st.title("Telesales Panel")
    st.caption(f"Logged in as: {current_user['username']}")

    as_of_date = st.date_input("Show Pending Up To Date", value=date.today())

    db = get_db_session()
    try:
        pending_followups = telesales_service.list_pending_followups(
            db=db,
            as_of_date=as_of_date,
        )
    finally:
        db.close()

    if not pending_followups:
        st.info("No pending follow-ups.")
        return

    st.subheader("Pending Follow-up Queue")
    st.dataframe(pd.DataFrame(pending_followups), use_container_width=True)

    st.subheader("Submit Follow-up Result")
    for item in pending_followups:
        with st.expander(
            f"{item['store_code']} - {item['store_name']} | Follow-up ID {item['followup_id']}"
        ):
            st.caption(f"Follow-up Date: {item['followup_date']}")
            if item.get("note"):
                st.caption(f"Existing Note: {item['note']}")

            with st.form(f"followup_form_{item['followup_id']}"):
                contact_status = st.selectbox(
                    "Contact Status",
                    options=[status.value for status in ContactStatus],
                )
                result = st.selectbox(
                    "Result",
                    options=[outcome.value for outcome in TelesalesOutcome],
                )
                note = st.text_area("Note")
                submitted = st.form_submit_button("Save Follow-up Result")

            if submitted:
                db = get_db_session()
                try:
                    telesales_service.submit_followup_result(
                        db=db,
                        followup_id=item["followup_id"],
                        telesales_user_id=current_user["id"],
                        contact_status=contact_status,
                        result=result,
                        note=note,
                    )
                    st.success("Follow-up saved successfully.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Save failed: {exc}")
                finally:
                    db.close()
