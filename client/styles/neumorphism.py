# Purpose: Global neumorphic design system and UI helper registry.
# Workflow Role: Provides reusable styling primitives across all Streamlit pages.
"""White Neumorphism design system for BexLogix Streamlit UI."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from client.i18n import align, direction, get_language, is_fa, start_side

BG = "#F2F4F7"
SURFACE = "#E8ECF1"
SHADOW_DARK = "#ccd0d8"
SHADOW_LIGHT = "#ffffff"
TEXT_PRIMARY = "#2C3E50"
TEXT_SECONDARY = "#5A6878"  # FIX: [A11Y-01] WCAG contrast-compliant secondary text color.
ACCENT_FA = "#3D5FCC"  # FIX: [A11Y-01] WCAG contrast-compliant accent color.
ACCENT_EN = "#D9A300"
ACCENT_GRADIENT_FA = "#6F87D7"
ACCENT_GRADIENT_EN = "#F3CF62"

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts"
_GLOBAL_CSS_CACHE: dict[str, str] = {}

_STATUS_DISPLAY_FA = {
    "green": "✓ سبز",  # FIX: [A11Y-03] Add icon + shape for color-blind safety.
    "yellow": "! زرد",
    "red": "✕ قرمز",
    "draft": "○ پیش‌نویس",
    "supervisor_approved": "◉ تأیید سرپرست",
    "published": "● منتشرشده",
    "completed": "✓ تکمیل‌شده",
    "skipped": "✕ ردشده",
}

_STATUS_DISPLAY_EN = {
    "green": "✓ Green",
    "yellow": "! Yellow",
    "red": "✕ Red",
    "draft": "○ Draft",
    "supervisor_approved": "◉ Supervisor Approved",
    "published": "● Published",
    "completed": "✓ Completed",
    "skipped": "✕ Skipped",
}

_ROLE_DISPLAY_FA = {
    "manager": "مدیر",
    "supervisor": "سرپرست",
    "visitor": "ویزیتور",
    "telesales": "فروش تلفنی",
}

_ROLE_DISPLAY_EN = {
    "manager": "Manager",
    "supervisor": "Supervisor",
    "visitor": "Visitor",
    "telesales": "Telesales",
}


def _build_local_font_face_css() -> str:
    # FIX: [OFFLINE-02] Load Persian fonts from local assets and remove runtime CDN dependency.
    font_defs: list[str] = []
    candidates = [
        ("400", "Vazirmatn-Regular.ttf"),
        ("700", "Vazirmatn-Bold.ttf"),
    ]
    for weight, filename in candidates:
        font_path = _FONTS_DIR / filename
        if not font_path.exists():
            continue
        encoded = base64.b64encode(font_path.read_bytes()).decode("ascii")
        font_defs.append(
            f"""
