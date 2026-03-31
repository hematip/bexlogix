from datetime import datetime, timezone

import streamlit as st

AUTH_USER_ID_KEY = "auth_user_id"
AUTH_USERNAME_KEY = "auth_username"
AUTH_ROLE_KEY = "auth_role"
AUTH_LOGIN_AT_KEY = "auth_login_at_utc"
AUTH_LAST_SEEN_AT_KEY = "auth_last_seen_at_utc"


def login_user(user_payload: dict) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    st.session_state[AUTH_USER_ID_KEY] = user_payload["id"]
    st.session_state[AUTH_USERNAME_KEY] = user_payload["username"]
    st.session_state[AUTH_ROLE_KEY] = user_payload["role"]
    st.session_state[AUTH_LOGIN_AT_KEY] = now_iso
    st.session_state[AUTH_LAST_SEEN_AT_KEY] = now_iso


def logout_user() -> None:
    for key in [
        AUTH_USER_ID_KEY,
        AUTH_USERNAME_KEY,
        AUTH_ROLE_KEY,
        AUTH_LOGIN_AT_KEY,
        AUTH_LAST_SEEN_AT_KEY,
    ]:
        if key in st.session_state:
            del st.session_state[key]


def is_session_valid(timeout_minutes: int = 480) -> bool:
    last_seen_raw = st.session_state.get(AUTH_LAST_SEEN_AT_KEY)
    if not last_seen_raw:
        return False

    try:
        last_seen = datetime.fromisoformat(last_seen_raw)
    except ValueError:
        return False

    now = datetime.now(timezone.utc)
    delta_minutes = (now - last_seen).total_seconds() / 60
    return delta_minutes <= timeout_minutes


def touch_session() -> None:
    st.session_state[AUTH_LAST_SEEN_AT_KEY] = datetime.now(timezone.utc).isoformat()


def get_current_user() -> dict | None:
    if not is_session_valid():
        return None
    user_id = st.session_state.get(AUTH_USER_ID_KEY)
    username = st.session_state.get(AUTH_USERNAME_KEY)
    role = st.session_state.get(AUTH_ROLE_KEY)
    if user_id is None or username is None or role is None:
        return None
    return {
        "id": user_id,
        "username": username,
        "role": role,
    }
