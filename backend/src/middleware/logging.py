"""HTTP Request Execution Time & Logging Middleware"""

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from backend.src.observability.logger import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} ({process_time:.2f}ms)"
        )
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        return response