@font-face {{
    font-family: 'Vazirmatn';
    font-style: normal;
    font-weight: {weight};
    src: url(data:font/ttf;base64,{encoded}) format('truetype');
    font-display: swap;
}}"""
        )
    return "".join(font_defs)


def _build_global_css() -> str:
    font_face_css = _build_local_font_face_css()
    rtl_layout = is_fa()
    flow_direction = direction()
    text_align = align()
    start_edge = start_side()
    end_edge = "left" if start_edge == "right" else "right"
    accent = ACCENT_FA if rtl_layout else ACCENT_EN
    accent_gradient = ACCENT_GRADIENT_FA if rtl_layout else ACCENT_GRADIENT_EN
    accent_soft = "#DBEAFE" if rtl_layout else "#FFF4CC"
    accent_text = "#1E40AF" if rtl_layout else "#8A6A00"
    accent_soft_alt = "#E0E7FF" if rtl_layout else "#FFF0B3"
    accent_text_alt = "#3730A3" if rtl_layout else "#8C6F00"
    base_font_stack = (
        "'Vazirmatn', 'IRANSansFaNum', 'IRANSans FaNum', 'IRAN Sans', 'Tahoma', 'Segoe UI', sans-serif"
        if rtl_layout
        else "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
    )
    today_shortcut_justify = "flex-end" if rtl_layout else "flex-start"
    progress_fill_anchor_css = (
        f"{start_edge}: 0; {end_edge}: auto; transform-origin: {start_edge} center;"
    )
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
    --bex-accent: {accent};
    --bex-accent-soft: {accent_soft};
    --bex-accent-soft-alt: {accent_soft_alt};
    --bex-accent-text: {accent_text};
    --bex-accent-text-alt: {accent_text_alt};
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
    font-family: {base_font_stack} !important;
}}

/* FIX: Ensure dropdown/date popovers also use Persian font stack. */
[data-baseweb="select"] *,
[data-baseweb="popover"] *,
[role="listbox"] *,
[role="option"],
[data-testid="stPopover"] * {{
    font-family: {base_font_stack} !important;
}}

/* FIX: [OFFLINE-02] Replace material-ligature dependency with local CSS arrows. */
[data-baseweb="select"] span.material-icons,
[data-baseweb="select"] span.material-symbols-rounded,
[data-testid="stExpanderToggleIcon"] span {{
    font-size: 0 !important;
    line-height: 0 !important;
    width: 1rem !important;
    height: 1rem !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
[data-baseweb="select"] span.material-icons::before,
[data-baseweb="select"] span.material-symbols-rounded::before,
[data-testid="stExpanderToggleIcon"] span::before {{
    content: "▾";
    font-size: 0.95rem;
    line-height: 1;
    color: var(--bex-text-secondary);
}}
details[data-testid="stExpander"][open] [data-testid="stExpanderToggleIcon"] span::before {{
    content: "▴";
}}

html,
body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {{
    background-color: var(--bex-bg) !important;
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
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
    text-align: {text_align};
}}

.date-input-label {{
    margin: 0.2rem 0 0.35rem;
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--bex-text-primary);
    text-align: {text_align};
}}

.jalali-selected-caption {{
    margin: 0.25rem 0 0.65rem;
    color: var(--bex-text-secondary);
    font-size: 0.95rem;
    line-height: 1.7;
    text-align: {text_align} !important;
    direction: {flow_direction} !important;
}}

/* FIX: Keep today's shortcut compact and aligned to the right side. */
div[class*="st-key-"][class*="_today_shortcut"] {{
    display: flex !important;
    justify-content: {today_shortcut_justify} !important;
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
    text-align: {text_align} !important;
    direction: {flow_direction} !important;
}}

.panel-description-columns {{
    margin: 0 0 0.85rem;
    color: #607c5d;
    font-size: 0.88rem;
    line-height: 1.8;
    text-align: {text_align} !important;
    direction: {flow_direction} !important;
}}

/* FIX: [UX-06] Ordered checklist alignment in pipeline status box. */
.pipeline-checklist-left,
.pipeline-checklist-right {{
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
    line-height: 2 !important;
    font-size: 0.96rem !important;
    color: var(--bex-text-primary) !important;
    padding: 0.2rem 0.35rem 0.35rem 0.25rem;
    width: 100% !important;
}}

[data-testid="stStatusWidget"] [data-testid="stMarkdownContainer"] {{
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
}}

.pipeline-progress-wrap {{
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
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
    direction: {flow_direction} !important;
}}

.pipeline-progress-fill {{
    position: absolute;
    {progress_fill_anchor_css}
    top: 0;
    bottom: 0;
    border-radius: 999px;
    background: linear-gradient(90deg, {accent} 0%, {accent_gradient} 100%);
    transition: width 240ms ease;
}}

.pipeline-progress-note {{
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
    margin-top: 0.5rem;
    font-size: 0.9rem;
    color: var(--bex-text-secondary);
    line-height: 1.8;
}}

/* FIX: [UX-09] Visitor progress must be RTL with right-aligned note text. */
.visitor-progress-wrap {{
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
    margin: 0.3rem 0 0.9rem;
}}

.visitor-progress-track {{
    width: 100%;
    height: 10px;
    border-radius: 999px;
    background: #d8dde5;
    position: relative;
    overflow: hidden;
    direction: {flow_direction} !important;
}}

.visitor-progress-fill {{
    position: absolute;
    {progress_fill_anchor_css}
    top: 0;
    bottom: 0;
    border-radius: 999px;
    transition: width 240ms ease;
}}

.visitor-progress-note {{
    margin-top: 0.45rem;
    color: var(--bex-text-secondary);
    font-size: 0.92rem;
    font-weight: 600;
    text-align: {text_align} !important;
    direction: {flow_direction} !important;
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

/* FIX: Standardize checkbox spacing/alignment for confirmation rows. */
[data-testid="stCheckbox"] {{
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
    margin-top: 0.2rem !important;
}}
[data-testid="stCheckbox"] > label {{
    direction: {flow_direction} !important;
    display: inline-flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: flex-start !important;
    column-gap: 0.45rem !important;
    row-gap: 0 !important;
    min-height: 40px !important;
    line-height: 1.8 !important;
    padding-{start_edge}: 0.25rem !important;
    cursor: pointer !important;
}}
[data-testid="stCheckbox"] input[type="checkbox"] {{
    width: 18px !important;
    height: 18px !important;
    margin: 0 !important;
}}
[data-testid="stCheckbox"] > label > div:last-child {{
    margin-{start_edge}: 0.18rem !important;
}}
[data-testid="stCheckbox"] span {{
    margin: 0 !important;
}}

/* FIX: Selectbox search must auto-switch direction (Persian RTL / English LTR). */
[data-baseweb="select"] input {{
    direction: auto !important;
    unicode-bidi: plaintext !important;
    text-align: start !important;
}}
[data-baseweb="select"] input::placeholder {{
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
}}

[data-testid="stFileUploaderDropzone"] {{
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
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
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
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
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
    line-height: 1.9 !important;
}}

.telesales-detail-line {{
    direction: {flow_direction} !important;
    text-align: {text_align} !important;
    margin: 0.35rem 0 !important;
    color: var(--bex-text-primary);
}}

[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden;
    box-shadow: 3px 3px 8px var(--bex-shadow-dark), -3px -3px 8px var(--bex-shadow-light) !important;
}}

/* FIX: Center all dataframe cells/headers and keep Persian-friendly visual alignment. */
[data-testid="stDataFrame"] [role="grid"] {{
    direction: {flow_direction} !important;
}}

[data-testid="stDataFrame"] [role="columnheader"],
[data-testid="stDataFrame"] [role="gridcell"] {{
    text-align: center !important;
    justify-content: center !important;
    align-items: center !important;
}}

[data-testid="stDataFrame"] [role="columnheader"] div,
[data-testid="stDataFrame"] [role="gridcell"] div {{
    width: 100% !important;
    text-align: center !important;
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
.badge-supervisor-approved {{ background: var(--bex-accent-soft-alt); color: var(--bex-accent-text-alt); }}
.badge-published {{ background: var(--bex-accent-soft); color: var(--bex-accent-text); }}
.badge-completed {{ background: #d4edda; color: #155724; }}
.badge-skipped   {{ background: #f8d7da; color: #721c24; }}

.section-header {{
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--bex-text-primary);
    margin-bottom: 0.6rem;
    padding-bottom: 0.3rem;
    border-bottom: 2px solid var(--bex-surface);
    text-align: {text_align} !important;
    direction: {flow_direction} !important;
}}

.role-badge {{
    display: inline-block;
    padding: 0.2rem 0.8rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
}}

.role-manager    {{ background: var(--bex-accent-soft); color: var(--bex-accent-text); }}
.role-supervisor {{ background: #fef3c7; color: #92400e; }}
.role-visitor    {{ background: #d1fae5; color: #065f46; }}
.role-telesales  {{ background: #ede9fe; color: #5b21b6; }}

.monitoring-bar {{
    background: var(--bex-accent-soft);
    color: var(--bex-accent-text);
    border-radius: 10px;
    padding: 0.6rem 1rem;
    font-weight: 600;
    font-size: 0.85rem;
    text-align: center;
    margin-bottom: 1rem;
    box-shadow: inset 2px 2px 5px rgba(0,0,0,0.06), inset -2px -2px 5px rgba(255,255,255,0.8);
}}

div[class*="st-key-global_fixed_lang_switch"] {{
    position: fixed !important;
    top: 0.55rem !important;
    left: 0.85rem !important;
    z-index: 10050 !important;
    min-width: 118px !important;
    max-width: 118px !important;
    margin: 0 !important;
    padding: 0.16rem !important;
    border-radius: 10px;
    background: rgba(242, 244, 247, 0.94);
    box-shadow: 2px 2px 6px rgba(204, 208, 216, 0.8), -2px -2px 6px rgba(255, 255, 255, 0.9);
}}

div[class*="st-key-global_fixed_lang_switch"] > div[data-testid="stHorizontalBlock"] {{
    gap: 0.24rem !important;
}}

div[class*="st-key-global_fixed_lang_switch"] button {{
    min-height: 30px !important;
    padding: 0.15rem 0.3rem !important;
    border-radius: 8px !important;
    border: 1px solid #c3cad6 !important;
    background: #eef1f5 !important;
    color: #2c3e50 !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    line-height: 1.1 !important;
}}

div[class*="st-key-global_fixed_lang_switch"] button[kind="primary"] {{
    background: var(--bex-accent) !important;
    color: #ffffff !important;
    border-color: var(--bex-accent) !important;
}}

div[class*="st-key-global_fixed_lang_switch"] [data-testid="stWidgetLabel"] {{
    display: none !important;
}}

button[data-baseweb="tab"] {{
    border-radius: 10px 10px 0 0 !important;
    font-weight: 600 !important;
}}

#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ display: none !important; }}
button[kind="header"] {{ display: none !important; }}
</style>
"""


