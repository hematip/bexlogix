"""White Neumorphism design system for BexLogix Streamlit UI."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Colour tokens
# ---------------------------------------------------------------------------
BG = "#F2F4F7"
SURFACE = "#E8ECF1"
SHADOW_DARK = "#ccd0d8"
SHADOW_LIGHT = "#ffffff"
TEXT_PRIMARY = "#2C3E50"
TEXT_SECONDARY = "#6C7A89"
ACCENT = "#5B7FFF"
SUCCESS = "#27AE60"
WARNING = "#F39C12"
DANGER = "#E74C3C"
INFO = "#3498DB"

# ---------------------------------------------------------------------------
# Global CSS — injected once per page render
# ---------------------------------------------------------------------------
_GLOBAL_CSS = f"""
<style>
/* ── Base ─────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {{
    background-color: {BG} !important;
    font-family: 'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}
[data-testid="stHeader"] {{
    background-color: {BG} !important;
}}

/* ── Sidebar ──────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    background: linear-gradient(145deg, #eaecf0, {BG}) !important;
    border-right: none !important;
    box-shadow: 4px 0 12px {SHADOW_DARK} !important;
}}
section[data-testid="stSidebar"] .stMarkdown {{
    color: {TEXT_PRIMARY};
}}

/* ── Neumorphic card (use class .neu-card) ────────────────────── */
.neu-card {{
    background: {BG};
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
    box-shadow: 6px 6px 14px {SHADOW_DARK},
                -6px -6px 14px {SHADOW_LIGHT};
    transition: box-shadow 0.2s ease;
}}
.neu-card-flat {{
    background: {BG};
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: 3px 3px 8px {SHADOW_DARK},
                -3px -3px 8px {SHADOW_LIGHT};
}}
.neu-card-inset {{
    background: {BG};
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: inset 3px 3px 8px {SHADOW_DARK},
                inset -3px -3px 8px {SHADOW_LIGHT};
}}

/* ── KPI metric tile ──────────────────────────────────────────── */
.neu-metric {{
    background: {BG};
    border-radius: 16px;
    padding: 1.2rem 1rem;
    text-align: center;
    box-shadow: 5px 5px 12px {SHADOW_DARK},
                -5px -5px 12px {SHADOW_LIGHT};
    min-height: 100px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}}
