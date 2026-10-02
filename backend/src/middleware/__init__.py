"""Middleware package initialization"""
from backend.src.middleware.logging import RequestLoggingMiddleware

__all__ = ["RequestLoggingMiddleware"]
