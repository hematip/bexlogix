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
TEXT_SECONDARY = "#6C7A89"
ACCENT = "#5B7FFF"

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_WINDOWS_FONTS_DIR = Path("C:/Windows/Fonts")
_GLOBAL_CSS_CACHE: str | None = None

_STATUS_DISPLAY = {
    "green": "سبز",
    "yellow": "زرد",
    "red": "قرمز",
    "draft": "پیش‌نویس",
    "published": "منتشرشده",
    "completed": "تکمیل‌شده",
    "skipped": "ردشده",
}

_ROLE_DISPLAY = {
    "manager": "مدیر",
    "supervisor": "سرپرست",
    "visitor": "ویزیتور",
    "telesales": "فروش تلفنی",
}


def _font_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    suffix = path.suffix.lower()
    mime = {
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }.get(suffix)
    if not mime:
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _find_first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _build_font_face_css() -> str:
    regular_font = _find_first_existing(
        [
            _ASSETS_DIR / "fonts" / "IRANSansFaNum-Regular.ttf",
            _ASSETS_DIR / "fonts" / "IRANSansFaNum.ttf",
            _WINDOWS_FONTS_DIR / "IRANSans(FaNum).ttf",
            _WINDOWS_FONTS_DIR / "IRANSans FaNum.ttf",
            _WINDOWS_FONTS_DIR / "IRAN Sans.ttf",
        ]
    )
    bold_font = _find_first_existing(
        [
            _ASSETS_DIR / "fonts" / "IRANSansFaNum-Bold.ttf",
            _WINDOWS_FONTS_DIR / "IRANSans(FaNum) Bold.ttf",
            _WINDOWS_FONTS_DIR / "IRANSans FaNum Bold.ttf",
            _WINDOWS_FONTS_DIR / "IRAN Sans Bold.ttf",
        ]
    )

    regular_uri = _font_data_uri(regular_font) if regular_font else None
    bold_uri = _font_data_uri(bold_font) if bold_font else None

    regular_src = (
        f"url('{regular_uri}') format('truetype')"
        if regular_uri
        else "local('IRANSans FaNum'), local('IRANSans(FaNum)'), local('IRAN Sans')"
    )
    bold_src = (
        f"url('{bold_uri}') format('truetype')"
        if bold_uri
        else "local('IRANSans FaNum Bold'), local('IRANSans(FaNum) Bold'), local('IRAN Sans Bold')"
    )

    return f"""
@font-face {{
    font-family: 'IRANSansFaNum';
    src: {regular_src};
    font-style: normal;
    font-weight: 400;
    font-display: swap;
}}
@font-face {{
    font-family: 'IRANSansFaNum';
    src: {bold_src};
    font-style: normal;
    font-weight: 700;
    font-display: swap;
}}
"""


