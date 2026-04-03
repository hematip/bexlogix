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
from client.styles.neumorphism import inject_global_css, render_login_logo, role_badge_html
from server.app.enums.roles import UserRole
from server.app.repositories import user_repository
from server.db.database import get_db_session
from server.db.startup_seed import seed_if_empty

VIEW_BY_ROLE = {
    UserRole.MANAGER.value: "manager",
    UserRole.SUPERVISOR.value: "supervisor",
    UserRole.VISITOR.value: "visitor",
    UserRole.TELESALES.value: "telesales",
}


def _get_query_view() -> str | None:
    raw_value = st.query_params.get("view")
    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        raw_value = raw_value[0] if raw_value else None
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().lower()
    return normalized or None


def _set_query_view(view: str) -> None:
    st.query_params["view"] = view


def _validate_current_user(user_payload: dict | None) -> dict | None:
    if not user_payload:
        return None

    db = get_db_session()
    try:
        db_user = user_repository.get_user_by_id(db, int(user_payload["id"]))
    finally:
        db.close()

    if not db_user or not db_user.is_active:
        return None
    if db_user.username != user_payload["username"]:
        return None
    if db_user.role != user_payload["role"]:
        return None

    return {
        "id": int(db_user.id),
        "username": str(db_user.username),
        "role": str(db_user.role),
    }


def _render_topbar(current_user: dict) -> bool:
    render_login_logo()
    spacer_col, user_col = st.columns([10.2, 1.8], gap="medium")
    with spacer_col:
        st.markdown('<div class="topbar-spacer"></div>', unsafe_allow_html=True)
    with user_col:
        st.markdown(
            f"""<div class="app-user-shell">
                <div class="app-user-mini">
                    <div class="app-user-mini-name">{current_user['username']}</div>
                    {role_badge_html(current_user['role'])}
                </div>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button("خروج", key="logout_topbar", use_container_width=True):
            return True
    return False

def main() -> None:
    st.set_page_config(
        page_title="BexLogix",
        layout="wide",
        page_icon="📦",
        initial_sidebar_state="collapsed",
    )
    seed_if_empty()
    inject_global_css()

    requested_view = _get_query_view()
    current_user = auth_state.get_current_user()
    if current_user is None:
        current_user = auth_state.restore_session_from_query_token()

    current_user = _validate_current_user(current_user)
    if current_user is None:
        auth_state.logout_user()
        auth_state.clear_persistent_login_query()
        if requested_view != "login":
            _set_query_view("login")
            st.rerun()
        render_login_page()
        return

    auth_state.touch_session()

    role = current_user["role"]
    expected_view = VIEW_BY_ROLE.get(role)
    if not expected_view:
        st.error("نقش کاربری پشتیبانی نمی‌شود.")
        return

    if requested_view != expected_view:
        _set_query_view(expected_view)
        st.rerun()

    if _render_topbar(current_user):
        auth_state.logout_user()
        auth_state.clear_persistent_login_query()
        _set_query_view("login")
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
        st.error("نقش کاربری پشتیبانی نمی‌شود.")


if __name__ == "__main__":
    main()

