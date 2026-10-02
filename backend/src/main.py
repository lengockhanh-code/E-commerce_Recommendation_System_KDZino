"""MerRec FastAPI Application Entry Point"""

import sys
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Add repository root to python path so module imports work reliably
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.src.config import settings
from backend.src.database.connection import engine, Base, get_db
from backend.src.middleware.logging import RequestLoggingMiddleware
from backend.src.observability.health import get_health_status
from backend.src.services.auth_service import handle_google_callback
from backend.src.api.router import api_router

# Schema is managed by explicit migrations, including in local development.

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc"
)

# Request timing & structured logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Cross-Origin Resource Sharing (CORS) Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include All API Routes under /api/v1
app.include_router(api_router, prefix=settings.API_V1_STR)


from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
import logging


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request, exc):
    logging.getLogger(__name__).warning("database_request_failed type=%s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Dịch vụ dữ liệu tạm thời không khả dụng. Vui lòng thử lại."})


import urllib.parse
from fastapi.responses import RedirectResponse

from backend.src.api.auth import google_callback
app.add_api_route("/auth/google/callback", google_callback, methods=["GET"], include_in_schema=False)


@app.get("/health", tags=["Health Check"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for container probes and load balancers"""
    return get_health_status(db)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs": f"{settings.API_V1_STR}/docs",
        "version": settings.VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.src.main:app", host="0.0.0.0", port=8000, reload=True)
