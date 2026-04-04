"""White Neumorphism design system for BexLogix Streamlit UI."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

BG = "#F2F4F7"
SURFACE = "#E8ECF1"
SHADOW_DARK = "#ccd0d8"
SHADOW_LIGHT = "#ffffff"
TEXT_PRIMARY = "#2C3E50"
TEXT_SECONDARY = "#5A6878"  # FIX: [A11Y-01] WCAG contrast-compliant secondary text color.
ACCENT = "#3D5FCC"  # FIX: [A11Y-01] WCAG contrast-compliant accent color.

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_GLOBAL_CSS_CACHE: str | None = None

_STATUS_DISPLAY = {
    "green": "✓ سبز",  # FIX: [A11Y-03] Add icon + shape for color-blind safety.
    "yellow": "! زرد",
    "red": "✕ قرمز",
    "draft": "○ پیش‌نویس",
    "supervisor_approved": "◉ تأیید سرپرست",
    "published": "● منتشرشده",
    "completed": "✓ تکمیل‌شده",
    "skipped": "✕ ردشده",
}

_ROLE_DISPLAY = {
    "manager": "مدیر",
    "supervisor": "سرپرست",
    "visitor": "ویزیتور",
    "telesales": "فروش تلفنی",
}


def _build_global_css() -> str:
    return f"""
<style>
:root {{
    --bex-bg: {BG};
    --bex-surface: {SURFACE};
    --bex-shadow-dark: {SHADOW_DARK};
    --bex-shadow-light: {SHADOW_LIGHT};
    --bex-text-primary: {TEXT_PRIMARY};
    --bex-text-secondary: {TEXT_SECONDARY};
    --bex-accent: {ACCENT};
}}

html,
body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stMarkdownContainer"],
input,
textarea,
select,
button,
label,
table,
th,
td,
p,
li {{
    font-family: 'Vazirmatn', 'IRANSansFaNum', 'IRANSans FaNum', 'IRAN Sans', 'Tahoma', 'Segoe UI', sans-serif !important;
}}

/* FIX: Ensure dropdown/date popovers also use Persian font stack. */
[data-baseweb="select"] *,
[data-baseweb="popover"] *,
[role="listbox"] *,
[role="option"],
[data-testid="stPopover"] * {{
    font-family: 'Vazirmatn', 'IRANSansFaNum', 'IRANSans FaNum', 'IRAN Sans', 'Tahoma', 'Segoe UI', sans-serif !important;
}}

/* FIX: Keep material ligature icons rendered as icons, not raw keyboard_arrow_down text. */
.material-symbols-rounded,
.material-symbols-outlined,
.material-icons,
[data-testid="stExpanderToggleIcon"] * {{
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 24px !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    direction: ltr !important;
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24 !important;
}}

html,
body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {{
    background-color: var(--bex-bg) !important;
    direction: rtl !important;
    text-align: right !important;
    color: var(--bex-text-primary) !important;
}}

[data-testid="stMainBlockContainer"] {{
    padding-top: 2rem !important;
    padding-right: 1.2rem !important;
    padding-left: 1.2rem !important;
}}

[data-testid="stHeader"] {{
    background-color: var(--bex-bg) !important;
}}

section[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarNav"] {{
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
    max-width: 0 !important;
    opacity: 0 !important;
    visibility: hidden !important;
}}

[data-testid="stHeadingWithActionElements"] [data-testid="stHeaderActionElements"] {{
    display: none !important;
}}

.page-title {{
    margin: 0 0 0.45rem 0;
    font-size: 2.45rem;
    font-weight: 700;
    line-height: 1.22;
    color: var(--bex-text-primary);
    text-align: right;
}}

.date-input-label {{
    margin: 0.2rem 0 0.35rem;
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--bex-text-primary);
    text-align: right;
}}

.jalali-selected-caption {{
    margin: 0.25rem 0 0.65rem;
    color: var(--bex-text-secondary);
    font-size: 0.95rem;
    line-height: 1.7;
    text-align: right !important;
    direction: rtl !important;
}}

