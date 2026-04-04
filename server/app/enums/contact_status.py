# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from enum import Enum

# Allowed telesales contact statuses
# Contract: ContactStatus defines a typed boundary and should remain behavior-stable.
class ContactStatus(Enum):
    REACHED = 'reached'
    NOT_REACHED = 'not_reached'
