import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from client import auth_state
from client.pages.login import render_login_page
from client.pages.manager_dashboard import render_manager_dashboard
from client.pages.supervisor_dashboard import render_supervisor_dashboard
from client.pages.telesales_panel import render_telesales_panel
from client.pages.visitor_panel import render_visitor_panel
from client.styles.neumorphism import (
    inject_global_css,
    render_sidebar_logo,
    role_badge_html,
)
from server.app.enums.roles import UserRole
from server.db.startup_seed import seed_if_empty


def main() -> None:
    st.set_page_config(page_title="BexLogix", layout="wide", page_icon="📦")
    seed_if_empty()
    inject_global_css()

    current_user = auth_state.get_current_user()
    if current_user is None:
        auth_state.logout_user()
        render_login_page()
        return

    auth_state.touch_session()

    with st.sidebar:
        render_sidebar_logo()
        st.markdown("---")

        role = current_user["role"]
        st.markdown(
            f"""<div class="neu-card-flat" style="text-align:center;">
                <div style="font-weight:700;font-size:1rem;margin-bottom:0.3rem;">
                    {current_user['username']}
                </div>
                {role_badge_html(role)}
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown("")
        if st.button("🚪  Logout", use_container_width=True):
            auth_state.logout_user()
            st.rerun()

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
