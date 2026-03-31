import sys
from pathlib import Path

import streamlit as st

# Ensure project root is importable when running: streamlit run client/streamlit_app.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from client import auth_state
from client.pages.login import render_login_page
from client.pages.manager_dashboard import render_manager_dashboard
from client.pages.supervisor_dashboard import render_supervisor_dashboard
from client.pages.telesales_panel import render_telesales_panel
from client.pages.visitor_panel import render_visitor_panel
from server.app.enums.roles import UserRole


def main() -> None:
    st.set_page_config(page_title="BexLogix", layout="wide")

    current_user = auth_state.get_current_user()
    if current_user is None:
        auth_state.logout_user()
        render_login_page()
        return

    auth_state.touch_session()

    with st.sidebar:
        st.subheader("Session")
        st.write(f"User: `{current_user['username']}`")
        st.write(f"Role: `{current_user['role']}`")
        if st.button("Logout"):
            auth_state.logout_user()
            st.rerun()

    role = current_user["role"]
    if role == UserRole.MANAGER.value:
        render_manager_dashboard(current_user)
    elif role == UserRole.SUPERVISOR.value:
        render_supervisor_dashboard(current_user)
    elif role == UserRole.VISITOR.value:
        render_visitor_panel(current_user)
    elif role == UserRole.TELESALES.value:
        render_telesales_panel(current_user)
    else:
        st.error("Unsupported role.")


if __name__ == "__main__":
    main()
