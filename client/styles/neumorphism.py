# Purpose: Global neumorphic design system and UI helper registry.
# Workflow Role: Provides reusable styling primitives across all Streamlit pages.
"""White Neumorphism design system for BexLogix Streamlit UI."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st

BG = "#ffffff"
SURFACE = "#f5f5f5"
SHADOW_DARK = "#e5e5e5"
SHADOW_LIGHT = "#ffffff"
TEXT_PRIMARY = "#0a0a0a"
TEXT_SECONDARY = "#737373"
ACCENT = "#0e7490"

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts"
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
    return f"""
<style>
{font_face_css}
:root {{
    --bex-background: {BG};
    --bex-foreground: {TEXT_PRIMARY};
    --bex-card: {BG};
    --bex-card-foreground: {TEXT_PRIMARY};
    --bex-muted: {SURFACE};
    --bex-muted-foreground: {TEXT_SECONDARY};
    --bex-border: {SHADOW_DARK};
    --bex-input: {SHADOW_DARK};
    --bex-ring: #a3a3a3;
    --bex-primary: {ACCENT};
    --bex-primary-foreground: #fafafa;
    --bex-secondary: {SURFACE};
    --bex-secondary-foreground: #171717;
    --bex-destructive: #dc2626;
    --bex-destructive-foreground: #fef2f2;
    --bex-destructive-ring: #dc262633;
    --bex-status-green-bg: #d4edda;
    --bex-status-green-fg: #155724;
    --bex-status-yellow-bg: #fff3cd;
    --bex-status-yellow-fg: #856404;
    --bex-status-red-bg: #f8d7da;
    --bex-status-red-fg: #721c24;
    --bex-status-gray-bg: #e2e3e5;
    --bex-status-gray-fg: #383d41;
    --bex-status-approved-bg: #e0e7ff;
    --bex-status-approved-fg: #3730a3;
    --bex-status-published-bg: #cce5ff;
    --bex-status-published-fg: #004085;
    --bex-role-manager-bg: #dbeafe;
    --bex-role-manager-fg: #1e40af;
    --bex-role-supervisor-bg: #fef3c7;
    --bex-role-supervisor-fg: #92400e;
    --bex-role-visitor-bg: #d1fae5;
    --bex-role-visitor-fg: #065f46;
    --bex-role-telesales-bg: #ede9fe;
    --bex-role-telesales-fg: #5b21b6;
    --bex-radius: 10px;
    --bex-radius-md: 8px;
    --bex-radius-lg: 10px;
    --bex-radius-xl: 14px;
    --bex-shadow-xs: 0 1px 2px 0 #0000000d;
    --bex-ring-shadow: 0 0 0 3px #a3a3a380;

    /* Backward-compatible aliases for existing helpers. */
    --bex-bg: var(--bex-background);
    --bex-surface: var(--bex-muted);
    --bex-shadow-dark: var(--bex-border);
    --bex-shadow-light: var(--bex-card);
    --bex-text-primary: var(--bex-foreground);
    --bex-text-secondary: var(--bex-muted-foreground);
    --bex-accent: var(--bex-primary);
    --bex-danger: var(--bex-destructive);
    --bex-login-shell-max: 36rem; /* Bextudio maxWidth/xl: 576px. */
    --bex-login-card-padding: 1.5rem; /* Bextudio spacing/6: 24px. */
    --bex-login-logo-max: 15rem;
    --bex-shell-max: 1280px;
    --bex-shell-padding: 24px;
    --bex-shell-offset: -24px;
    --bex-shell-padding-mobile: 16px;
    --bex-shell-offset-mobile: -16px;
    --bex-control-min-width: 140px;
    --bex-control-max-width: 320px;
    --bex-control-height: 36px;
    --bex-touch-height: 44px;
    --bex-action-gap: 12px;
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
    direction: rtl !important;
    text-align: right !important;
    color: var(--bex-text-primary) !important;
}}

[data-testid="stMainBlockContainer"] {{
    width: 100% !important;
    max-width: var(--bex-shell-max) !important;
    margin-inline: auto !important;
    padding-top: 2rem !important;
    padding-inline: var(--bex-shell-padding) !important;
    box-sizing: border-box !important;
}}

div.st-key-app_header_shell {{
    width: calc(100% + var(--bex-shell-padding) + var(--bex-shell-padding)) !important;
    max-width: var(--bex-shell-max) !important;
    margin-inline: var(--bex-shell-offset) !important;
    padding-inline: var(--bex-shell-padding) !important;
    box-sizing: border-box !important;
}}

