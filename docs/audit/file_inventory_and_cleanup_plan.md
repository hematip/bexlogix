# File/Folder Inventory and Conservative Cleanup Plan

## 1) Inventory Classification

### Core (keep)
- `client/` (UI, router, components, style system).
- `server/app/` (domain logic, repositories, models, auth, enums).
- `server/db/` (DB setup, seed, sample generation).
- `server/tests/` (regression and integrity coverage).
- `data/` sample files required for MVP scenario.
- `BexLogix.md`, `BexLogix_Comprehensive_Technical_Product_Specification.md`.

### Runtime / local artifacts (do not commit)
- `venv/`
- `__pycache__/` (all levels)
- `.pytest_cache/`
- `.mypy_cache/`, `.ruff_cache/`, `.cache/`
- `*.log`, local SQLite temp variants
- `.streamlit/secrets.toml`

### IDE / machine-local (do not commit)
- `.idea/`
- `.vscode/`

### Optional legacy / deprecate-candidate (do not remove aggressively)
- `server/app/services/import_visitors_service.py`
- `server/db/seed_visitors.py`
- `data/visitors_sample_10.xlsx`
- `data/upload_template_visitors.xlsx`
- `data/upload_template_users.xlsx`
- `data/upload_template_stores.xlsx`

## 2) Conservative Cleanup Actions Applied
1. `.gitignore` hardened for recursive runtime artifacts and local caches.
2. `.streamlit/secrets.toml` explicitly ignored.
3. `docs/audit/tmp/` ignored for local audit scratch files.
4. No destructive deletion on business-critical code paths.

## 3) Cleanup Strategy (Conservative)
- Keep all operational and test-critical files intact.
- Mark optional legacy files as `deprecate-candidate` in documentation first.
- Only delete legacy candidates after:
  1) no runtime references,
  2) no test references,
  3) explicit product-owner sign-off.

## 4) Risk Notes
- Immediate aggressive deletion can break backward smoke scripts and ad-hoc migration/backfill workflows.
- Conservative mode minimizes regression risk and preserves troubleshooting ability.
