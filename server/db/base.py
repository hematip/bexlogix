# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from sqlalchemy.orm import DeclarativeBase

# All the db models must inherit from this Base
# Contract: Base defines a typed boundary and should remain behavior-stable.
class Base(DeclarativeBase):
    pass
