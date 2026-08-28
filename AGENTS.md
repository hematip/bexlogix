# AGENTS.md — BexLogix UI work

Read this fully before changing any file. It exists because the design system
and the runtime come from two different worlds, and the failure modes are not
obvious.

## What this project is

BexLogix is a Persian, RTL, offline-first field-sales operations app for
Tehran. It runs as a **Streamlit** app inside Docker on a local machine. Roles:
manager, supervisor, visitor (field), telesales, admin.

Offline-first is a hard constraint. No CDN fonts, no CDN CSS, no external
script tags, no Google Fonts. Everything ships in the image.

## What the design system is

The Bextudio Figma file is built on the **shadcn/ui kit** (shadcndesign.com).
That means the design system is natively React + Tailwind + Radix.

**Streamlit is not React-with-your-classes.** It renders its own DOM, its
class names are hashed, and it does not accept Tailwind utilities on its
widgets. So there is no faithful port of shadcn components into Streamlit.

What we are doing instead: **porting the tokens, not the components.** The goal
is a Streamlit app that reads as the same product family — same palette, type
scale, spacing rhythm, radii, focus treatment — not a pixel copy of the Figma
frames. If a task cannot be done with tokens, say so and stop rather than
inventing a lookalike with hardcoded values.

## Source of truth

| File | Role |
|---|---|
| `app/design/tokens.json` | Extracted from Figma. **The only source of truth.** |
| `app/assets/bextudio.css` | Generated from tokens. Edit tokens first. |
| `app/assets/fonts/` | Vazirmatn + Geist, bundled locally. |
| `app/ui/theme.py` | The single place CSS is injected. |

## Hard rules

1. **No hardcoded values.** Below the `:root` block in `bextudio.css`, no hex
   colours, no px font sizes, no px radii, no px spacing. Use `var(--bx-*)`.
   If a token is missing, add it to `tokens.json` and regenerate — do not
   inline a value.
2. **Never target `.st-emotion-cache-*`.** Those hashes change on every
   Streamlit release. Target `[data-testid="..."]` only.
3. **Streamlit is pinned in `requirements.txt`.** Do not bump it as part of a
   UI task. `data-testid` attributes have changed between releases; a version
   bump silently breaks this stylesheet. If a bump is genuinely needed, it is
   its own PR with a full visual re-check.
4. **One injection point.** CSS is injected once by `theme.py`. Do not scatter
   `st.markdown("<style>")` through the pages.
5. **Presentation only.** Do not touch business logic, repositories, services,
   domain enums, validation rules, or routing/OSRM/VROOM code. If a UI change
   appears to require a logic change, stop and describe it instead.
6. **Never remove information from a destructive or high-consequence screen**
   to make it look cleaner. Publishing routes, finalising unsubmitted visits
   and flushing a date's data all have operational consequences. Restructure,
   sequence or progressively disclose — do not delete.
7. **No secrets in code or commits.** If you find a token, password or
   connection string in the repo, report it and do not reproduce it.

## RTL and bidi

- The document is RTL. Use logical CSS properties (`margin-inline-start`,
  `padding-inline-end`, `border-inline-start`) — never `left`/`right`.
- Latin runs inside Persian sentences must be isolated or they reorder
  visually. Wrap them in `.bx-ltr`: usernames, `visitor_code`, XLSX column
  names (`work_date`, `start_lat`, `start_lon`, `is_active_today`), file
  names, coordinates, IDs.
- Numbers in tables and KPI tiles use `.bx-num` (tabular, LTR-isolated).
- Jalali dates display Persian; the Gregorian equivalent, where shown, is a
  Latin run and must be isolated.
- Test every change with a long Persian store name and a long Tehran address.
  Truncation and overflow behave differently in RTL.

## Typography

`Geist` has **no Persian glyph coverage.** The stack is
`"Vazirmatn", "Geist", ...` so Persian renders in Vazirmatn and embedded Latin
still renders in Geist. Do not "fix" this by removing Vazirmatn, and do not
apply Geist directly to Persian text.

Vazirmatn's metrics differ from Geist's — line heights from the token scale
may need visual checking on Persian paragraphs. Report cases where the token
line-height looks wrong rather than overriding it locally.

## Known accessibility issue — read before styling buttons

The Figma primary, `#0891b2`, gives roughly **3.55:1** against white text.
Button text is 14px / weight 500, so WCAG 2.2 AA requires 4.5:1. It fails.

`bextudio.css` therefore introduces `--bx-primary-strong` (`#0e7490`, ≈5.36:1)
for any surface carrying text, and keeps `--bx-primary` for borders, focus
rings, icons and chart series. Do not "restore brand accuracy" by swapping
`--bx-primary-strong` back to `--bx-primary` on buttons.

This is a design-system question that needs the brand owner's decision. Flag
it; do not resolve it unilaterally in either direction.

Other standing requirements:
- Visible focus on every interactive element. Never `outline: none` without a
  replacement `box-shadow`.
- Colour is never the only carrier of meaning. The green/amber/red visit
  outcomes each need a text label and a distinct icon shape, not just a
  colour.
- Field controls for the visitor role use `.bx-touch` (44px targets).
- Everything must survive 200% browser zoom without horizontal scrolling of
  the page body.

## English strings that leak through the framework

Streamlit ships English in the file uploader ("Browse files", "Drag and drop
file here", "200MB per file"), and in some widget internals. CSS can hide
these but cannot translate them. Do not fake translations with `::after`
content on an element that still contains English text — screen readers will
announce both.

Preferred order: a Persian `label` and `help` on the widget → a Persian
instruction line rendered above it → hiding the English string only if it is
fully redundant. Record anything that cannot be translated in
`docs/i18n-gaps.md` rather than leaving it silently English.

## Docker workflow

Source is bind-mounted (`./app:/app`), so a CSS change does not need a
rebuild. Streamlit reruns on save.

The CSS link carries a cache-busting query built from the file hash. If a
change appears not to apply, check the hash is being recomputed before
assuming the selector is wrong.

## Order of work

Do not start with pages. Work in this order, one PR per step:

1. Tokens + font bundling + `theme.py` injection point
2. Global typography, colour, RTL base
3. Base controls: button, input, select, checkbox, expander, metric, alert,
   dataframe, file uploader
4. Then page by page: manager dashboard → supervisor → visitor → telesales

## Definition of done for any UI PR

- No hardcoded colour/size/radius/spacing outside `:root`
- No `.st-emotion-cache-*` selectors
- Streamlit version unchanged
- Screenshots before/after at 1440px, 768px and 390px widths
- Checked at 200% zoom
- Checked with a long Persian name and a long address
- Keyboard tab pass: focus visible and in a sensible reading order
- No business logic touched
- Any English string that could not be translated is logged in
  `docs/i18n-gaps.md`

## When to stop and ask

- The change would alter what a user sees before a destructive action
- The change would remove a field, warning, count or consequence preview
- The design calls for a component Streamlit cannot express with tokens
- A token is missing and you would have to invent a value
- The task appears to require a Streamlit version bump
