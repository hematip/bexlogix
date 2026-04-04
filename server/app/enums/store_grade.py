# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from enum import Enum

# Allowed service levels for stores.
# Contract: StoreEnum defines a typed boundary and should remain behavior-stable.
class StoreEnum(str, Enum):
    VIP ='VIP'
    A_PLUS = 'A+'
    A = 'A'
    B = 'B'
    C = 'C'
