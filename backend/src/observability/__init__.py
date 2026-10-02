"""Observability module initialization"""
from backend.src.observability.logger import logger
from backend.src.observability.health import get_health_status
from backend.src.observability.metrics import get_admin_metrics

__all__ = ["logger", "get_health_status", "get_admin_metrics"]
