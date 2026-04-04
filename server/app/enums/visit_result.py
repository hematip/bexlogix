# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from enum import Enum

# Allowed visit result values
# Contract: VisitResult defines a typed boundary and should remain behavior-stable.
class VisitResult(Enum):
    GREEN = 'green'
    YELLOW = 'yellow'
    RED = 'red'
