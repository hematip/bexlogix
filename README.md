# BexLogix

BexLogix is an offline-first Streamlit application for field-sales operations.

## What It Does
- Manages role-based workflows for `manager`, `supervisor`, `visitor`, and `telesales` users.
- Builds daily store assignments and route ordering for field visitors.
- Tracks visit outcomes (`green`, `yellow`, `red`) and creates telesales follow-ups for red visits.
- Provides operational dashboards, route map visualization, and daily reporting/export.

## Core Daily Process
1. Startup seed loads baseline `login.xlsx` and `stores.xlsx` when the database is empty.
2. Manager uploads `visitors.xlsx` (daily visitor status) and optionally new `stores.xlsx`.
3. System creates draft assignments, orders routes with local OSRM, and falls back to nearest-neighbor if needed.
4. Manager publishes assignments.
5. Visitors submit visit results and notes.
6. Red visits are pushed to telesales follow-up queue.
7. Telesales finalizes follow-up outcomes.

## Data File Contracts (`data/`)
- `login.xlsx`: users and passwords for initial seed.
- `stores.xlsx`: master store list (300 stores in sample).
- `visitors.xlsx`: daily visitor status file (10 visitors in sample).

## Run (Offline)
1. Create environment and install dependencies:
   - `python -m venv .venv`
   - `./.venv/Scripts/activate`
   - `pip install -r requirements.txt`
2. Prepare OSRM graph once:
   - `./scripts/offline_prepare_osrm_tehran.ps1`
3. Start local offline stack:
   - `./scripts/offline_up.ps1`
4. Run app:
   - `streamlit run client/streamlit_app.py`
5. For full deployment and recovery guide:
   - See `DEPLOY.md`

## Notes
- The app is designed to run with no external internet dependency at runtime.
- If local OSRM is unavailable, route ordering automatically falls back to internal nearest-neighbor.
- If local tiles are unavailable, map markers and route path still render without basemap tiles.
