# BexLogix Process Flow Report (Code-Based Audit)

## 1) Runtime Architecture
- Presentation: `client/streamlit_app.py` + role pages in `client/pages/`.
- Domain workflow: `server/app/services/*`.
- Persistence boundary: `server/app/repositories/*`.
- Data model: `server/app/models/*`.
- Database: SQLite via `server/db/database.py`.

## 2) End-to-End Operational Flow
1. Startup boot:
   - `seed_if_empty()` in `server/db/startup_seed.py`.
   - Seeds only `users_seed_sample_10_visitors.xlsx` and `stores_sample_300.xlsx`.
2. Manager daily pipeline:
   - Optional stores import (`import_service.import_stores_from_excel`).
   - Required daily file import (`import_daily_visitor_statuses_from_excel`).
   - Draft assignment generation (`assignment_service.generate_draft_assignments`).
   - Route ordering (`routing_service.apply_routes_for_work_date` with `OSRMRoutePlanner` fallback to NN).
3. Publish:
   - `assignment_service.publish_assignments`.
4. Visitor execution:
   - Visitor submits `green/yellow/red` from `client/pages/visitor_panel.py`.
   - `visit_service.submit_visit_result` updates assignment + schedule.
   - `red` triggers telesales follow-up creation.
5. Telesales follow-up:
   - Queue listing from `telesales_service.list_pending_followups`.
   - Result submit via `telesales_service.submit_followup_result`.
6. Monitoring and export:
   - KPI + tables + map in manager/supervisor pages.
   - Exports from `reporting_export_service`.

## 3) Role Routing and Session
- Role-based view routing: `?view=manager|supervisor|visitor|telesales`.
- Guarded session:
  - Streamlit session state + signed query token in `client/auth_state.py`.
  - DB-backed user validation on each run in `client/streamlit_app.py`.
- On invalid/expired session:
  - forced logout + rewrite to `?view=login`.

## 4) Core Data Lifecycle
- Master data:
  - Users: `users`.
  - Stores: `stores`.
  - Visitor profile: `visitor_profiles` (upserted by daily import contract).
- Daily data:
  - `daily_visitor_statuses` (per visitor, per date).
  - `daily_assignments` (generated/published/completed/skipped).
  - `visits` (one logical visit result per assignment).
  - `telesales_followups` (pending/finalized chain).
- Derived state:
  - `store_schedule_states` holds due/queue state for fast scheduling.

## 5) Verified Baseline (Current Workspace)
- `pytest -q` result: `17 passed, 1 skipped`.
- `python scripts/quality_gate.py` result: passed.
- DB table presence verified: assignments, visits, followups, daily statuses, schedule states.
