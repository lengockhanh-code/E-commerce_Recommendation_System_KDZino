"""SQLAlchemy Database Connection & Session Management"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

Base = declarative_base()

db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

use_sqlite = False
try:
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args={"connect_timeout": 3}
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception:
    use_sqlite = True
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if use_sqlite:
    from app.model.models import Base as ModelsBase
    ModelsBase.metadata.create_all(bind=engine)


def get_db():
    if use_sqlite:
        from app.model.models import Base as ModelsBase
        ModelsBase.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
