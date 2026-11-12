from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# For SQLite, check_same_thread=False is needed for multi-threaded FastAPI workers
connect_args = {}
db_url = settings.DATABASE_URL

# Normalize PostgreSQL connection strings to explicitly use psycopg2
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

