"""Health Check Service"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.src.config import settings
from backend.src.observability.logger import logger


def get_health_status(db: Session) -> dict:
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as err:
        logger.error(f"Database health check failed: {err}")
        db_status = f"unhealthy: {str(err)}"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "version": settings.VERSION,
        "database": db_status,
        "services": {
            "catalog": "active",
            "recommendation_engine": "active",
            "google_oauth": "configured" if settings.GOOGLE_CLIENT_ID else "unconfigured"
        }
    }