def _build_global_css() -> str:
    font_face_css = _build_font_face_css()
    return f"""
<style>
{font_face_css}

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
    font-family: 'IRANSansFaNum', 'IRANSans FaNum', 'IRAN Sans', 'Tahoma', 'Segoe UI', sans-serif !important;
}}

.material-symbols-rounded,
.material-symbols-outlined,
.material-icons,
[class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
    font-style: normal !important;
    font-weight: normal !important;
    font-size: 20px !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    direction: ltr !important;
    display: inline-block !important;
    -webkit-font-feature-settings: 'liga';
    -webkit-font-smoothing: antialiased;
    font-feature-settings: 'liga';
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

.app-user-mini {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.3rem;
    background: var(--bex-bg);
    border-radius: 12px;
    padding: 0.52rem 0.55rem;
    box-shadow: 4px 4px 10px var(--bex-shadow-dark), -4px -4px 10px var(--bex-shadow-light);
    margin-top: 0;
    margin-bottom: 0.45rem;
    width: 100%;
    min-width: 165px;
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

.st-key-logout_topbar {{
    width: 100%;
    max-width: 100%;
}}

.st-key-logout_topbar > div {{
    width: 100%;
}}

.st-key-logout_topbar button {{
    width: 100% !important;
    min-width: 165px !important;
    margin: 0 !important;
    box-sizing: border-box !important;
}}

.main-logo {{
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 0.35rem 0 1rem;
}}

.main-logo-shell {{
    display: inline-block;
    align-items: center;
    justify-content: center;
    width: auto;
    max-width: max-content;
    padding: 0.38rem 0.6rem;
    border-radius: 14px;
    background: var(--bex-bg);
    box-shadow: 4px 4px 10px var(--bex-shadow-dark), -4px -4px 10px var(--bex-shadow-light);
}}

.main-logo img {{
    max-width: 320px;
    display: block;
    height: auto;
}}

.login-logo {{
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
    margin: 0.65rem auto 1rem;
    overflow: visible !important;
}}

.login-logo-shell {{
    display: inline-block;
    width: auto;
    max-width: max-content;
    background: var(--bex-bg);
    border-radius: 14px;
    padding: 0.38rem 0.6rem;
    box-shadow: 4px 4px 10px var(--bex-shadow-dark), -4px -4px 10px var(--bex-shadow-light);
}}

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
    color: #9CA3AF;
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
    color: #7d916f;
    font-size: 0.88rem;
    line-height: 1.8;
    text-align: right !important;
    direction: rtl !important;
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
    color: var(--bex-text-secondary);
    margin-top: 0.35rem;
}}

div.stButton > button,
div.stFormSubmitButton > button,
div.stDownloadButton > button {{
    border: none !important;
    border-radius: 12px !important;
    box-shadow: 4px 4px 10px var(--bex-shadow-dark), -4px -4px 10px var(--bex-shadow-light) !important;
    font-weight: 600 !important;
}}

div.stButton > button {{
    background: var(--bex-bg) !important;
    color: var(--bex-text-primary) !important;
    padding: 0.55rem 1.6rem !important;
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
}}

[data-testid="stFileUploaderDropzone"] button {{
    direction: rtl !important;
    text-align: center !important;
}}

[data-testid="stFileUploaderDropzone"] button * {{
    display: none !important;
}}

[data-testid="stFileUploaderDropzone"] button::after {{
    content: "آپلود فایل";
    display: inline-block;
    font-weight: 700;
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

details[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
details[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] * {{
    direction: rtl !important;
    text-align: right !important;
    font-size: 1.08rem !important;
}}

details[data-testid="stExpander"] summary > div:first-child,
details[data-testid="stExpander"] summary > span:first-child,
details[data-testid="stExpander"] summary [aria-hidden="true"] {{
    display: none !important;
}}

[data-testid="stExpanderToggleIcon"],
[data-testid="stExpanderToggleIcon"] *,
details[data-testid="stExpander"] summary [data-testid="stExpanderIcon"],
details[data-testid="stExpander"] summary [data-testid*="Expander"][data-testid*="Icon"],
details[data-testid="stExpander"] summary .material-symbols-rounded,
details[data-testid="stExpander"] summary .material-symbols-outlined,
details[data-testid="stExpander"] summary .material-icons,
details[data-testid="stExpander"] summary .notranslate {{
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
    visibility: hidden !important;
    opacity: 0 !important;
}}

details[data-testid="stExpander"] summary::-webkit-details-marker {{
    display: none !important;
}}

details[data-testid="stExpander"] summary::marker {{
    content: "" !important;
}}

[data-baseweb="select"] *:not(.material-icons):not(.material-symbols-rounded):not(.material-symbols-outlined),
[role="listbox"] *:not(.material-icons):not(.material-symbols-rounded):not(.material-symbols-outlined),
[data-baseweb="popover"] *:not(.material-icons):not(.material-symbols-rounded):not(.material-symbols-outlined) {{
    font-family: 'IRANSansFaNum', 'IRANSans FaNum', 'IRAN Sans', 'Tahoma', 'Segoe UI', sans-serif !important;
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
    font-weight: 600;
}}

.badge-green  {{ background: #d4edda; color: #155724; }}
.badge-yellow {{ background: #fff3cd; color: #856404; }}
.badge-red    {{ background: #f8d7da; color: #721c24; }}
.badge-gray   {{ background: #e2e3e5; color: #383d41; }}
.badge-draft     {{ background: #e2e3e5; color: #383d41; }}
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


def neu_section_header(title: str) -> None:
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def status_badge(text: str) -> str:
    normalized = str(text or "").strip().lower()
    css_map = {
        "green": "badge-green",
        "yellow": "badge-yellow",
        "red": "badge-red",
        "draft": "badge-draft",
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