/* FIX: Keep today's shortcut compact and aligned to the right side. */
div[class*="st-key-"][class*="_today_shortcut"] {{
    display: flex !important;
    justify-content: flex-end !important;
}}
div[class*="st-key-"][class*="_today_shortcut"] > div {{
    width: auto !important;
}}
div[class*="st-key-"][class*="_today_shortcut"] button {{
    width: auto !important;
    min-width: 118px !important;
    padding-left: 0.9rem !important;
    padding-right: 0.9rem !important;
}}

.app-user-mini {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.3rem;
    background: var(--bex-bg);
    border-radius: 12px;
    padding: 0.45rem 0.5rem;
    box-shadow: 4px 4px 10px var(--bex-shadow-dark), -4px -4px 10px var(--bex-shadow-light);
    margin-top: 0;
    margin-bottom: 0.45rem;
    width: 100%;
    min-width: 140px;
    max-width: 100%;
    box-sizing: border-box;
}}

.app-user-shell {{
    width: 100%;
    max-width: 100%;
    display: flex;
    direction: ltr;
    justify-content: flex-start;
}}

.topbar-spacer {{
    height: 0.1rem;
}}

.app-user-mini-name {{
    font-size: 0.85rem;
    font-weight: 700;
    line-height: 1.1;
}}

.st-key-logout_topbar button {{
    width: 100% !important;
    min-width: 140px !important;
    margin: 0 !important;
    box-sizing: border-box !important;
}}

.main-logo,
.login-logo {{
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 0.65rem auto 1rem;
    width: 100%;
}}

.main-logo-shell,
.login-logo-shell {{
    display: inline-block;
    width: auto;
    max-width: max-content;
    background: var(--bex-bg);
    border-radius: 14px;
    padding: 0.38rem 0.6rem;
    box-shadow: 4px 4px 10px var(--bex-shadow-dark), -4px -4px 10px var(--bex-shadow-light);
}}

.main-logo img,
.login-logo img {{
    max-width: 320px;
    display: block;
    height: auto;
}}

.login-title-block {{
    text-align: center;
    margin-bottom: 0.9rem;
}}

.login-title-main {{
    margin: 0 0 0.25rem 0;
    font-size: 2.4rem;
    font-weight: 700;
    line-height: 1.22;
    color: var(--bex-text-primary);
}}

.login-title-sub {{
    color: var(--bex-text-secondary);
    font-size: 0.95rem;
    margin: 0;
}}

.login-footer-powered {{
    text-align: center;
    color: #7a8492;
    font-size: 0.78rem;
    margin-top: 1.2rem;
}}

.panel-description {{
    margin: 0.12rem 0 0.3rem;
    color: var(--bex-text-secondary);
    font-size: 0.95rem;
    line-height: 1.95;
    text-align: right !important;
    direction: rtl !important;
}}

.panel-description-columns {{
    margin: 0 0 0.85rem;
    color: #607c5d;
    font-size: 0.88rem;
    line-height: 1.8;
    text-align: right !important;
    direction: rtl !important;
}}

/* FIX: [UX-06] Ordered checklist alignment in pipeline status box. */
.pipeline-checklist-left,
.pipeline-checklist-right {{
    direction: rtl !important;
    text-align: right !important;
    line-height: 2 !important;
    font-size: 0.96rem !important;
    color: var(--bex-text-primary) !important;
    padding: 0.2rem 0.35rem 0.35rem 0.25rem;
    width: 100% !important;
}}

[data-testid="stStatusWidget"] [data-testid="stMarkdownContainer"] {{
    direction: rtl !important;
    text-align: right !important;
}}

.pipeline-progress-wrap {{
    direction: rtl !important;
    text-align: right !important;
    margin-top: 0.3rem;
}}

.pipeline-progress-label {{
    font-size: 0.92rem;
    color: var(--bex-text-primary);
    margin-bottom: 0.2rem;
    font-weight: 700;
}}

.pipeline-progress-track {{
    width: 100%;
    height: 10px;
    border-radius: 999px;
    background: #d8dde5;
    position: relative;
    overflow: hidden;
    direction: rtl !important;
}}

