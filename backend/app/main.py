"""Compatibility shim for backend.app.main -> backend.src.main"""
from backend.src.main import app

__all__ = ["app"]
