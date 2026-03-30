from enum import Enum

# All roles
class UserRole(str, Enum):
    MANAGER = 'manager'
    SUPERVISOR = 'supervisor'
    VISITOR = 'visitor'
    TELESALES = 'telesales'