.pipeline-progress-fill {{
    position: absolute;
    right: 0;
    left: auto;
    top: 0;
    bottom: 0;
    border-radius: 999px;
    background: linear-gradient(90deg, #3D5FCC 0%, #6f87d7 100%);
    transform-origin: right center;
    transition: width 240ms ease;
}}

.pipeline-progress-note {{
    direction: rtl !important;
    text-align: right !important;
    margin-top: 0.5rem;
    font-size: 0.9rem;
    color: var(--bex-text-secondary);
    line-height: 1.8;
}}

/* FIX: [UX-09] Visitor progress must be RTL with right-aligned note text. */
.visitor-progress-wrap {{
    direction: rtl !important;
    text-align: right !important;
    margin: 0.3rem 0 0.9rem;
}}

.visitor-progress-track {{
    width: 100%;
    height: 10px;
    border-radius: 999px;
    background: #d8dde5;
    position: relative;
    overflow: hidden;
    direction: rtl !important;
}}

.visitor-progress-fill {{
    position: absolute;
    right: 0;
    left: auto;
    top: 0;
    bottom: 0;
    border-radius: 999px;
    transform-origin: right center;
    transition: width 240ms ease;
}}

.visitor-progress-note {{
    margin-top: 0.45rem;
    color: var(--bex-text-secondary);
    font-size: 0.92rem;
    font-weight: 600;
    text-align: right !important;
    direction: rtl !important;
}}

.hourglass-spin {{
    display: inline-block;
    animation: hourglass-wobble 1.1s ease-in-out infinite;
    transform-origin: center;
}}

@keyframes hourglass-wobble {{
    0% {{ transform: rotate(0deg) scale(1); }}
    25% {{ transform: rotate(-18deg) scale(1.05); }}
    50% {{ transform: rotate(0deg) scale(1); }}
    75% {{ transform: rotate(18deg) scale(1.05); }}
    100% {{ transform: rotate(0deg) scale(1); }}
}}

.ltr-inline {{
    direction: ltr;
    unicode-bidi: bidi-override;
    text-align: left;
    display: inline-block;
}}

.section-gap {{
    height: 0.85rem;
}}

.section-gap-lg {{
    height: 1.35rem;
}}

.neu-card {{
    background: var(--bex-bg);
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
    box-shadow: 6px 6px 14px var(--bex-shadow-dark), -6px -6px 14px var(--bex-shadow-light);
}}

.neu-card-flat {{
    background: var(--bex-bg);
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: 3px 3px 8px var(--bex-shadow-dark), -3px -3px 8px var(--bex-shadow-light);
}}

.neu-metric {{
    background: var(--bex-bg);
    border-radius: 16px;
    padding: 1.2rem 1rem;
    text-align: center;
    box-shadow: 5px 5px 12px var(--bex-shadow-dark), -5px -5px 12px var(--bex-shadow-light);
    min-height: 100px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}}

.neu-metric .metric-value {{
    font-size: 1.9rem;
    font-weight: 700;
    color: var(--bex-text-primary);
    line-height: 1.2;
}}

.neu-metric .metric-label {{
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--bex-text-primary); /* FIX: [A11Y-01] Use primary color for metric labels. */
    margin-top: 0.35rem;
}}

.neu-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 0.9rem;
    margin-bottom: 0.8rem;
}}

div.stButton > button,
div.stFormSubmitButton > button,
div.stDownloadButton > button {{
    border: none !important;
    border-radius: 12px !important;
    box-shadow: 4px 4px 10px var(--bex-shadow-dark), -4px -4px 10px var(--bex-shadow-light) !important;
    font-weight: 600 !important;
    min-height: 44px !important; /* FIX: [A11Y-05] Minimum touch target. */
}}

div.stButton > button {{
    background: var(--bex-bg) !important;
    color: var(--bex-text-primary) !important;
    padding: 0.55rem 1.2rem !important;
}}

div.stFormSubmitButton > button {{
    background: var(--bex-accent) !important;
    color: #fff !important;
    padding: 0.55rem 2rem !important;
}}

