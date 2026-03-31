import streamlit as st

from client import auth_state
from client.styles.neumorphism import inject_global_css, render_login_logo
from server.app.auth.session import authenticate_user
from server.db.database import get_db_session


def render_login_page() -> None:
    inject_global_css()

    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    render_login_logo()

    st.markdown(
        '<div class="neu-card" style="padding:2rem;">',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<h3 style="text-align:center;margin-bottom:0.2rem;">Welcome to BexLogix</h3>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:#6C7A89;font-size:0.85rem;margin-bottom:1.2rem;">'
        "Internal workflow application — Zar Group</p>",
        unsafe_allow_html=True,
    )

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<p style="text-align:center;color:#9CA3AF;font-size:0.78rem;margin-top:1.2rem;">'
        "Powered by <strong>Kanoon Iran Novin</strong></p>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if not submitted:
        return

    db = get_db_session()
    try:
        user = authenticate_user(db, username=username, password=password)
    finally:
        db.close()

    if not user:
        st.error("Invalid username/password or inactive account.")
        return

    auth_state.login_user(
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        }
    )
    st.rerun()
