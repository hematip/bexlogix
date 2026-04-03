import re

import streamlit as st

from client import auth_state
from client.styles.neumorphism import inject_global_css, render_login_logo
from server.app.auth.session import authenticate_user
from server.app.enums.roles import UserRole
from server.db.database import get_db_session

VIEW_BY_ROLE = {
    UserRole.MANAGER.value: "manager",
    UserRole.SUPERVISOR.value: "supervisor",
    UserRole.VISITOR.value: "visitor",
    UserRole.TELESALES.value: "telesales",
}

_PERSIAN_PATTERN = re.compile(r"[\u0600-\u06FF]")


def _contains_persian_text(value: str) -> bool:
    return bool(_PERSIAN_PATTERN.search(str(value or "")))


def render_login_page() -> None:
    inject_global_css()
    render_login_logo()

    st.markdown(
        """
        <div class="login-title-block">
            <div class="login-title-main">ورود به BexLogix</div>
            <div class="login-title-sub">سیستم مدیریت عملیات فروش میدانی</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("نام کاربری", key="login_username")
        password = st.text_input("رمز عبور", type="password", key="login_password")

        if _contains_persian_text(password):
            st.warning(
                "رمز عبور را با صفحه‌کلید فارسی تایپ کرده‌اید. "
                "در صورت خطای ورود، زبان صفحه‌کلید را روی English قرار دهید."
            )

        submitted = st.form_submit_button("ورود", use_container_width=True)

    st.markdown(
        '<p class="login-footer-powered">Powered by <strong>Kanoon Iran Novin</strong></p>',
        unsafe_allow_html=True,
    )

    if not submitted:
        return

    db = get_db_session()
    try:
        user = authenticate_user(db, username=username, password=password)
    finally:
        db.close()

    if not user:
        st.error("نام کاربری یا رمز عبور اشتباه است، یا حساب کاربر غیرفعال است.")
        return

    auth_state.login_user(
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        }
    )
    auth_state.set_persistent_login_query(
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        }
    )
    st.query_params["view"] = VIEW_BY_ROLE.get(user.role, "login")
    st.rerun()
