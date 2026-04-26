# Purpose: Shared localization and layout-direction helpers.
# Workflow Role: Centralizes language state, query persistence, and UI direction.

from __future__ import annotations

from urllib.parse import urlencode

import streamlit as st

LANG_FA = "fa"
LANG_EN = "en"
DEFAULT_LANG = LANG_FA

_LANG_SESSION_KEY = "ui_language"
_LANG_QUERY_KEY = "lang"

_SUPPORTED_LANGS = {LANG_FA, LANG_EN}


def _normalize_lang(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in _SUPPORTED_LANGS else DEFAULT_LANG


def _query_value(name: str) -> str | None:
    raw_value = st.query_params.get(name)
    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        raw_value = raw_value[0] if raw_value else None
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    return text or None


def get_language() -> str:
    session_lang_raw = st.session_state.get(_LANG_SESSION_KEY)
    session_lang = _normalize_lang(session_lang_raw) if session_lang_raw else None
    query_lang_raw = _query_value(_LANG_QUERY_KEY)
    query_lang = _normalize_lang(query_lang_raw) if query_lang_raw else None

    resolved = session_lang or query_lang or DEFAULT_LANG

    if st.session_state.get(_LANG_SESSION_KEY) != resolved:
        st.session_state[_LANG_SESSION_KEY] = resolved
    if query_lang != resolved:
        st.query_params[_LANG_QUERY_KEY] = resolved

    return resolved


def set_language(lang: str) -> bool:
    normalized = _normalize_lang(lang)
    changed = False

    if st.session_state.get(_LANG_SESSION_KEY) != normalized:
        st.session_state[_LANG_SESSION_KEY] = normalized
        changed = True

    query_lang_raw = _query_value(_LANG_QUERY_KEY)
    query_lang = _normalize_lang(query_lang_raw) if query_lang_raw else None
    if query_lang != normalized:
        st.query_params[_LANG_QUERY_KEY] = normalized
        changed = True

    return changed


def is_fa() -> bool:
    return get_language() == LANG_FA


def is_en() -> bool:
    return get_language() == LANG_EN


def is_rtl() -> bool:
    return is_fa()


def direction() -> str:
    return "rtl" if is_rtl() else "ltr"


def align() -> str:
    return "right" if is_rtl() else "left"


def start_side() -> str:
    return "right" if is_rtl() else "left"


def end_side() -> str:
    return "left" if is_rtl() else "right"


def t(fa_text: str, en_text: str) -> str:
    return fa_text if is_fa() else en_text


def _build_lang_href(target_lang: str) -> str:
    normalized = _normalize_lang(target_lang)
    query_pairs: list[tuple[str, str]] = []
    for key in st.query_params.keys():
        if key == _LANG_QUERY_KEY:
            continue
        raw_value = st.query_params.get(key)
        if raw_value is None:
            continue
        if isinstance(raw_value, list):
            for item in raw_value:
                text = str(item or "").strip()
                if text:
                    query_pairs.append((key, text))
            continue
        text = str(raw_value).strip()
        if text:
            query_pairs.append((key, text))
    query_pairs.append((_LANG_QUERY_KEY, normalized))
    return f"?{urlencode(query_pairs, doseq=True)}"


def render_language_switch(key: str = "global_lang_switch") -> None:
    current = get_language()
    fa_href = _build_lang_href(LANG_FA)
    en_href = _build_lang_href(LANG_EN)
    fa_style = (
        "background:var(--bex-accent);color:#fff;border-color:var(--bex-accent);"
        if current == LANG_FA
        else "background:#eef1f5;color:#2c3e50;border-color:#c3cad6;"
    )
    en_style = (
        "background:var(--bex-accent);color:#fff;border-color:var(--bex-accent);"
        if current == LANG_EN
        else "background:#eef1f5;color:#2c3e50;border-color:#c3cad6;"
    )
    st.markdown(
        f"""
        <div id="{key}" style="
            position:fixed;top:0.55rem;left:0.85rem;z-index:2147483000;
            display:inline-flex;gap:0.25rem;padding:0.16rem;border-radius:10px;
            background:rgba(242,244,247,0.94);
            box-shadow:2px 2px 6px rgba(204,208,216,0.8),-2px -2px 6px rgba(255,255,255,0.9);
            direction:ltr;">
          <a href="{fa_href}" target="_self" style="
              min-width:40px;padding:0.22rem 0.5rem;border-radius:8px;border:1px solid;
              text-decoration:none;font-size:0.82rem;font-weight:700;line-height:1.1;
              text-align:center;{fa_style}">
              FA
          </a>
          <a href="{en_href}" target="_self" style="
              min-width:40px;padding:0.22rem 0.5rem;border-radius:8px;border:1px solid;
              text-decoration:none;font-size:0.82rem;font-weight:700;line-height:1.1;
              text-align:center;{en_style}">
              EN
          </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
