"""Advisor analysis routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
from packages.shared.donniecraftshell_contracts.craft_investment import (
    CRAFT_INVESTMENT_WORKSPACE_VERSION,
    CraftInvestmentWorkspaceRepository,
    CraftInvestmentWorkspaceSaveStatus,
)
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.economy_quote_workspace import (
    ECONOMY_QUOTE_WORKSPACE_VERSION,
    EconomyQuoteWorkspaceRepository,
    EconomyQuoteWorkspaceSaveStatus,
)
from packages.shared.donniecraftshell_contracts.live_economy import PoeShowLiveEconomyProvider
from packages.shared.donniecraftshell_contracts.manual_valuation_workspace import (
    MANUAL_VALUATION_WORKSPACE_VERSION,
    ManualValuationWorkspaceRepository,
    ManualValuationWorkspaceSaveStatus,
)

from services.api.app.dependencies.advisor import (
    get_advisor_orchestrator,
    get_craft_investment_workspace,
    get_economy_repository,
    get_economy_quote_workspace,
    get_live_economy_provider,
    get_manual_valuation_workspace,
)
from services.api.app.mappers.advisor import (
    advisor_request_to_domain,
    advisor_result_to_dto,
    craft_investment_preview_to_dto,
    craft_investment_workspace_record_to_storage,
    manual_valuation_preview_to_dto,
    manual_valuation_workspace_record_to_storage,
)
from services.api.app.schemas.advisor import (
    AdvisorAnalyzeRequestDto,
    AdvisorAnalyzeResponseDto,
    CraftInvestmentPreviewRequestDto,
    CraftInvestmentPreviewResponseDto,
    CraftInvestmentWorkspaceDeleteResponseDto,
    CraftInvestmentWorkspaceListResponseDto,
    CraftInvestmentWorkspacePersistenceStatusDto,
    CraftInvestmentWorkspaceRecordDto,
    CraftInvestmentWorkspaceSaveRequestDto,
    CraftInvestmentWorkspaceSaveResponseDto,
    EconomyQuoteWorkspaceDeleteResponseDto,
    EconomyQuoteWorkspaceListResponseDto,
    EconomyQuoteWorkspacePersistenceStatusDto,
    EconomyQuoteWorkspaceRecordDto,
    EconomyQuoteWorkspaceSaveRequestDto,
    EconomyQuoteWorkspaceSaveResponseDto,
    EconomyEvidenceSourceDto,
    EconomyEvidenceSummaryDto,
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
    live_economy_provider: PoeShowLiveEconomyProvider = Depends(get_live_economy_provider),
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
        live_result = live_economy_provider.economy_repository(
            economy_repository,
            request.league,
            as_of,
        )
        effective_economy_repository = economy_quote_workspace.economy_repository(
            live_result.repository,
            request.league,
            as_of,
        )
        domain_request = advisor_request_to_domain(scoped_request, effective_economy_repository)
        result = orchestrator.with_economy_repository(effective_economy_repository).analyze(domain_request)
        dto = advisor_result_to_dto(result)
        dto.economy_evidence = _economy_evidence_summary(
            dto,
            live_economy_provider,
            live_result,
        )
        dto.warnings.extend(live_result.warnings)
        return dto
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


def _economy_evidence_summary(
    dto: AdvisorAnalyzeResponseDto,
    live_economy_provider: PoeShowLiveEconomyProvider,
    live_result,
) -> EconomyEvidenceSummaryDto:
    line_summaries = _economy_line_summaries(dto)
    resolved_assets = {line["asset_id"] for line in line_summaries if line["resolved"]}
    missing_assets = {line["asset_id"] for line in line_summaries if not line["resolved"]}
    missing_assets -= resolved_assets
    breakdowns = _economy_source_breakdown(
        dto.context.league,
        line_summaries,
        live_economy_provider,
        live_result,
        missing_assets,
    )
    source_modes = {breakdown.mode for breakdown in breakdowns if breakdown.mode != "MISSING"}
    live_modes = {mode for mode in source_modes if mode.startswith("LIVE")}
    if "LOCAL_OVERRIDE" in source_modes and len(source_modes) > 1:
        mode = "MIXED"
    elif live_modes:
        mode = _live_result_mode(live_result)
    elif source_modes:
        mode = next(iter(source_modes))
    elif _live_economy_enabled(live_economy_provider, live_result):
        mode = "LIVE_UNAVAILABLE"
    elif missing_assets:
        mode = "MISSING"
    else:
        mode = "UNAVAILABLE"
    freshness_values = [line["freshness"] for line in line_summaries if line["resolved"] and line.get("freshness")]
    return EconomyEvidenceSummaryDto(
        mode=mode,
        live_economy_enabled=_live_economy_enabled(live_economy_provider, live_result),
        provider="poe.show" if _live_economy_enabled(live_economy_provider, live_result) else None,
        league=dto.context.league,
        cache_path=_live_cache_path(live_economy_provider) if _live_economy_enabled(live_economy_provider, live_result) else None,
        resolved_required_asset_count=len(resolved_assets),
        missing_required_asset_count=len(missing_assets),
        freshness=_worst_freshness(freshness_values),
        source_breakdown=breakdowns,
        warnings=list(live_result.warnings),
    )


def _economy_line_summaries(dto: AdvisorAnalyzeResponseDto) -> list[dict]:
    summaries: list[dict] = []
    for action in dto.actions:
        for line in action.material_cost.lines:
            asset_id = line.get("asset_id")
            if not isinstance(asset_id, str):
                continue
            summaries.append(
                {
                    "asset_id": asset_id,
                    "resolved": line.get("unit_price") is not None,
                    "source": line.get("source"),
                    "snapshot_id": line.get("snapshot_id") or line.get("quote_snapshot_id"),
                    "freshness": line.get("freshness"),
                    "retrieved_at": _line_retrieved_at(line),
                }
            )
    return summaries


def _economy_source_breakdown(
    league: str,
    lines: list[dict],
    live_economy_provider: PoeShowLiveEconomyProvider,
    live_result,
    missing_assets: set[str],
) -> list[EconomyEvidenceSourceDto]:
    grouped: dict[str, list[dict]] = {}
    for line in lines:
        if not line["resolved"]:
            continue
        grouped.setdefault(_line_source_mode(line, live_result), []).append(line)
    breakdowns = [
        EconomyEvidenceSourceDto(
            mode=mode,
            provider=_provider_for_mode(mode),
            league=league,
            snapshot_ids=sorted({str(line["snapshot_id"]) for line in mode_lines if line.get("snapshot_id")}),
            resolved_required_asset_count=len({line["asset_id"] for line in mode_lines}),
            missing_required_asset_count=0,
            freshness=_worst_freshness([line["freshness"] for line in mode_lines if line.get("freshness")]),
            retrieved_at=max(
                (line["retrieved_at"] for line in mode_lines if line.get("retrieved_at") is not None),
                default=None,
            ),
            cache_path=_live_cache_path(live_economy_provider) if mode.startswith("LIVE") else None,
            warnings=_warnings_for_mode(mode, live_result),
        )
        for mode, mode_lines in sorted(grouped.items())
    ]
    if _live_economy_enabled(live_economy_provider, live_result) and not any(item.mode.startswith("LIVE") for item in breakdowns):
        breakdowns.append(
            EconomyEvidenceSourceDto(
                mode="LIVE_UNAVAILABLE",
                provider="poe.show",
                league=league,
                cache_path=_live_cache_path(live_economy_provider),
                warnings=list(live_result.warnings) or ["Live economy provider returned no usable snapshots."],
            )
        )
    if missing_assets:
        breakdowns.append(
            EconomyEvidenceSourceDto(
                mode="MISSING",
                provider=None,
                league=league,
                missing_required_asset_count=len(missing_assets),
                warnings=["Required economy quote evidence remains unavailable."],
            )
        )
    return breakdowns


def _line_source_mode(line: dict, live_result) -> str:
    source = line.get("source")
    snapshot_id = str(line.get("snapshot_id") or "")
    live_snapshot_ids = {snapshot.snapshot_id for snapshot in live_result.snapshots}
    if source == "LOCAL_OPERATOR_ECONOMY_QUOTE":
        return "LOCAL_OVERRIDE"
    if snapshot_id in live_snapshot_ids or snapshot_id.startswith("economy-snapshot:live-"):
        return _live_result_mode(live_result)
    if source == "poe.show":
        return "OFFLINE_BUNDLED"
    return "PROVIDER_SNAPSHOT"


def _live_result_mode(live_result) -> str:
    if live_result.fetched_count and live_result.cache_hit_count:
        return "LIVE_MIXED"
    if live_result.fetched_count:
        return "LIVE_FETCHED"
    if live_result.cache_hit_count:
        warnings = " ".join(live_result.warnings).lower()
        if "fetch failed" in warnings or "returned http" in warnings:
            return "LIVE_CACHE_FALLBACK"
        return "LIVE_CACHED"
    return "LIVE_UNAVAILABLE"


def _live_economy_enabled(live_economy_provider: PoeShowLiveEconomyProvider, live_result) -> bool:
    config = getattr(live_economy_provider, "config", None)
    enabled = getattr(config, "enabled", None)
    if enabled is not None:
        return bool(enabled)
    return bool(live_result.fetched_count or live_result.cache_hit_count or live_result.snapshots)


def _live_cache_path(live_economy_provider: PoeShowLiveEconomyProvider) -> str | None:
    cache_dir = getattr(live_economy_provider, "cache_dir", None)
    return str(cache_dir) if cache_dir is not None else None


def _provider_for_mode(mode: str) -> str | None:
    if mode.startswith("LIVE") or mode == "OFFLINE_BUNDLED":
        return "poe.show"
    if mode == "LOCAL_OVERRIDE":
        return "LOCAL_OPERATOR_ECONOMY_QUOTE"
    return None


def _warnings_for_mode(mode: str, live_result) -> list[str]:
    if mode.startswith("LIVE"):
        return list(live_result.warnings)
    if mode == "OFFLINE_BUNDLED":
        return ["Bundled offline economy snapshot; not runtime live economy evidence."]
    if mode == "LOCAL_OVERRIDE":
        return ["Local operator quote override; no external provider fetch was performed for this quote."]
    return []


def _line_retrieved_at(line: dict) -> datetime | None:
    for provenance in line.get("provenance", []):
        value = provenance.get("retrieved_at")
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            continue
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return None


def _worst_freshness(values: list[str]) -> str | None:
    if not values:
        return None
    order = {"FRESH": 0, "AGING": 1, "STALE": 2, "UNAVAILABLE": 3}
    return max(values, key=lambda value: order.get(value, 3))


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


@router.post("/craft-investment/preview", response_model=CraftInvestmentPreviewResponseDto)
def preview_craft_investment(
    request: CraftInvestmentPreviewRequestDto,
) -> CraftInvestmentPreviewResponseDto:
    try:
        return craft_investment_preview_to_dto(request)
    except ValueError as exc:
        _bad_request("Craft investment preview was rejected.", (str(exc),))


@router.post("/craft-investment/workspace/entries", response_model=CraftInvestmentWorkspaceSaveResponseDto)
def save_craft_investment_entry(
    request: CraftInvestmentWorkspaceSaveRequestDto,
    workspace: CraftInvestmentWorkspaceRepository = Depends(get_craft_investment_workspace),
) -> CraftInvestmentWorkspaceSaveResponseDto:
    result = workspace.save_record(craft_investment_workspace_record_to_storage(request.record))
    if result.status == CraftInvestmentWorkspaceSaveStatus.REJECTED:
        _bad_request("Craft investment workspace entry was rejected.", result.warnings)
    return _craft_investment_save_response(result, workspace)


@router.put("/craft-investment/workspace/entries/{entry_id}", response_model=CraftInvestmentWorkspaceSaveResponseDto)
def update_craft_investment_entry(
    entry_id: str,
    request: CraftInvestmentWorkspaceSaveRequestDto,
    workspace: CraftInvestmentWorkspaceRepository = Depends(get_craft_investment_workspace),
) -> CraftInvestmentWorkspaceSaveResponseDto:
    result = workspace.update_record(entry_id, craft_investment_workspace_record_to_storage(request.record))
    if result.status in {CraftInvestmentWorkspaceSaveStatus.REJECTED, CraftInvestmentWorkspaceSaveStatus.NOT_FOUND}:
        _bad_request("Craft investment workspace update was rejected.", result.warnings)
    return _craft_investment_save_response(result, workspace)


@router.get("/craft-investment/workspace/entries", response_model=CraftInvestmentWorkspaceListResponseDto)
def list_craft_investment_entries(
    ledger_id: str | None = None,
    subject_id: str | None = None,
    workspace: CraftInvestmentWorkspaceRepository = Depends(get_craft_investment_workspace),
) -> CraftInvestmentWorkspaceListResponseDto:
    return CraftInvestmentWorkspaceListResponseDto(
        workspace_version=CRAFT_INVESTMENT_WORKSPACE_VERSION,
        records=[CraftInvestmentWorkspaceRecordDto(**record) for record in workspace.list_records(ledger_id, subject_id)],
        persistence=_craft_investment_persistence_to_dto(workspace.persistence_status()),
    )


@router.delete("/craft-investment/workspace/entries/{entry_id}", response_model=CraftInvestmentWorkspaceDeleteResponseDto)
def delete_craft_investment_entry(
    entry_id: str,
    workspace: CraftInvestmentWorkspaceRepository = Depends(get_craft_investment_workspace),
) -> CraftInvestmentWorkspaceDeleteResponseDto:
    result = workspace.delete_record(entry_id)
    if result.status == CraftInvestmentWorkspaceSaveStatus.REJECTED:
        _bad_request("Craft investment workspace delete was rejected.", result.warnings)
    return CraftInvestmentWorkspaceDeleteResponseDto(
        workspace_version=CRAFT_INVESTMENT_WORKSPACE_VERSION,
        status=result.status.value,
        entry_id=result.entry_id,
        deleted_count=1 if result.record else 0,
        persistence=_craft_investment_persistence_to_dto(workspace.persistence_status()),
        warnings=list(result.warnings),
    )


@router.delete("/craft-investment/workspace/ledger", response_model=CraftInvestmentWorkspaceDeleteResponseDto)
def clear_craft_investment_ledger(
    ledger_id: str,
    workspace: CraftInvestmentWorkspaceRepository = Depends(get_craft_investment_workspace),
) -> CraftInvestmentWorkspaceDeleteResponseDto:
    result = workspace.clear_ledger(ledger_id)
    if result.status == CraftInvestmentWorkspaceSaveStatus.REJECTED:
        _bad_request("Craft investment workspace ledger clear was rejected.", result.warnings)
    return CraftInvestmentWorkspaceDeleteResponseDto(
        workspace_version=CRAFT_INVESTMENT_WORKSPACE_VERSION,
        status=result.status.value,
        entry_id=None,
        deleted_count=len(result.records),
        persistence=_craft_investment_persistence_to_dto(workspace.persistence_status()),
        warnings=list(result.warnings),
    )


@router.post("/manual-valuation/workspace/evidence", response_model=ManualValuationWorkspaceSaveResponseDto)
def save_manual_valuation_evidence(
    request: ManualValuationWorkspaceSaveRequestDto,
    workspace: ManualValuationWorkspaceRepository = Depends(get_manual_valuation_workspace),
) -> ManualValuationWorkspaceSaveResponseDto:
    try:
        record = manual_valuation_workspace_record_to_storage(request.record)
    except ValueError as exc:
        _bad_request("Manual valuation workspace evidence was rejected.", (str(exc),))
    result = workspace.save_record(record)
    if result.status == ManualValuationWorkspaceSaveStatus.REJECTED:
        _bad_request("Manual valuation workspace evidence was rejected.", result.warnings)
    return _workspace_save_response(result, workspace)


@router.put("/manual-valuation/workspace/evidence/{evidence_id}", response_model=ManualValuationWorkspaceSaveResponseDto)
def update_manual_valuation_evidence(
    evidence_id: str,
    request: ManualValuationWorkspaceSaveRequestDto,
    workspace: ManualValuationWorkspaceRepository = Depends(get_manual_valuation_workspace),
) -> ManualValuationWorkspaceSaveResponseDto:
    try:
        record = manual_valuation_workspace_record_to_storage(request.record)
    except ValueError as exc:
        _bad_request("Manual valuation workspace evidence update was rejected.", (str(exc),))
    result = workspace.update_record(evidence_id, record)
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


def _craft_investment_save_response(
    result,
    workspace: CraftInvestmentWorkspaceRepository,
) -> CraftInvestmentWorkspaceSaveResponseDto:
    return CraftInvestmentWorkspaceSaveResponseDto(
        workspace_version=CRAFT_INVESTMENT_WORKSPACE_VERSION,
        status=result.status.value,
        entry_id=result.entry_id,
        record=_craft_investment_record_to_dto(result.record),
        persistence=_craft_investment_persistence_to_dto(workspace.persistence_status()),
        warnings=list(result.warnings),
    )


def _craft_investment_record_to_dto(record) -> CraftInvestmentWorkspaceRecordDto | None:
    if record is None:
        return None
    return CraftInvestmentWorkspaceRecordDto(**record)


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


def _craft_investment_persistence_to_dto(status) -> CraftInvestmentWorkspacePersistenceStatusDto:
    return CraftInvestmentWorkspacePersistenceStatusDto(
        storage_version=status.storage_version,
        storage_mode=status.storage_mode,
        persistence_enabled=status.persistence_enabled,
        loaded_entry_count=status.loaded_entry_count,
        skipped_entry_count=status.skipped_entry_count,
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
