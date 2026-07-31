"""Application factory and entry point for the XDebug backend.

Run locally with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.router import api_router
from app.container import Container
from app.core.config import Settings
from app.core.errors import XDebugError
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application instance."""
    container = Container(settings)
    configured = container.settings
    configure_logging(configured.log_level)
    logger = container.logger
    logger.structured(
        logging.INFO,
        "application starting",
        environment=configured.environment,
        version=__version__,
    )

    app = FastAPI(
        title=configured.app_name,
        version=__version__,
        description="Backend services for the XDebug explainable debugging platform.",
        debug=configured.debug,
    )
    app.state.container = container

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(XDebugError, _xdebug_error_handler)
    app.include_router(api_router, prefix=configured.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        """Return a minimal landing payload."""
        return {"app": configured.app_name, "docs": "/docs"}

    return app


async def _xdebug_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Serialize XDebugError instances into the structured error envelope."""
    error = cast(XDebugError, exc)
    logger = get_logger("xdebug")
    logger.structured(
        logging.ERROR,
        "request failed",
        reason=error.reason,
        path=request.url.path,
        module=error.module,
    )
    return JSONResponse(status_code=error.status_code, content=error.to_dict())


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
