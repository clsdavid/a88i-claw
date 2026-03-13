from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from autocrab.core.models.config import settings

# Create the SQLAlchemy engine using the configured database URL
# Using connect_args={"check_same_thread": False} is required for SQLite and FastAPI
engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.db_url else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
