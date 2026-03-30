from server.db.base import Base
from server.db.database import engine

# Import models so SQLAlchemy can register them
# from server.app.models.user import User
# from server.app.models.store import Store
# from server.app.models.visitor_profile import VisitorProfile
# from server.app.models.daily_visitor_status import DailyVisitorStatus
# from server.app.models.daily_assignment import DailyAssignment
# from server.app.models.visit import Visit
# from server.app.models.telesales_followup import TelesalesFollowup
# from server.app.models.store_schedule_state import StoreScheduleState

# Create all tables defined in ORM models
def create_tables():
    Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
    create_tables()
    print('Tables created successfully')
