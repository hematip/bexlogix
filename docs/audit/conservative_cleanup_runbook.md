# Conservative Cleanup Runbook (Step-by-Step)

## Goal
Clean local/runtime noise without changing business behavior or removing operational modules prematurely.

## Step 1: Baseline Safety
1. Run `pytest -q`.
2. Run `python scripts/quality_gate.py`.
3. Record current outputs before cleanup.

## Step 2: Ignore Policy Enforcement
1. Ensure `.gitignore` contains runtime, cache, IDE, and local secret patterns.
2. Ensure no `venv/`, `__pycache__/`, `.pytest_cache/` entries are tracked.

## Step 3: Local Artifact Sweep (non-business)
1. Remove local runtime caches from workspace machine if needed.
2. Keep database and sample data files required by current tests and demo flow.

## Step 4: Deprecate-Candidate Review
1. For each candidate file:
   - check import references via `rg`,
   - check test references,
   - classify as `keep` or `safe-to-retire`.
2. Do not delete in the same step unless explicitly approved.

## Step 5: Validation After Cleanup
1. Re-run `pytest -q`.
2. Re-run `python scripts/quality_gate.py`.
3. Run smoke checks for:
   - manager pipeline,
   - visitor submission,
   - telesales submission,
   - summary export.

## Step 6: Sign-Off Checklist
- No business logic changed.
- No route/visit/telesales flow regression.
- Role-based routing still valid.
- DB integrity checks still pass.
