from enum import Enum

# Allowed service levels for stores.
class StoreEnum(str, Enum):
    VIP ='VIP'
    A_PLUS = 'A+'
    A = 'A'
    B = 'B'
    C = 'C'