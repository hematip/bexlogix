from enum import Enum

# Allowed telesales contact statuses
class ContactStatus(Enum):
    REACHED = 'reached'
    NOT_REACHED = 'not_reached'