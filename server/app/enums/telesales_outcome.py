# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from enum import Enum

# Allowed telesales follow-up outcomes
# Contract: TelesalesOutcome defines a typed boundary and should remain behavior-stable.
class TelesalesOutcome(Enum):
    SALE_DONE = 'sale_done'
    NO_NEED = 'no_need'
    POSTPONE = 'postpone'
    INVALID = 'invalid'
