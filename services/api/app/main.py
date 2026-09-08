"""FastAPI application entrypoint for DonnieCraftShell."""

from __future__ import annotations

import logging

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError as exc:  # pragma: no cover - documents missing deps
    raise RuntimeError(
        "FastAPI/Pydantic are required to run the HTTP API. "
        "Install backend dependencies before starting services.api.app.main."
    ) from exc

from services.api.app.config import get_settings
from services.api.app.routes import advisor, health, items, observations


logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)
app = FastAPI(title="DonnieCraftShell API", version="0.1.0")
settings = get_settings()
if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["content-type"],
    )
app.include_router(health.router)
app.include_router(items.router)
app.include_router(advisor.router)
app.include_router(observations.router)
