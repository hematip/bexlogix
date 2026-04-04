# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

import os


# Contract: _to_float executes one deterministic step in the workflow.
def _to_float(raw_value: str | None, default: float) -> float:
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


# Base URL for OSRM route optimization API.
# Example: https://router.project-osrm.org
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org").strip()

# Timeout (seconds) for OSRM HTTP calls before fallback planner is used.
OSRM_TIMEOUT_SECONDS = _to_float(os.getenv("OSRM_TIMEOUT_SECONDS"), 6.0)
