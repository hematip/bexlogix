from enum import Enum

# Allowed telesales follow-up outcomes
class TelesalesOutcome(Enum):
    SALE_DONE = 'sale_done'
    NO_NEED = 'no_need'
    POSTPONE = 'postpone'
    INVALID = 'invalid'