div.stDownloadButton > button {{
    background: var(--bex-bg) !important;
    border: 1px solid var(--bex-surface) !important;
    color: var(--bex-text-primary) !important;
}}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div,
input[type="text"],
input[type="password"],
input[type="date"] {{
    border-radius: 10px !important;
    border: none !important;
    box-shadow: inset 2px 2px 5px var(--bex-shadow-dark), inset -2px -2px 5px var(--bex-shadow-light) !important;
    background: var(--bex-bg) !important;
}}

[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
input[type="text"],
input[type="password"],
textarea {{
    direction: auto !important;
    unicode-bidi: plaintext !important;
    text-align: start !important;
}}

[data-testid="stFileUploaderDropzone"] {{
    direction: rtl !important;
    text-align: right !important;
    min-height: 44px !important; /* FIX: [A11Y-05] Minimum touch target for upload zone. */
}}

[data-testid="stFileUploaderDropzone"] button {{
    min-height: 44px !important;
}}

details[data-testid="stExpander"] {{
    background: var(--bex-bg) !important;
    border: none !important;
    border-radius: 14px !important;
    box-shadow: 4px 4px 10px var(--bex-shadow-dark), -4px -4px 10px var(--bex-shadow-light) !important;
    margin-bottom: 0.8rem;
}}

details[data-testid="stExpander"] summary {{
    direction: rtl !important;
    text-align: right !important;
    font-size: 1.08rem !important;
}}

/* FIX: [A11Y-02] Expander icon is intentionally visible for accessibility. */
[data-testid="stExpanderToggleIcon"] {{
    display: inline-flex !important;
}}

details[data-testid="stExpander"] [data-testid="stCaptionContainer"],
details[data-testid="stExpander"] [data-testid="stCaptionContainer"] *,
details[data-testid="stExpander"] .stCaptionContainer,
details[data-testid="stExpander"] .stCaptionContainer * {{
    direction: rtl !important;
    text-align: right !important;
    line-height: 1.9 !important;
}}

.telesales-detail-line {{
    direction: rtl !important;
    text-align: right !important;
    margin: 0.35rem 0 !important;
    color: var(--bex-text-primary);
}}

[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden;
    box-shadow: 3px 3px 8px var(--bex-shadow-dark), -3px -3px 8px var(--bex-shadow-light) !important;
}}

.badge {{
    display: inline-block;
    padding: 0.22rem 0.7rem;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
}}

