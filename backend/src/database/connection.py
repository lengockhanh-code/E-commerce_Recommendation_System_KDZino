"""Database Engine, Session & Connection Dependency"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.src.config import settings

db_url = settings.DATABASE_URL

if db_url.startswith("sqlite"):
    from sqlalchemy.pool import StaticPool
    connect_args = {"check_same_thread": False}
    if ":memory:" in db_url:
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            poolclass=StaticPool
        )
    else:
        engine = create_engine(db_url, connect_args=connect_args)
else:
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_timeout=5,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=10000"},
        pool_size=10,
        max_overflow=20
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for providing database sessions per request"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
