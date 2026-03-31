"""
Import all ORM models to guarantee SQLAlchemy metadata registration.
"""

# Import order does not matter here; each import registers its table on Base.metadata.
from server.app.models.daily_assignment import DailyAssignment  # noqa: F401
from server.app.models.daily_visitor_status import DailyVisitorStatus  # noqa: F401
from server.app.models.store import Store  # noqa: F401
from server.app.models.store_schedule_state import StoreScheduleState  # noqa: F401
from server.app.models.telesales_followup import TelesalesFollowup  # noqa: F401
from server.app.models.user import User  # noqa: F401
from server.app.models.visit import Visit  # noqa: F401
from server.app.models.visitor_profile import VisitorProfile  # noqa: F401


def register_models() -> None:
    """
    Explicit hook for bootstrap flows (create tables, migrations, tests).
    """
    return None