.badge-green  {{ background: #d4edda; color: #155724; }}
.badge-yellow {{ background: #fff3cd; color: #856404; }}
.badge-red    {{ background: #f8d7da; color: #721c24; }}
.badge-gray   {{ background: #e2e3e5; color: #383d41; }}
.badge-draft     {{ background: #e2e3e5; color: #383d41; }}
.badge-supervisor-approved {{ background: #e0e7ff; color: #3730a3; }}
.badge-published {{ background: #cce5ff; color: #004085; }}
.badge-completed {{ background: #d4edda; color: #155724; }}
.badge-skipped   {{ background: #f8d7da; color: #721c24; }}

.section-header {{
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--bex-text-primary);
    margin-bottom: 0.6rem;
    padding-bottom: 0.3rem;
    border-bottom: 2px solid var(--bex-surface);
    text-align: right !important;
    direction: rtl !important;
}}

.role-badge {{
    display: inline-block;
    padding: 0.2rem 0.8rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
}}

.role-manager    {{ background: #dbeafe; color: #1e40af; }}
.role-supervisor {{ background: #fef3c7; color: #92400e; }}
.role-visitor    {{ background: #d1fae5; color: #065f46; }}
.role-telesales  {{ background: #ede9fe; color: #5b21b6; }}

.monitoring-bar {{
    background: #dbeafe;
    color: #1e40af;
    border-radius: 10px;
    padding: 0.6rem 1rem;
    font-weight: 600;
    font-size: 0.85rem;
    text-align: center;
    margin-bottom: 1rem;
    box-shadow: inset 2px 2px 5px rgba(0,0,0,0.06), inset -2px -2px 5px rgba(255,255,255,0.8);
}}

button[data-baseweb="tab"] {{
    border-radius: 10px 10px 0 0 !important;
    font-weight: 600 !important;
}}

#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
</style>
"""


def inject_global_css() -> None:
    # FIX: [ARCH-05] Load robust Persian font via CDN with local IRANSans fallback.
    st.markdown(
        '<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">',
        unsafe_allow_html=True,
    )

    global _GLOBAL_CSS_CACHE
    if _GLOBAL_CSS_CACHE is None:
        _GLOBAL_CSS_CACHE = _build_global_css()
    st.markdown(_GLOBAL_CSS_CACHE, unsafe_allow_html=True)


def _logo_img_tag(max_width: int = 280) -> str | None:
    for extension, mime in [
        ("png", "image/png"),
        ("jpg", "image/jpeg"),
        ("jpeg", "image/jpeg"),
        ("svg", "image/svg+xml"),
    ]:
        path = _ASSETS_DIR / f"logo.{extension}"
        if path.exists():
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return (
                f'<img src="data:{mime};base64,{encoded}" alt="BexLogix" '
                f'style="max-width:{max_width}px;height:auto;">'
            )
    return None


def render_sidebar_logo() -> None:
    tag = _logo_img_tag(max_width=180)
    if tag:
        st.markdown(f'<div class="main-logo"><div class="main-logo-shell">{tag}</div></div>', unsafe_allow_html=True)


def render_login_logo() -> None:
    tag = _logo_img_tag(max_width=320)
    if tag:
        st.markdown(
            f'<div class="login-logo"><div class="login-logo-shell">{tag}</div></div>',
            unsafe_allow_html=True,
        )


def render_main_logo(max_width: int = 220) -> None:
    tag = _logo_img_tag(max_width=max_width)
    if tag:
        st.markdown(
            f'<div class="main-logo"><div class="main-logo-shell">{tag}</div></div>',
            unsafe_allow_html=True,
        )


def neu_card(content_html: str, css_class: str = "neu-card") -> None:
    st.markdown(f'<div class="{css_class}">{content_html}</div>', unsafe_allow_html=True)


def neu_metric(label: str, value: str | int | float) -> None:
    st.markdown(
        f"""<div class="neu-metric">
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_metric_grid(items: list[tuple[str, str | int | float]]) -> None:
    # FIX: [A11Y-04] Responsive KPI grid replacing fixed 5-column layout.
    tiles = []
    for label, value in items:
        tiles.append(
            f"""<div class="neu-metric">
                <div class="metric-value">{value}</div>
                <div class="metric-label">{label}</div>
            </div>"""
        )
    html_block = '<div class="neu-kpi-grid">' + "".join(tiles) + "</div>"
    st.markdown(html_block, unsafe_allow_html=True)


def neu_section_header(title: str) -> None:
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def render_page_title(title: str) -> None:
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)


def render_panel_description(text: str) -> None:
    st.markdown(f'<div class="panel-description">{text}</div>', unsafe_allow_html=True)


def render_panel_columns_description(text: str) -> None:
    st.markdown(f'<div class="panel-description-columns">{text}</div>', unsafe_allow_html=True)


def status_badge(text: str) -> str:
    normalized = str(text or "").strip().lower()
    css_map = {
        "green": "badge-green",
        "yellow": "badge-yellow",
        "red": "badge-red",
        "draft": "badge-draft",
        "supervisor_approved": "badge-supervisor-approved",
        "published": "badge-published",
        "completed": "badge-completed",
        "skipped": "badge-skipped",
    }
    css_class = css_map.get(normalized, "badge-gray")
    display_text = _STATUS_DISPLAY.get(normalized, text)
    return f'<span class="badge {css_class}">{display_text}</span>'


def role_badge_html(role: str) -> str:
    normalized = str(role or "").strip().lower()
    css_map = {
        "manager": "role-manager",
        "supervisor": "role-supervisor",
        "visitor": "role-visitor",
        "telesales": "role-telesales",
    }
    css_class = css_map.get(normalized, "role-manager")
    display_text = _ROLE_DISPLAY.get(normalized, role)
    return f'<span class="role-badge {css_class}">{display_text}</span>'
