# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from enum import Enum

# All roles
# Contract: UserRole defines a typed boundary and should remain behavior-stable.
class UserRole(str, Enum):
    MANAGER = 'manager'
    SUPERVISOR = 'supervisor'
    VISITOR = 'visitor'
    TELESALES = 'telesales'
