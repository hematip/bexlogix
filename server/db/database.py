from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Where is my db
DATABASE_URL = "sqlite:///./bexlogix.db"

# The main connection to db
engine = create_engine(
    DATABASE_URL,
    connect_args={'check_same_thread': False},
)

# Take session from db
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Create a new database session
def get_db_session():
    return SessionLocal()