@media (max-width: 767px) {{
    [data-testid="stMainBlockContainer"] {{
        padding-inline: var(--bex-shell-padding-mobile) !important;
    }}

    div.st-key-app_header_shell {{
        width: calc(100% + var(--bex-shell-padding-mobile) + var(--bex-shell-padding-mobile)) !important;
        margin-inline: var(--bex-shell-offset-mobile) !important;
        padding-inline: var(--bex-shell-padding-mobile) !important;
    }}
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

.jalali-selected-caption {{
    margin: 0;
    color: var(--bex-text-secondary);
    font-size: 0.95rem;
    line-height: 1.45;
    text-align: right !important;
    direction: rtl !important;
    unicode-bidi: plaintext !important;
    overflow-wrap: anywhere;
}}

/* FIX: Keep the selected date and today's shortcut as one compact, right-aligned row. */
[data-testid="stHorizontalBlock"]:has(.jalali-selected-caption) {{
    align-items: center !important;
    justify-content: flex-start !important;
    flex-wrap: nowrap !important;
    gap: 0.5rem !important;
    margin: 0 0 0.2rem !important;
}}
[data-testid="stHorizontalBlock"]:has(.jalali-selected-caption) > [data-testid="stColumn"]:first-child {{
    flex: 0 1 auto !important;
    width: auto !important;
    min-width: 0 !important;
}}
[data-testid="stHorizontalBlock"]:has(.jalali-selected-caption) > [data-testid="stColumn"]:last-child {{
    flex: 0 0 auto !important;
    width: auto !important;
    min-width: 0 !important;
}}
div[class*="st-key-"][class*="_today_shortcut"] {{
    display: flex !important;
    justify-content: flex-start !important;
}}
div[class*="st-key-"][class*="_today_shortcut"] > div {{
    width: auto !important;
}}
div[class*="st-key-"][class*="_today_shortcut"] button {{
    width: auto !important;
    min-width: 96px !important;
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
}}

div.st-key-app_header_row {{
    width: 100%;
    max-width: 100%;
    border-bottom: 1px solid var(--bex-border);
    box-sizing: border-box;
}}

div.st-key-app_header_row [data-testid="stHorizontalBlock"] {{
    display: grid !important;
    grid-template-columns: minmax(0, 4.2fr) minmax(0, 4.8fr) max-content;
    align-items: center !important;
    gap: 0.75rem !important;
    min-height: 64px;
    padding-inline: 0;
}}

div.st-key-app_header_row [data-testid="stColumn"] {{
    width: auto !important;
    min-width: 0 !important;
    flex: none !important;
}}

.app-header-brand {{
    display: flex;
    align-items: center;
    gap: 0;
    min-width: 0;
}}

.app-header-brand-mark {{
    display: inline-flex;
    align-items: center;
    flex: 0 0 auto;
    margin-inline-end: 12px;
}}

.app-header-brand-mark img {{
    display: block;
    width: auto !important;
    height: auto !important;
    max-width: 100% !important;
    max-height: 40px !important;
}}

.app-header-separator {{
    width: 1px;
    height: 20px;
    flex: 0 0 1px;
    margin-inline-end: 12px;
    background: var(--bex-border);
}}

.app-header-title {{
    min-width: 0;
    color: var(--bex-text-primary);
    font-size: 1.15rem;
    font-weight: 600;
    line-height: 1.4;
    white-space: nowrap;
}}

.app-header-center {{
    min-height: 1px;
}}

.app-user-menu-identity {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    min-width: 0;
    padding: 0.15rem 0.1rem 0.25rem;
}}

.app-user-menu-name {{
    min-width: 0;
    overflow: hidden;
    color: var(--bex-text-primary);
    font-size: 0.9rem;
    font-weight: 700;
    line-height: 1.4;
    text-overflow: ellipsis;
    white-space: nowrap;
}}

.app-user-menu-divider {{
    height: 1px;
    margin: 0.4rem 0 0.3rem;
    background: var(--bex-border);
}}

div.st-key-user_menu_trigger {{
    display: flex !important;
    justify-content: flex-end !important;
    width: max-content !important;
    max-width: 100% !important;
}}

div.st-key-user_menu_trigger button {{
    width: auto !important;
    min-width: 0 !important;
    min-height: 32px !important;
    height: 32px !important;
    padding: 0.2rem 0.6rem !important;
    margin: 0 !important;
    box-sizing: border-box !important;
    border: 1px solid var(--bex-input) !important;
    border-radius: var(--bex-radius-md) !important;
    background: var(--bex-card) !important;
    color: var(--bex-foreground) !important;
    box-shadow: var(--bex-shadow-xs) !important;
    cursor: pointer !important;
    white-space: nowrap !important;
}}

div.st-key-user_menu_trigger button:hover {{
    background: var(--bex-muted) !important;
    border-color: var(--bex-input) !important;
}}

div.st-key-user_menu_trigger button [data-testid="stMarkdownContainer"] p {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
    direction: rtl;
    unicode-bidi: isolate;
    color: var(--bex-foreground) !important;
    font-size: 0.86rem;
    line-height: 1;
}}

