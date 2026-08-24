"""Advisor analysis routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.economy_quote_workspace import (
    ECONOMY_QUOTE_WORKSPACE_VERSION,
    EconomyQuoteWorkspaceRepository,
    EconomyQuoteWorkspaceSaveStatus,
)
from packages.shared.donniecraftshell_contracts.manual_valuation_workspace import (
    MANUAL_VALUATION_WORKSPACE_VERSION,
    ManualValuationWorkspaceRepository,
    ManualValuationWorkspaceSaveStatus,
)

from services.api.app.dependencies.advisor import (
    get_advisor_orchestrator,
    get_economy_repository,
    get_economy_quote_workspace,
    get_manual_valuation_workspace,
)
from services.api.app.mappers.advisor import (
    advisor_request_to_domain,
    advisor_result_to_dto,
    manual_valuation_preview_to_dto,
)
from services.api.app.schemas.advisor import (
    AdvisorAnalyzeRequestDto,
    AdvisorAnalyzeResponseDto,
    EconomyQuoteWorkspaceDeleteResponseDto,
    EconomyQuoteWorkspaceListResponseDto,
    EconomyQuoteWorkspacePersistenceStatusDto,
    EconomyQuoteWorkspaceRecordDto,
    EconomyQuoteWorkspaceSaveRequestDto,
    EconomyQuoteWorkspaceSaveResponseDto,
    ManualValuationWorkspaceDeleteResponseDto,
    ManualValuationWorkspaceListResponseDto,
    ManualValuationWorkspacePersistenceStatusDto,
    ManualValuationWorkspaceRecordDto,
    ManualValuationWorkspaceSaveRequestDto,
    ManualValuationWorkspaceSaveResponseDto,
    ManualValuationPreviewRequestDto,
    ManualValuationPreviewResponseDto,
)


router = APIRouter(prefix="/api/v1/advisor", tags=["advisor"])


@router.post("/analyze", response_model=AdvisorAnalyzeResponseDto)
def analyze_advisor(
    request: AdvisorAnalyzeRequestDto,
    orchestrator: CraftAdvisorOrchestrator = Depends(get_advisor_orchestrator),
    economy_repository: EconomyRepository = Depends(get_economy_repository),
    economy_quote_workspace: EconomyQuoteWorkspaceRepository = Depends(get_economy_quote_workspace),
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
        as_of = request.as_of or datetime.now(timezone.utc)
        scoped_request = request.model_copy(update={"as_of": as_of})
        effective_economy_repository = economy_quote_workspace.economy_repository(
            economy_repository,
            request.league,
            as_of,
        )
        domain_request = advisor_request_to_domain(scoped_request, effective_economy_repository)
        result = orchestrator.with_economy_repository(effective_economy_repository).analyze(domain_request)
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


@router.post("/economy-quotes/workspace/quotes", response_model=EconomyQuoteWorkspaceSaveResponseDto)
def save_economy_quote(
    request: EconomyQuoteWorkspaceSaveRequestDto,
    workspace: EconomyQuoteWorkspaceRepository = Depends(get_economy_quote_workspace),
) -> EconomyQuoteWorkspaceSaveResponseDto:
    result = workspace.save_record(request.record.model_dump(mode="json", exclude_none=True))
    if result.status == EconomyQuoteWorkspaceSaveStatus.REJECTED:
        _bad_request("Economy quote workspace record was rejected.", result.warnings)
    return _economy_quote_save_response(result, workspace)


@router.put("/economy-quotes/workspace/quotes/{evidence_id}", response_model=EconomyQuoteWorkspaceSaveResponseDto)
def update_economy_quote(
    evidence_id: str,
    request: EconomyQuoteWorkspaceSaveRequestDto,
    workspace: EconomyQuoteWorkspaceRepository = Depends(get_economy_quote_workspace),
) -> EconomyQuoteWorkspaceSaveResponseDto:
    result = workspace.update_record(evidence_id, request.record.model_dump(mode="json", exclude_none=True))
    if result.status in {EconomyQuoteWorkspaceSaveStatus.REJECTED, EconomyQuoteWorkspaceSaveStatus.NOT_FOUND}:
        _bad_request("Economy quote workspace update was rejected.", result.warnings)
    return _economy_quote_save_response(result, workspace)


@router.get("/economy-quotes/workspace/quotes", response_model=EconomyQuoteWorkspaceListResponseDto)
def list_economy_quotes(
    league: str | None = None,
    asset_id: str | None = None,
    workspace: EconomyQuoteWorkspaceRepository = Depends(get_economy_quote_workspace),
) -> EconomyQuoteWorkspaceListResponseDto:
    return EconomyQuoteWorkspaceListResponseDto(
        workspace_version=ECONOMY_QUOTE_WORKSPACE_VERSION,
        records=[_economy_quote_record_to_dto(record) for record in workspace.list_records(league, asset_id)],
        persistence=_economy_quote_persistence_to_dto(workspace.persistence_status()),
        warnings=(
            "Local economy quote evidence is used only for exact matching league/asset Advisor reruns.",
            *workspace.persistence_status().warnings,
        ),
    )


@router.delete("/economy-quotes/workspace/quotes/{evidence_id}", response_model=EconomyQuoteWorkspaceDeleteResponseDto)
def delete_economy_quote(
    evidence_id: str,
    workspace: EconomyQuoteWorkspaceRepository = Depends(get_economy_quote_workspace),
) -> EconomyQuoteWorkspaceDeleteResponseDto:
    result = workspace.delete_record(evidence_id)
    if result.status == EconomyQuoteWorkspaceSaveStatus.NOT_FOUND:
        _bad_request("Economy quote workspace delete was rejected.", result.warnings)
    return EconomyQuoteWorkspaceDeleteResponseDto(
        workspace_version=ECONOMY_QUOTE_WORKSPACE_VERSION,
        status=result.status.value,
        evidence_id=result.evidence_id,
        deleted_count=1,
        persistence=_economy_quote_persistence_to_dto(workspace.persistence_status()),
        warnings=list(result.warnings),
    )


@router.delete("/economy-quotes/workspace/quotes", response_model=EconomyQuoteWorkspaceDeleteResponseDto)
def clear_economy_quotes(
    league: str | None = None,
    asset_id: str | None = None,
    workspace: EconomyQuoteWorkspaceRepository = Depends(get_economy_quote_workspace),
) -> EconomyQuoteWorkspaceDeleteResponseDto:
    result = workspace.clear_quotes(league, asset_id)
    if result.status == EconomyQuoteWorkspaceSaveStatus.REJECTED:
        _bad_request("Economy quote workspace clear was rejected.", result.warnings)
    return EconomyQuoteWorkspaceDeleteResponseDto(
        workspace_version=ECONOMY_QUOTE_WORKSPACE_VERSION,
        status=result.status.value,
        evidence_id=None,
        deleted_count=len(result.records),
        persistence=_economy_quote_persistence_to_dto(workspace.persistence_status()),
        warnings=list(result.warnings),
    )


@router.post("/manual-valuation/preview", response_model=ManualValuationPreviewResponseDto)
def preview_manual_valuation(
    request: ManualValuationPreviewRequestDto,
    economy_repository: EconomyRepository = Depends(get_economy_repository),
) -> ManualValuationPreviewResponseDto:
    try:
        return manual_valuation_preview_to_dto(request, economy_repository)
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


@router.post("/manual-valuation/workspace/evidence", response_model=ManualValuationWorkspaceSaveResponseDto)
def save_manual_valuation_evidence(
    request: ManualValuationWorkspaceSaveRequestDto,
    workspace: ManualValuationWorkspaceRepository = Depends(get_manual_valuation_workspace),
) -> ManualValuationWorkspaceSaveResponseDto:
    result = workspace.save_record(request.record.model_dump(mode="json", exclude_none=True))
    if result.status == ManualValuationWorkspaceSaveStatus.REJECTED:
        _bad_request("Manual valuation workspace evidence was rejected.", result.warnings)
    return _workspace_save_response(result, workspace)


@router.put("/manual-valuation/workspace/evidence/{evidence_id}", response_model=ManualValuationWorkspaceSaveResponseDto)
def update_manual_valuation_evidence(
    evidence_id: str,
    request: ManualValuationWorkspaceSaveRequestDto,
    workspace: ManualValuationWorkspaceRepository = Depends(get_manual_valuation_workspace),
) -> ManualValuationWorkspaceSaveResponseDto:
    result = workspace.update_record(evidence_id, request.record.model_dump(mode="json", exclude_none=True))
    if result.status in {ManualValuationWorkspaceSaveStatus.REJECTED, ManualValuationWorkspaceSaveStatus.NOT_FOUND}:
        _bad_request("Manual valuation workspace evidence update was rejected.", result.warnings)
    return _workspace_save_response(result, workspace)


@router.get("/manual-valuation/workspace/evidence", response_model=ManualValuationWorkspaceListResponseDto)
def list_manual_valuation_evidence(
    subject_id: str | None = None,
    workspace: ManualValuationWorkspaceRepository = Depends(get_manual_valuation_workspace),
) -> ManualValuationWorkspaceListResponseDto:
    try:
        records = workspace.list_records(subject_id)
    except ValueError as exc:
        _bad_request("Manual valuation workspace subject list was rejected.", (str(exc),))
    return ManualValuationWorkspaceListResponseDto(
        workspace_version=MANUAL_VALUATION_WORKSPACE_VERSION,
        records=[_workspace_record_to_dto(record) for record in records],
        persistence=_manual_workspace_persistence_to_dto(workspace.persistence_status()),
        warnings=(
            "Persisted manual valuation evidence is inactive until explicitly submitted to Advisor.",
            *workspace.persistence_status().warnings,
        ),
    )


@router.delete("/manual-valuation/workspace/evidence/{evidence_id}", response_model=ManualValuationWorkspaceDeleteResponseDto)
def delete_manual_valuation_evidence(
    evidence_id: str,
    workspace: ManualValuationWorkspaceRepository = Depends(get_manual_valuation_workspace),
) -> ManualValuationWorkspaceDeleteResponseDto:
    result = workspace.delete_record(evidence_id)
    if result.status == ManualValuationWorkspaceSaveStatus.NOT_FOUND:
        _bad_request("Manual valuation workspace evidence delete was rejected.", result.warnings)
    return ManualValuationWorkspaceDeleteResponseDto(
        workspace_version=MANUAL_VALUATION_WORKSPACE_VERSION,
        status=result.status.value,
        evidence_id=result.evidence_id,
        deleted_count=1,
        persistence=_manual_workspace_persistence_to_dto(workspace.persistence_status()),
        warnings=list(result.warnings),
    )


@router.delete("/manual-valuation/workspace/subject", response_model=ManualValuationWorkspaceDeleteResponseDto)
def clear_manual_valuation_subject(
    subject_id: str,
    workspace: ManualValuationWorkspaceRepository = Depends(get_manual_valuation_workspace),
) -> ManualValuationWorkspaceDeleteResponseDto:
    result = workspace.clear_subject(subject_id)
    if result.status == ManualValuationWorkspaceSaveStatus.REJECTED:
        _bad_request("Manual valuation workspace subject clear was rejected.", result.warnings)
    return ManualValuationWorkspaceDeleteResponseDto(
        workspace_version=MANUAL_VALUATION_WORKSPACE_VERSION,
        status=result.status.value,
        evidence_id=None,
        deleted_count=len(result.records),
        persistence=_manual_workspace_persistence_to_dto(workspace.persistence_status()),
        warnings=list(result.warnings),
    )


def _workspace_save_response(
    result,
    workspace: ManualValuationWorkspaceRepository,
) -> ManualValuationWorkspaceSaveResponseDto:
    return ManualValuationWorkspaceSaveResponseDto(
        workspace_version=MANUAL_VALUATION_WORKSPACE_VERSION,
        status=result.status.value,
        evidence_id=result.evidence_id,
        record=_workspace_record_to_dto(result.record),
        persistence=_manual_workspace_persistence_to_dto(workspace.persistence_status()),
        warnings=list(result.warnings),
    )


def _workspace_record_to_dto(record) -> ManualValuationWorkspaceRecordDto | None:
    if record is None:
        return None
    return ManualValuationWorkspaceRecordDto(**record)


def _economy_quote_save_response(
    result,
    workspace: EconomyQuoteWorkspaceRepository,
) -> EconomyQuoteWorkspaceSaveResponseDto:
    return EconomyQuoteWorkspaceSaveResponseDto(
        workspace_version=ECONOMY_QUOTE_WORKSPACE_VERSION,
        status=result.status.value,
        evidence_id=result.evidence_id,
        record=_economy_quote_record_to_dto(result.record),
        persistence=_economy_quote_persistence_to_dto(workspace.persistence_status()),
        warnings=list(result.warnings),
    )


def _economy_quote_record_to_dto(record) -> EconomyQuoteWorkspaceRecordDto | None:
    if record is None:
        return None
    return EconomyQuoteWorkspaceRecordDto(**record)


def _manual_workspace_persistence_to_dto(status) -> ManualValuationWorkspacePersistenceStatusDto:
    return ManualValuationWorkspacePersistenceStatusDto(
        storage_version=status.storage_version,
        storage_mode=status.storage_mode,
        persistence_enabled=status.persistence_enabled,
        loaded_evidence_count=status.loaded_evidence_count,
        skipped_evidence_count=status.skipped_evidence_count,
        warnings=list(status.warnings),
    )


def _economy_quote_persistence_to_dto(status) -> EconomyQuoteWorkspacePersistenceStatusDto:
    return EconomyQuoteWorkspacePersistenceStatusDto(
        storage_version=status.storage_version,
        storage_mode=status.storage_mode,
        persistence_enabled=status.persistence_enabled,
        loaded_quote_count=status.loaded_quote_count,
        skipped_quote_count=status.skipped_quote_count,
        warnings=list(status.warnings),
    )


def _bad_request(message: str, warnings) -> None:
    raise HTTPException(
        status_code=400,
        detail={
            "code": "VALIDATION_ERROR",
            "message": message,
            "recoverable": True,
            "reliable_no_result": True,
            "warnings": list(warnings),
        },
    )