def inject_global_css() -> None:
    language = get_language()
    if language not in _GLOBAL_CSS_CACHE:
        _GLOBAL_CSS_CACHE[language] = _build_global_css()
    st.markdown(_GLOBAL_CSS_CACHE[language], unsafe_allow_html=True)


def _logo_img_tag(max_width: int = 280) -> str | None:
    language = get_language()
    prefixes = ["logo"] if language == "fa" else ["logo_en", "logo"]
    alt_text = "Bextudio" if language == "fa" else "Helio"
    extensions = [
        ("png", "image/png"),
        ("jpg", "image/jpeg"),
        ("jpeg", "image/jpeg"),
        ("svg", "image/svg+xml"),
    ]
    for prefix in prefixes:
        for extension, mime in extensions:
            path = _ASSETS_DIR / f"{prefix}.{extension}"
            if not path.exists():
                continue
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return (
                f'<img src="data:{mime};base64,{encoded}" alt="{alt_text}" '
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
    display_map = _STATUS_DISPLAY_FA if is_fa() else _STATUS_DISPLAY_EN
    display_text = display_map.get(normalized, text)
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
    display_map = _ROLE_DISPLAY_FA if is_fa() else _ROLE_DISPLAY_EN
    display_text = display_map.get(normalized, role)
    return f'<span class="role-badge {css_class}">{display_text}</span>'
