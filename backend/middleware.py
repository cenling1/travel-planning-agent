from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from time import monotonic
import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RequestGuardMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        rate_limit_per_minute: int = 0,
        max_inflight_requests: int = 0,
    ):
        super().__init__(app)
        self.rate_limit_per_minute = rate_limit_per_minute
        self.windows: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()
        self.semaphore = (
            asyncio.Semaphore(max_inflight_requests)
            if max_inflight_requests > 0
            else None
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        if self.rate_limit_per_minute > 0 and await self._is_rate_limited(request):
            return JSONResponse({"detail": "请求过于频繁，请稍后再试"}, status_code=429)

        if self.semaphore is None:
            return await call_next(request)

        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=0.1)
        except TimeoutError:
            return JSONResponse({"detail": "服务繁忙，请稍后再试"}, status_code=503)
        try:
            return await call_next(request)
        finally:
            self.semaphore.release()

    async def _is_rate_limited(self, request: Request) -> bool:
        now = monotonic()
        authorization = request.headers.get("authorization", "")
        forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        key = (
            hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:24]
            if authorization
            else forwarded_for or (request.client.host if request.client else "unknown")
        )
        async with self.lock:
            window = self.windows[key]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self.rate_limit_per_minute:
                return True
            window.append(now)
            return False
