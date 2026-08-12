"""Advisor analysis routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository

from services.api.app.dependencies.advisor import get_advisor_orchestrator, get_economy_repository
from services.api.app.mappers.advisor import advisor_request_to_domain, advisor_result_to_dto
from services.api.app.schemas.advisor import AdvisorAnalyzeRequestDto, AdvisorAnalyzeResponseDto


router = APIRouter(prefix="/api/v1/advisor", tags=["advisor"])


@router.post("/analyze", response_model=AdvisorAnalyzeResponseDto)
def analyze_advisor(
    request: AdvisorAnalyzeRequestDto,
    orchestrator: CraftAdvisorOrchestrator = Depends(get_advisor_orchestrator),
    economy_repository: EconomyRepository = Depends(get_economy_repository),
) -> AdvisorAnalyzeResponseDto:
    if not request.clipboard_text.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "clipboard_text is required.",
                "recoverable": True,
                "reliable_no_result": True,
            },
        )
    try:
        domain_request = advisor_request_to_domain(request, economy_repository)
        result = orchestrator.analyze(domain_request)
        return advisor_result_to_dto(result)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(exc),
                "recoverable": True,
                "reliable_no_result": True,
            },
        ) from exc
