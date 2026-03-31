import streamlit as st

from client import auth_state
from server.app.auth.session import authenticate_user
from server.db.database import get_db_session


def render_login_page() -> None:
    st.title("BexLogix Login")
    st.caption("Internal workflow app for Zar Group")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

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
    st.success("Login successful.")
    st.rerun()