div.st-key-user_menu_trigger button code {{
    display: inline-flex;
    align-items: center;
    flex: 0 0 auto;
    padding: 0.12rem 0.45rem;
    border: 1px solid var(--bex-border);
    border-radius: var(--bex-radius-md);
    background: var(--bex-muted);
    color: var(--bex-muted-foreground);
    font-family: inherit !important;
    font-size: 0.72rem;
    font-weight: 700;
    line-height: 1;
    white-space: nowrap;
}}

div.st-key-user_menu_trigger span.material-icons,
div.st-key-user_menu_trigger span.material-symbols-rounded,
div.st-key-user_menu_trigger [data-testid="stIconMaterial"] {{
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 1rem !important;
    height: 1rem !important;
    font-size: 0 !important;
    line-height: 0 !important;
}}

div.st-key-user_menu_trigger span.material-icons::before,
div.st-key-user_menu_trigger span.material-symbols-rounded::before,
div.st-key-user_menu_trigger [data-testid="stIconMaterial"]::before {{
    content: "▾";
    color: var(--bex-text-secondary);
    font-size: 0.8rem;
    line-height: 1;
}}

div.st-key-user_menu_trigger button[aria-expanded="true"] span.material-icons::before,
div.st-key-user_menu_trigger button[aria-expanded="true"] span.material-symbols-rounded::before,
div.st-key-user_menu_trigger button[aria-expanded="true"] [data-testid="stIconMaterial"]::before {{
    content: "▴";
}}

[data-baseweb="popover"]:has(.app-user-menu-identity) {{
    min-width: 14rem;
    direction: rtl !important;
    text-align: right !important;
}}

div.st-key-user_menu_logout button {{
    width: 100% !important;
    min-height: 44px !important;
    padding: 0.45rem 0.65rem !important;
    border: 0 !important;
    border-radius: var(--bex-radius-md) !important;
    background: transparent !important;
    color: var(--bex-destructive) !important;
    box-shadow: none !important;
    justify-content: flex-start !important;
}}

div.st-key-user_menu_logout button:hover {{
    background: var(--bex-muted) !important;
}}

div.st-key-user_menu_logout button > div {{
    width: 100%;
    justify-content: flex-start !important;
}}

div.st-key-user_menu_logout button [data-testid="stMarkdownContainer"] {{
    width: 100%;
}}

div.st-key-user_menu_logout button [data-testid="stMarkdownContainer"] p {{
    color: var(--bex-destructive) !important;
    text-align: right !important;
}}

