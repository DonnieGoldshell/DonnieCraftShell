"""FastAPI application entrypoint for DonnieCraftShell."""

from __future__ import annotations

try:
    from fastapi import FastAPI
except ModuleNotFoundError as exc:  # pragma: no cover - documents missing deps
    raise RuntimeError(
        "FastAPI/Pydantic are required to run the HTTP API. "
        "Install backend dependencies before starting services.api.app.main."
    ) from exc

from services.api.app.routes import advisor, health, items


app = FastAPI(title="DonnieCraftShell API", version="0.1.0")
app.include_router(health.router)
app.include_router(items.router)
app.include_router(advisor.router)
