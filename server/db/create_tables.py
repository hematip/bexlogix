from server.db.base import Base
from server.db.database import engine
from server.app.models.model_registry import register_models

# Create all tables defined in ORM models.
# MVP note: migration tool is intentionally not introduced yet.
def create_tables():
    register_models()
    Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
    create_tables()
    print('Tables created successfully')