@media (max-width: 767px) {{
    div.st-key-app_header_row [data-testid="stHorizontalBlock"] {{
        grid-template-columns: minmax(0, 1fr);
        min-height: auto;
        padding-block: 0.65rem;
        row-gap: 0.55rem !important;
    }}

    div.st-key-app_header_row [data-testid="stColumn"]:nth-child(1) {{
        grid-column: 1 / -1;
    }}

    div.st-key-app_header_row [data-testid="stColumn"]:nth-child(2) {{
        display: none !important;
    }}

    div.st-key-app_header_row [data-testid="stColumn"]:nth-child(3) {{
        grid-column: 1 / -1;
        display: flex !important;
        justify-content: flex-end !important;
    }}

    .app-header-brand {{
        width: 100%;
    }}

    .app-header-title {{
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    div.st-key-user_menu_trigger button {{
        min-height: 44px !important;
        height: 44px !important;
    }}

    div.st-key-user_menu_trigger {{
        width: auto !important;
    }}
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
    background: var(--bex-card);
    border: 1px solid var(--bex-border);
    border-radius: var(--bex-radius-xl);
    padding: 0.38rem 0.6rem;
    box-shadow: var(--bex-shadow-xs);
}}

.main-logo img,
.login-logo img {{
    max-width: 320px;
    display: block;
    height: auto;
}}

.login-logo-shell {{
    background: transparent;
    border: 0;
    border-radius: 0;
    padding: 0;
    box-shadow: none;
}}

.login-logo img {{
    max-width: var(--bex-login-logo-max) !important;
}}

.login-title-block {{
    text-align: center;
    margin-bottom: 0.9rem;
}}

[data-testid="stMainBlockContainer"]:has(.login-title-block) {{
    width: 100% !important;
    max-width: var(--bex-login-shell-max) !important;
    margin-inline: auto !important;
    box-sizing: border-box !important;
}}

[data-testid="stMainBlockContainer"]:has(.login-title-block) [data-testid="stForm"] {{
    padding: var(--bex-login-card-padding) !important;
    box-sizing: border-box !important;
}}

[data-testid="stMainBlockContainer"]:has(.login-title-block) div.stFormSubmitButton {{
    display: flex !important;
    justify-content: stretch !important;
    width: 100% !important;
}}

[data-testid="stMainBlockContainer"]:has(.login-title-block)
    div.stFormSubmitButton > [data-testid^="stBaseButton"] {{
    width: 100% !important;
    min-width: 100% !important;
    max-width: none !important;
    flex-basis: 100% !important;
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
    color: var(--bex-text-secondary);
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
    color: var(--bex-muted-foreground);
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
    height: 8px;
    border-radius: 999px;
    background: var(--bex-muted);
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
    background: var(--bex-primary);
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
    height: 8px;
    border-radius: 999px;
    background: var(--bex-muted);
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

/* Replace the legacy inlined active color while preserving the green completion state. */
.visitor-progress-fill[style*="#3D5FCC"] {{
    background: var(--bex-primary) !important;
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
    transform-origin: center;
}}

@media (prefers-reduced-motion: no-preference) {{
    .hourglass-spin {{
        animation: hourglass-wobble 1.1s ease-in-out infinite;
    }}

    @keyframes hourglass-wobble {{
        0% {{ transform: rotate(0deg) scale(1); }}
        25% {{ transform: rotate(-18deg) scale(1.05); }}
        50% {{ transform: rotate(0deg) scale(1); }}
        75% {{ transform: rotate(18deg) scale(1.05); }}
        100% {{ transform: rotate(0deg) scale(1); }}
    }}
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
    background: var(--bex-card);
    border: 1px solid var(--bex-border);
    border-radius: var(--bex-radius-lg);
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
    box-shadow: var(--bex-shadow-xs);
}}

.neu-card-flat {{
    background: var(--bex-card);
    border: 1px solid var(--bex-border);
    border-radius: var(--bex-radius-lg);
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: var(--bex-shadow-xs);
}}

.neu-metric {{
    background: var(--bex-card);
    border: 1px solid var(--bex-border);
    border-radius: var(--bex-radius-lg);
    padding: 1.2rem 1rem;
    text-align: center;
    box-shadow: var(--bex-shadow-xs);
    min-height: 100px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}}

.neu-metric .metric-value {{
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--bex-foreground);
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
}}

.neu-metric .metric-label {{
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--bex-muted-foreground);
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
    min-height: var(--bex-control-height) !important;
    height: var(--bex-control-height) !important;
    border: 1px solid var(--bex-input) !important;
    border-radius: var(--bex-radius-md) !important;
    background: var(--bex-card) !important;
    color: var(--bex-foreground) !important;
    box-shadow: var(--bex-shadow-xs) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
}}

div.stButton > button {{
    padding: 0.55rem 1.2rem !important;
}}

div.stButton > button:hover,
div.stDownloadButton > button:hover {{
    background: var(--bex-muted) !important;
    color: var(--bex-foreground) !important;
}}

div.stButton > button :is(p, [data-testid="stMarkdownContainer"] p),
div.stDownloadButton > button :is(p, [data-testid="stMarkdownContainer"] p) {{
    color: var(--bex-foreground) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
}}

div.stFormSubmitButton > button {{
    background: var(--bex-primary) !important;
    border-color: transparent !important;
    color: var(--bex-primary-foreground) !important;
    padding: 0.55rem 2rem !important;
}}

div.stFormSubmitButton > button :is(p, [data-testid="stMarkdownContainer"] p) {{
    color: var(--bex-primary-foreground) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
}}

div.stButton > button[data-testid*="primary"],
div.stButton > button[data-testid*="primary"]:focus-visible,
div.stButton > button[data-testid*="primary"]:disabled,
div.stFormSubmitButton > button[data-testid*="primary"],
div.stFormSubmitButton > button[data-testid*="primary"]:focus-visible,
div.stFormSubmitButton > button[data-testid*="primary"]:disabled {{
    background: var(--bex-primary) !important;
    border-color: transparent !important;
    color: var(--bex-primary-foreground) !important;
}}

div.stButton > button[data-testid*="primary"]:hover,
div.stFormSubmitButton > button[data-testid*="primary"]:hover {{
    background: color-mix(in srgb, var(--bex-primary) 90%, var(--bex-foreground)) !important;
    border-color: transparent !important;
    color: var(--bex-primary-foreground) !important;
}}

div.stButton > button[data-testid*="primary"] :is(p, [data-testid="stMarkdownContainer"] p),
div.stButton > button[data-testid*="primary"]:hover :is(p, [data-testid="stMarkdownContainer"] p),
div.stButton > button[data-testid*="primary"]:focus-visible :is(p, [data-testid="stMarkdownContainer"] p),
div.stButton > button[data-testid*="primary"]:disabled :is(p, [data-testid="stMarkdownContainer"] p),
div.stFormSubmitButton > button[data-testid*="primary"] :is(p, [data-testid="stMarkdownContainer"] p),
div.stFormSubmitButton > button[data-testid*="primary"]:hover :is(p, [data-testid="stMarkdownContainer"] p),
div.stFormSubmitButton > button[data-testid*="primary"]:focus-visible :is(p, [data-testid="stMarkdownContainer"] p),
div.stFormSubmitButton > button[data-testid*="primary"]:disabled :is(p, [data-testid="stMarkdownContainer"] p) {{
    color: var(--bex-primary-foreground) !important;
}}

div.stButton > button:disabled,
div.stFormSubmitButton > button:disabled,
div.stDownloadButton > button:disabled {{
    opacity: 0.5 !important;
    pointer-events: none !important;
}}

div[class*="st-key-flush_"] button {{
    background: var(--bex-destructive) !important;
    border: 1px solid transparent !important;
    color: var(--bex-destructive-foreground) !important;
}}

div[class*="st-key-flush_"] button:hover {{
    background: color-mix(in srgb, var(--bex-destructive) 90%, var(--bex-foreground)) !important;
    color: var(--bex-destructive-foreground) !important;
}}

div[class*="st-key-flush_"] button :is(p, [data-testid="stMarkdownContainer"] p) {{
    color: var(--bex-destructive-foreground) !important;
}}

div.stDownloadButton > button {{
    background: var(--bex-card) !important;
    border: 1px solid var(--bex-input) !important;
    color: var(--bex-foreground) !important;
}}

div.stButton.st-key-user_menu_logout > button {{
    width: 100% !important;
    max-width: none !important;
    border-color: transparent !important;
    background: transparent !important;
    color: var(--bex-destructive) !important;
    box-shadow: none !important;
    justify-content: flex-start !important;
}}

div.stButton.st-key-user_menu_logout > button:hover {{
    background: var(--bex-muted) !important;
    color: var(--bex-destructive) !important;
}}

div.stButton.st-key-user_menu_logout > button :is(p, [data-testid="stMarkdownContainer"] p) {{
    color: var(--bex-destructive) !important;
}}

[data-testid="stHorizontalBlock"]:has([data-testid="stDownloadButton"])
> [data-testid="stColumn"]:not(:has([data-testid="stDownloadButton"])) {{
    display: none !important;
}}

@media (min-width: 768px) {{
    div.stButton,
    div.stFormSubmitButton,
    [data-testid="stDownloadButton"] {{
        display: flex !important;
        justify-content: flex-start !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
    }}

    [data-testid^="stBaseButton"],
    [data-testid="stDownloadButton"] button {{
        width: auto !important;
        min-width: var(--bex-control-min-width) !important;
        max-width: var(--bex-control-max-width) !important;
        flex: 0 1 auto !important;
        white-space: nowrap !important;
    }}

    div[class*="st-key-"][class*="_today_shortcut"] button {{
        min-width: var(--bex-control-min-width) !important;
    }}

    [data-testid="stHorizontalBlock"]:has(div[class*="st-key-publish_"]) {{
        align-items: flex-start !important;
        gap: var(--bex-action-gap) !important;
    }}

    [data-testid="stHorizontalBlock"]:has(div[class*="st-key-publish_"])
    > [data-testid="stColumn"]:has(div[class*="st-key-publish_"]) {{
        flex: 0 0 var(--bex-control-min-width) !important;
        width: var(--bex-control-min-width) !important;
        min-width: var(--bex-control-min-width) !important;
    }}

    [data-testid="stHorizontalBlock"]:has(div[class*="st-key-publish_"])
    > [data-testid="stColumn"]:has(div[class*="st-key-finalize_"]) {{
        flex: 1 1 auto !important;
        width: auto !important;
        min-width: 0 !important;
    }}

    [data-testid="stHorizontalBlock"]:has([data-testid="stDownloadButton"]),
    [data-testid="stHorizontalBlock"]:has(div.st-key-telesales_prev_page) {{
        justify-content: flex-start !important;
        align-items: flex-start !important;
        gap: var(--bex-action-gap) !important;
    }}

    [data-testid="stHorizontalBlock"]:has([data-testid="stDownloadButton"])
    > [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"]:has(div.st-key-telesales_prev_page)
    > [data-testid="stColumn"] {{
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: 0 !important;
    }}

    div[class*="st-key-build_pipeline_"] div.stButton,
    div[class*="st-key-build_pipeline_"] [data-testid^="stBaseButton"] {{
        width: 100% !important;
        min-width: 100% !important;
        max-width: none !important;
        flex-basis: 100% !important;
    }}
}}

@media (max-width: 767px) {{
    div.stButton,
    div.stFormSubmitButton,
    [data-testid="stDownloadButton"],
    div.st-key-user_menu_trigger {{
        display: flex !important;
        justify-content: stretch !important;
        width: 100% !important;
        max-width: none !important;
    }}

    div.stButton > [data-testid^="stBaseButton"],
    div.stFormSubmitButton > [data-testid^="stBaseButton"],
    div.stDownloadButton > button,
    [data-testid="stDownloadButton"] > button {{
        width: 100% !important;
        min-width: 0 !important;
        max-width: none !important;
        min-height: var(--bex-touch-height) !important;
        height: var(--bex-touch-height) !important;
        flex: 1 1 100% !important;
    }}

    [data-testid="stHorizontalBlock"]:has(div[class*="st-key-publish_"]),
    [data-testid="stHorizontalBlock"]:has([data-testid="stDownloadButton"]),
    [data-testid="stHorizontalBlock"]:has(div.st-key-telesales_prev_page) {{
        flex-direction: column !important;
        align-items: stretch !important;
        gap: var(--bex-action-gap) !important;
    }}

    [data-testid="stHorizontalBlock"]:has(div[class*="st-key-publish_"])
    > [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"]:has([data-testid="stDownloadButton"])
    > [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"]:has(div.st-key-telesales_prev_page)
    > [data-testid="stColumn"] {{
        flex: 1 1 100% !important;
        width: 100% !important;
        min-width: 0 !important;
    }}

    [data-testid="stHorizontalBlock"]:has(div[class*="st-key-publish_"])
    [data-testid="stElementContainer"],
    [data-testid="stHorizontalBlock"]:has([data-testid="stDownloadButton"])
    [data-testid="stElementContainer"],
    [data-testid="stHorizontalBlock"]:has(div.st-key-telesales_prev_page)
    [data-testid="stElementContainer"],
    [data-testid="stHorizontalBlock"]:has(div[class*="st-key-publish_"])
    [data-testid="stButton"],
    [data-testid="stHorizontalBlock"]:has([data-testid="stDownloadButton"])
    [data-testid="stDownloadButton"],
    [data-testid="stHorizontalBlock"]:has(div.st-key-telesales_prev_page)
    [data-testid="stButton"] {{
        flex: 1 1 100% !important;
        width: 100% !important;
        max-width: none !important;
    }}
}}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div,
input[type="text"],
input[type="password"],
input[type="date"] {{
    min-height: 36px !important;
    border-radius: var(--bex-radius-md) !important;
    border: 1px solid var(--bex-input) !important;
    box-shadow: none !important;
    background: var(--bex-card) !important;
    color: var(--bex-foreground) !important;
    font-size: 0.875rem !important;
}}

button:focus-visible,
a:focus-visible,
[role="button"]:focus-visible,
[role="tab"]:focus-visible,
div.stButton > button:focus-visible,
div.stFormSubmitButton > button:focus-visible,
div.stDownloadButton > button:focus-visible,
div.st-key-user_menu_trigger button:focus-visible,
div.st-key-user_menu_logout button:focus-visible,
input:focus-visible,
textarea:focus-visible,
[data-baseweb="select"] > div:focus-within,
details[data-testid="stExpander"] summary:focus-visible,
[data-testid="stCheckbox"] input:focus-visible + div,
[data-testid="stToggle"] [role="switch"]:focus-visible {{
    outline: none !important;
    box-shadow: var(--bex-ring-shadow) !important;
    border-color: var(--bex-ring) !important;
}}

div[class*="st-key-flush_"] button:focus-visible,
div.st-key-user_menu_logout button:focus-visible {{
    box-shadow: 0 0 0 3px var(--bex-destructive-ring) !important;
    border-color: var(--bex-destructive) !important;
}}

[data-testid="stForm"] {{
    background: var(--bex-card) !important;
    border: 1px solid var(--bex-border) !important;
    border-radius: var(--bex-radius-lg) !important;
    box-shadow: var(--bex-shadow-xs) !important;
}}

[data-testid="stAlertContainer"] {{
    background: var(--bex-card) !important;
    color: var(--bex-foreground) !important;
    border: 1px solid var(--bex-border) !important;
    border-inline-start: 4px solid var(--bex-primary) !important;
    border-radius: var(--bex-radius-lg) !important;
    box-shadow: var(--bex-shadow-xs) !important;
    font-size: 0.875rem !important;
}}

[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{
    border-inline-start-color: var(--bex-status-green-fg) !important;
}}

[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
    border-inline-start-color: var(--bex-status-yellow-fg) !important;
}}

[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
    border-inline-start-color: var(--bex-destructive) !important;
}}

[data-testid="stAlertContainer"] [data-testid^="stAlertContent"] {{
    color: var(--bex-foreground) !important;
    font-size: 0.875rem !important;
}}

[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
label p {{
    color: var(--bex-foreground) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
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
    direction: rtl !important;
    text-align: right !important;
    margin-top: 0.2rem !important;
}}
[data-testid="stCheckbox"] > label {{
    direction: rtl !important;
    display: inline-flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: flex-start !important;
    column-gap: 0.45rem !important;
    row-gap: 0 !important;
    min-height: 36px !important;
    line-height: 1.8 !important;
    padding-right: 0.25rem !important;
    cursor: pointer !important;
}}
[data-testid="stCheckbox"] input[type="checkbox"] {{
    width: 16px !important;
    height: 16px !important;
    margin: 0 !important;
}}
[data-testid="stCheckbox"] label > span:first-child,
[data-testid="stCheckbox"] label > span:first-child > div {{
    width: 16px !important;
    min-width: 16px !important;
    height: 16px !important;
    border: 1px solid var(--bex-input) !important;
    border-radius: 4px !important;
    background: var(--bex-card) !important;
    box-shadow: none !important;
}}
[data-testid="stCheckbox"] label:has(input:checked) > span:first-child,
[data-testid="stCheckbox"] label:has(input:checked) > span:first-child > div {{
    border-color: var(--bex-primary) !important;
    background: var(--bex-primary) !important;
}}
[data-testid="stCheckbox"] > label > div:last-child {{
    margin-right: 0.18rem !important;
}}
[data-testid="stCheckbox"] span {{
    margin: 0 !important;
}}

[data-testid="stToggle"] [role="switch"] {{
    min-width: 36px !important;
    width: 36px !important;
    height: 20px !important;
    border: 1px solid var(--bex-input) !important;
    background: var(--bex-muted) !important;
    box-shadow: none !important;
}}
[data-testid="stToggle"] [role="switch"][aria-checked="true"] {{
    border-color: var(--bex-primary) !important;
    background: var(--bex-primary) !important;
}}

/* FIX: Selectbox search must auto-switch direction (Persian RTL / English LTR). */
[data-baseweb="select"] input {{
    direction: auto !important;
    unicode-bidi: plaintext !important;
    text-align: start !important;
}}
[data-baseweb="select"] input::placeholder {{
    direction: rtl !important;
    text-align: right !important;
}}

[data-testid="stFileUploaderDropzone"] {{
    direction: rtl !important;
    text-align: right !important;
    width: 100% !important;
    min-height: 44px !important; /* FIX: [A11Y-05] Minimum touch target for upload zone. */
    border: 1px dashed var(--bex-input) !important;
    border-radius: var(--bex-radius-lg) !important;
    background: var(--bex-card) !important;
    box-shadow: none !important;
}}

[data-testid="stFileUploaderDropzone"] button {{
    min-height: 44px !important;
}}

details[data-testid="stExpander"] {{
    background: var(--bex-card) !important;
    border: 1px solid var(--bex-border) !important;
    border-radius: var(--bex-radius-lg) !important;
    box-shadow: var(--bex-shadow-xs) !important;
    margin-bottom: 0.8rem;
}}

details[data-testid="stExpander"] summary {{
    direction: rtl !important;
    text-align: right !important;
    color: var(--bex-foreground) !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
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
    border: 1px solid var(--bex-border) !important;
    border-radius: var(--bex-radius-lg) !important;
    overflow: hidden;
    background: var(--bex-card) !important;
    box-shadow: var(--bex-shadow-xs) !important;
}}

/* FIX: Center all dataframe cells/headers and keep Persian-friendly visual alignment. */
[data-testid="stDataFrame"] [role="grid"] {{
    direction: rtl !important;
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
    padding: 0.125rem 0.5rem;
    border: 1px solid currentColor;
    border-radius: var(--bex-radius-md);
    font-size: 0.75rem;
    font-weight: 500;
    line-height: 1rem;
}}

.badge-green  {{ background: var(--bex-status-green-bg); color: var(--bex-status-green-fg); }}
.badge-yellow {{ background: var(--bex-status-yellow-bg); color: var(--bex-status-yellow-fg); }}
.badge-red    {{ background: var(--bex-status-red-bg); color: var(--bex-status-red-fg); }}
.badge-gray   {{ background: var(--bex-status-gray-bg); color: var(--bex-status-gray-fg); }}
.badge-draft     {{ background: var(--bex-status-gray-bg); color: var(--bex-status-gray-fg); }}
.badge-supervisor-approved {{ background: var(--bex-status-approved-bg); color: var(--bex-status-approved-fg); }}
.badge-published {{ background: var(--bex-status-published-bg); color: var(--bex-status-published-fg); }}
.badge-completed {{ background: var(--bex-status-green-bg); color: var(--bex-status-green-fg); }}
.badge-skipped   {{ background: var(--bex-status-red-bg); color: var(--bex-status-red-fg); }}

.section-header {{
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--bex-text-primary);
    margin-bottom: 0.6rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid var(--bex-border);
    text-align: right !important;
    direction: rtl !important;
}}

.role-badge {{
    display: inline-block;
    padding: 0.125rem 0.5rem;
    border: 1px solid currentColor;
    border-radius: var(--bex-radius-md);
    font-size: 0.75rem;
    font-weight: 500;
    line-height: 1rem;
}}

.role-manager    {{ background: var(--bex-role-manager-bg); color: var(--bex-role-manager-fg); }}
.role-supervisor {{ background: var(--bex-role-supervisor-bg); color: var(--bex-role-supervisor-fg); }}
.role-visitor    {{ background: var(--bex-role-visitor-bg); color: var(--bex-role-visitor-fg); }}
.role-telesales  {{ background: var(--bex-role-telesales-bg); color: var(--bex-role-telesales-fg); }}

.monitoring-bar {{
    background: var(--bex-card);
    color: var(--bex-role-manager-fg);
    border: 1px solid var(--bex-border);
    border-inline-start: 4px solid var(--bex-role-manager-fg);
    border-radius: var(--bex-radius-lg);
    padding: 0.6rem 1rem;
    font-weight: 600;
    font-size: 0.85rem;
    text-align: center;
    margin-bottom: 1rem;
    box-shadow: var(--bex-shadow-xs);
}}

button[data-baseweb="tab"] {{
    border-radius: var(--bex-radius-md) var(--bex-radius-md) 0 0 !important;
    font-weight: 500 !important;
}}

#MainMenu {{ visibility: hidden; }}
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {{
    display: none !important;
}}
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


def render_dashboard_header(current_user: dict, title: str):
    logo_tag = _logo_img_tag(max_width=160)
    safe_title = html.escape(str(title or ""))
    safe_username = html.escape(str(current_user.get("username") or ""))
    normalized_role = str(current_user.get("role") or "").strip().lower()
    safe_role_label = html.escape(str(_ROLE_DISPLAY.get(normalized_role, normalized_role)))
    role_badge = role_badge_html(normalized_role)
    brand_html = f'<span class="app-header-brand-mark">{logo_tag}</span>' if logo_tag else ""

    brand_col, center_col, user_menu_col = st.columns(
        [4.2, 4.8, 1.8],
        gap="small",
    )
    with brand_col:
        st.markdown(
            f'<div class="app-header-brand">{brand_html}'
            f'<span class="app-header-separator" aria-hidden="true"></span>'
            f'<span class="app-header-title">{safe_title}</span></div>',
            unsafe_allow_html=True,
        )
    with center_col:
        st.markdown('<div class="app-header-center" aria-hidden="true"></div>', unsafe_allow_html=True)
    with user_menu_col:
        user_menu = st.popover(
            f"\u2066{safe_username}\u2069  `{safe_role_label}`",
            key="user_menu_trigger",
            type="secondary",
            width="content",
            wrap=False,
        )
    with user_menu:
        st.markdown(
            f'<div class="app-user-menu-identity"><span class="app-user-menu-name ltr-inline" '
            f'dir="ltr">{safe_username}</span>'
            f'{role_badge}</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="app-user-menu-divider" aria-hidden="true"></div>', unsafe_allow_html=True)
        return st.button(
            "خروج",
            key="user_menu_logout",
            type="tertiary",
            use_container_width=True,
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
