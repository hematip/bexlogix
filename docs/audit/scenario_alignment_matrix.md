# Scenario Alignment Matrix (`BexLogix.md`)

## Status Legend
- `Aligned`: behavior is implemented as expected.
- `Partially aligned`: implemented but with technical/operational caveat.
- `Gap`: not fully delivered or still unstable.

| Scenario Requirement (`BexLogix.md`) | Code Evidence | Status | Notes |
|---|---|---|---|
| 300 stores / 10 visitors / capacity 30 sample scale | `data/stores_sample_300.xlsx`, `data/daily_visitor_status_sample_10.xlsx`, `DEFAULT_DAILY_CAPACITY=30` | Aligned | Sample dimensions are also tested in `server/tests/test_sample_file_dimensions.py`. |
| Store visit as basket unit | `Store` category flags + `get_store_visit_interval_days()` | Aligned | Single store visit unit with multi-category support. |
| Frequency matrix by grade and category | `CONFECTIONERY_OIL_INTERVALS`, `PASTA_INTERVALS` in `scheduling_service.py` | Aligned | Exact matrix values implemented. |
| Multi-category uses shortest interval | `return min(candidate_intervals)` | Aligned | Matches scenario rule directly. |
| Due stores determined from schedule state | `get_due_store_ids()` | Aligned | Uses next visit date + queue state + active store filters. |
| Yellow result retries in +3 days | `YELLOW_RETRY_DAYS = 3` + `apply_visit_result_to_schedule()` | Aligned | Exact scenario rule. |
| Red result handed to telesales | `visit_service.submit_visit_result()` + `telesales_service.create_followup_for_red_visit()` | Aligned | Immediate queue handoff is active. |
| Daily assignment across active visitors with capacity | `get_active_visitor_day_contexts()` + `_geo_capacity_allocate_stores()` | Aligned | Capacity-aware and geographic allocation. |
| Route generation per visitor from start point | `routing_service.apply_routes_for_work_date()` | Aligned | OSRM primary + NN fallback. |
| Manager control over generation/publish | `manager_dashboard.py` + `assignment_service` manager checks | Aligned | Manager-only policy enforced via role checks. |
| Supervisor monitoring-only | `supervisor_dashboard.py` no mutation actions | Aligned | View-only behavior in page workflow. |
| Visitor submits own route results only | `visit_service` ownership + status validation | Aligned | Prevents foreign assignment submission. |
| Telesales handles pending red queue | `telesales_panel.py` + `telesales_service` | Aligned | Pending queue and outcomes are operational. |
| Monitoring and export at end of day | `reporting_export_service.py` | Aligned | KPI + detailed multi-sheet summary export exists. |
| Map route visualization | `client/components/route_map.py` | Partially aligned | Route rendering works, but base-tile Persian text shaping depends on provider/browser and can still be visually inconsistent. |
| “No store leaves tracking cycle” | schedule + follow-up + reconciliation services | Partially aligned | Business flow exists; DB-level hard constraints are still partly service-enforced (not fully DB-constrained). |

## Observed Gaps / Cautions (Report-Only)
1. Some historic/legacy import modules still exist (e.g., visitors/backfill import paths), even though the main manager flow is now daily-driven.
2. Map label quality for Persian street names is externally constrained by tile/font rendering; app-level logic cannot guarantee perfect glyph shaping across all providers.
3. Several uniqueness rules rely on service/integrity checks rather than strict DB constraints for every table.