.neu-metric .metric-value {{
    font-size: 1.9rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    line-height: 1.2;
}}
.neu-metric .metric-label {{
    font-size: 0.82rem;
    font-weight: 500;
    color: {TEXT_SECONDARY};
    margin-top: 0.35rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}

/* ── Buttons ──────────────────────────────────────────────────── */
div.stButton > button {{
    background: {BG} !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.55rem 1.6rem !important;
    color: {TEXT_PRIMARY} !important;
    font-weight: 600 !important;
    box-shadow: 4px 4px 10px {SHADOW_DARK},
                -4px -4px 10px {SHADOW_LIGHT} !important;
    transition: all 0.15s ease !important;
}}
div.stButton > button:hover {{
    box-shadow: 2px 2px 5px {SHADOW_DARK},
                -2px -2px 5px {SHADOW_LIGHT} !important;
    transform: translateY(1px);
}}
div.stButton > button:active {{
    box-shadow: inset 3px 3px 6px {SHADOW_DARK},
                inset -3px -3px 6px {SHADOW_LIGHT} !important;
    transform: translateY(0);
}}

/* ── Form submit button ───────────────────────────────────────── */
div.stFormSubmitButton > button {{
    background: {ACCENT} !important;
    color: #fff !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.55rem 2rem !important;
    font-weight: 600 !important;
    box-shadow: 4px 4px 10px {SHADOW_DARK},
                -4px -4px 10px {SHADOW_LIGHT} !important;
}}
div.stFormSubmitButton > button:hover {{
    filter: brightness(1.08);
    box-shadow: 2px 2px 5px {SHADOW_DARK},
                -2px -2px 5px {SHADOW_LIGHT} !important;
}}

/* ── Inputs (text, select, date, file) ────────────────────────── */
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div,
input[type="text"],
input[type="password"],
input[type="date"] {{
    border-radius: 10px !important;
    border: none !important;
    box-shadow: inset 2px 2px 5px {SHADOW_DARK},
                inset -2px -2px 5px {SHADOW_LIGHT} !important;
    background: {BG} !important;
}}

/* ── Expander ─────────────────────────────────────────────────── */
details[data-testid="stExpander"] {{
    background: {BG} !important;
    border: none !important;
    border-radius: 14px !important;
    box-shadow: 4px 4px 10px {SHADOW_DARK},
                -4px -4px 10px {SHADOW_LIGHT} !important;
    margin-bottom: 0.8rem;
}}
details[data-testid="stExpander"] summary {{
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}

/* ── Dataframe wrapper ────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden;
    box-shadow: 3px 3px 8px {SHADOW_DARK},
                -3px -3px 8px {SHADOW_LIGHT} !important;
}}

/* ── Status badges ────────────────────────────────────────────── */
.badge {{
    display: inline-block;
    padding: 0.22rem 0.7rem;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.03em;
}}
.badge-green  {{ background: #d4edda; color: #155724; }}
.badge-yellow {{ background: #fff3cd; color: #856404; }}
.badge-red    {{ background: #f8d7da; color: #721c24; }}
.badge-blue   {{ background: #d1ecf1; color: #0c5460; }}
.badge-gray   {{ background: #e2e3e5; color: #383d41; }}
.badge-draft     {{ background: #e2e3e5; color: #383d41; }}
.badge-published {{ background: #cce5ff; color: #004085; }}
.badge-completed {{ background: #d4edda; color: #155724; }}
.badge-skipped   {{ background: #f8d7da; color: #721c24; }}

/* ── Section header ───────────────────────────────────────────── */
.section-header {{
    font-size: 1.15rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    margin-bottom: 0.6rem;
    padding-bottom: 0.3rem;
    border-bottom: 2px solid {SURFACE};
}}

/* ── Role badge ───────────────────────────────────────────────── */
.role-badge {{
    display: inline-block;
    padding: 0.2rem 0.8rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.role-manager    {{ background: #dbeafe; color: #1e40af; }}
.role-supervisor {{ background: #fef3c7; color: #92400e; }}
.role-visitor    {{ background: #d1fae5; color: #065f46; }}
.role-telesales  {{ background: #ede9fe; color: #5b21b6; }}

/* ── Login page centering ─────────────────────────────────────── */
.login-container {{
    max-width: 420px;
    margin: 0 auto;
    padding-top: 2rem;
}}
.login-logo {{
    text-align: center;
    margin-bottom: 1.5rem;
}}
.login-logo img {{
    max-width: 280px;
    height: auto;
}}

/* ── Sidebar logo ─────────────────────────────────────────────── */
.sidebar-logo {{
    text-align: center;
    padding: 0.8rem 0 0.5rem 0;
}}
.sidebar-logo img {{
    max-width: 180px;
    height: auto;
}}

/* ── Download button ──────────────────────────────────────────── */
div.stDownloadButton > button {{
    background: {BG} !important;
    border: 1px solid {SURFACE} !important;
    border-radius: 12px !important;
    box-shadow: 4px 4px 10px {SHADOW_DARK},
                -4px -4px 10px {SHADOW_LIGHT} !important;
    color: {TEXT_PRIMARY} !important;
    font-weight: 600 !important;
}}

/* ── Monitoring info bar ──────────────────────────────────────── */
.monitoring-bar {{
    background: #dbeafe;
    color: #1e40af;
    border-radius: 10px;
    padding: 0.6rem 1rem;
    font-weight: 600;
    font-size: 0.85rem;
    text-align: center;
    margin-bottom: 1rem;
    box-shadow: inset 2px 2px 5px rgba(0,0,0,0.06),
                inset -2px -2px 5px rgba(255,255,255,0.8);
}}

/* ── Tabs styling ─────────────────────────────────────────────── */
button[data-baseweb="tab"] {{
    border-radius: 10px 10px 0 0 !important;
    font-weight: 600 !important;
}}

/* ── Hide default Streamlit branding ──────────────────────────── */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
</style>
"""


def inject_global_css() -> None:
    """Inject the full neumorphism stylesheet into the current page."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Logo helpers
# ---------------------------------------------------------------------------
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _logo_img_tag(max_width: int = 280) -> str | None:
    """Return an <img> tag for the logo (supports png, jpg, jpeg, svg)."""
    for ext, mime in [
        ("png", "image/png"),
        ("jpg", "image/jpeg"),
        ("jpeg", "image/jpeg"),
        ("svg", "image/svg+xml"),
    ]:
        path = _ASSETS_DIR / f"logo.{ext}"
        if path.exists():
            b64 = base64.b64encode(path.read_bytes()).decode()
            return f'<img src="data:{mime};base64,{b64}" alt="BexLogix" style="max-width:{max_width}px;height:auto;">'
    return None


def render_sidebar_logo() -> None:
    """Render the logo in the sidebar."""
    tag = _logo_img_tag(max_width=180)
    if tag:
        st.markdown(f'<div class="sidebar-logo">{tag}</div>', unsafe_allow_html=True)


def render_login_logo() -> None:
    """Render the logo on the login page (centered, larger)."""
    tag = _logo_img_tag(max_width=320)
    if tag:
        st.markdown(f'<div class="login-logo">{tag}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Component helpers
# ---------------------------------------------------------------------------


def neu_card(content_html: str, css_class: str = "neu-card") -> None:
    """Render a neumorphic card with arbitrary HTML content."""
    st.markdown(f'<div class="{css_class}">{content_html}</div>', unsafe_allow_html=True)


def neu_metric(label: str, value: str | int | float) -> None:
    """Render a single KPI metric tile."""
    st.markdown(
        f"""<div class="neu-metric">
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def neu_section_header(title: str) -> None:
    """Render a styled section header."""
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def status_badge(text: str) -> str:
    """Return HTML for a status badge."""
    css_map = {
        "green": "badge-green",
        "yellow": "badge-yellow",
        "red": "badge-red",
        "draft": "badge-draft",
        "published": "badge-published",
        "completed": "badge-completed",
        "skipped": "badge-skipped",
    }
    cls = css_map.get(text.lower(), "badge-gray")
    return f'<span class="badge {cls}">{text}</span>'


def role_badge_html(role: str) -> str:
    """Return HTML for a role badge."""
    css_map = {
        "manager": "role-manager",
        "supervisor": "role-supervisor",
        "visitor": "role-visitor",
        "telesales": "role-telesales",
    }
    cls = css_map.get(role.lower(), "role-manager")
    return f'<span class="role-badge {cls}">{role}</span>'
