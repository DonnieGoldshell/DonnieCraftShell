"""Health routes."""

from __future__ import annotations

from fastapi import APIRouter

from services.api.app.config import get_settings
from services.api.app.schemas.common import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="donniecraftshell-api",
        version="0.1.0",
        environment=settings.environment,
    )


@router.get("/api/v1/health", response_model=HealthResponse)
def api_health() -> HealthResponse:
    return health()
