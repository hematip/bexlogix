from server.db.base import Base
from server.db.database import engine

# Import models so SQLAlchemy can register them
from server.app.models.user import User
from server.app.models.store import Store

# Create all tables defined in ORM models
def create_tables():
    Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
    create_tables()
    print('Tables created successfully')
