"""HTTP middleware for structured request logging."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from app.core.logging import get_logger, log_context

logger = get_logger("xdebug.http")


class RequestLoggingMiddleware:
    """Log every HTTP request with method, path, status and duration."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Wrap the ASGI app, logging each HTTP request as structured JSON."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:12]
        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))
        started = time.perf_counter()

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                duration_ms = (time.perf_counter() - started) * 1000.0
                logger.structured(
                    logging.INFO,
                    "request completed",
                    status=message.get("status"),
                    duration_ms=round(duration_ms, 2),
                )
            await send(message)

        with log_context(request_id=request_id, method=method, path=path):
            await self.app(scope, receive, send_wrapper)
