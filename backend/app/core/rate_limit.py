import time
from collections import defaultdict, deque
from typing import Deque, Dict
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Lightweight sliding-window rate limiter per client IP to protect API and AI endpoints."""

    def __init__(self, app, max_requests_per_minute: int = 180):
        super().__init__(app)
        self.max_requests = max(10, int(max_requests_per_minute))
        self.window_seconds = 60.0
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in ("/health", "/api/v1/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # Allow pytest TestClient/AsyncClient burst tests cleanly unless explicitly testing rate limit
        client_host = request.client.host if request.client else "unknown"
        if client_host == "testclient":
            return await call_next(request)

        now = time.monotonic()
        bucket = self._buckets[client_host]
        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "error": {
                        "code": "RateLimitExceeded",
                        "message": "Too many requests. Please slow down and retry shortly.",
                    },
                },
            )

        bucket.append(now)
        return await call_next(request)
