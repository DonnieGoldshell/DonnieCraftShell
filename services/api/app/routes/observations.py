"""Manual craft observation recorder routes."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
from packages.shared.donniecraftshell_contracts.domain import GameContext
from packages.shared.donniecraftshell_contracts.curated_observation_import import (
    build_empirical_datasets_from_curated_export,
)
from packages.shared.donniecraftshell_contracts.empirical_probability import (
    EMPIRICAL_DATASET_REGISTRY_VERSION,
    EmpiricalDatasetRegistrationStatus,
    EmpiricalProbabilityDatasetRegistry,
)
from packages.shared.donniecraftshell_contracts.observation_recorder import (
    CraftObservationRecorder,
    OBSERVATION_RECORDER_VERSION,
    ObservationDraft,
)
from packages.shared.donniecraftshell_contracts.observation_review import (
    OBSERVATION_REVIEW_VERSION,
    ObservationReviewDecision,
    ObservationReviewStatus,
    review_observation_batches,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item

from services.api.app.dependencies.advisor import get_advisor_orchestrator, get_empirical_probability_registry
from services.api.app.schemas.observations import (
    CraftObservationExportRequestDto,
    CraftObservationExportResponseDto,
    CraftObservationRecordRequestDto,
    CraftObservationRecordResponseDto,
    CuratedObservationBuildRequestDto,
    CuratedObservationBuildResponseDto,
    CuratedObservationRejectedRecordDto,
    EmpiricalDatasetListResponseDto,
    EmpiricalDatasetRegisterRequestDto,
    EmpiricalDatasetRegisterResponseDto,
    EmpiricalDatasetSummaryDto,
    ObservationReviewRecordDto,
    ObservationReviewRequestDto,
    ObservationReviewResponseDto,
    ObservationClassificationDto,
)


router = APIRouter(prefix="/api/v1/observations", tags=["observations"])


@router.post("/record", response_model=CraftObservationRecordResponseDto)
def record_observation(
    request: CraftObservationRecordRequestDto,
    orchestrator: CraftAdvisorOrchestrator = Depends(get_advisor_orchestrator),
) -> CraftObservationRecordResponseDto:
    if not request.before_clipboard_text.strip() or not request.after_clipboard_text.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "before_clipboard_text and after_clipboard_text are required.",
                "recoverable": True,
                "reliable_no_result": True,
            },
        )
    game_context = GameContext(game=request.game, league=request.league, game_version=request.game_version)
    before = parse_clipboard_item(request.before_clipboard_text, game_context)
    after = parse_clipboard_item(request.after_clipboard_text, game_context)
    if before.item is None or after.item is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PARSE_FAILURE",
                "message": "before and after clipboard text must both parse as supported items.",
                "recoverable": True,
                "reliable_no_result": True,
            },
    )
    _validate_item_context(request, before.item, after.item)
    crafting_dataset_version = _trusted_crafting_dataset_version(request, orchestrator)
    modifier_dataset_version = _trusted_modifier_dataset_version(request, orchestrator)
    outcome_set = _trusted_outcome_set(request, before.item, orchestrator, modifier_dataset_version)
    source_outcome_set_id = _trusted_source_outcome_set_id(outcome_set)

    recorder = CraftObservationRecorder()
    if request.manual_outcome_id or request.manual_reason:
        classification = recorder.classify_manually(
            request.manual_outcome_id,
            tuple(state.outcome_id for state in outcome_set.hypothetical_states),
            request.manual_reason or "",
        )
    else:
        classification = recorder.classify_automatically(before.item, after.item, outcome_set)

    recorded = recorder.record(
        ObservationDraft(
            action_id=request.action_id,
            source_outcome_set_id=source_outcome_set_id,
            item_class=before.item.item_class or "",
            league=request.league,
            before_item=before.item,
            after_item=after.item,
            observed_at=request.observed_at,
            source_id=request.source_id,
            game=request.game,
            game_version=request.game_version,
            crafting_dataset_version=crafting_dataset_version,
            modifier_dataset_version=modifier_dataset_version,
            source_uri=request.source_uri,
            synthetic=request.synthetic,
        ),
        classification,
    )
    return CraftObservationRecordResponseDto(
        raw_record_id=recorded.raw_record_id,
        classification=ObservationClassificationDto(
            method=classification.method.value,
            outcome_id=classification.outcome_id,
            reason=classification.reason,
            warnings=list(classification.warnings),
        ),
        before_item_fingerprint=recorded.before_item_fingerprint,
        after_item_fingerprint=recorded.after_item_fingerprint,
        export_record=recorded.to_export_record(),
        warnings=list(recorded.warnings),
    )


@router.post("/export", response_model=CraftObservationExportResponseDto)
def export_observations(request: CraftObservationExportRequestDto) -> CraftObservationExportResponseDto:
    return CraftObservationExportResponseDto(
        recorder_version=OBSERVATION_RECORDER_VERSION,
        exported_at=datetime.now(timezone.utc),
        observations=request.observations,
        warnings=["Recorder exports are raw observations; import/readiness gates still apply."],
    )


@router.post("/review", response_model=ObservationReviewResponseDto)
def review_observations(request: ObservationReviewRequestDto) -> ObservationReviewResponseDto:
    batch_payloads = list(request.batches)
    if request.observations:
        batch_payloads.append({"observations": request.observations})
    if not batch_payloads:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "At least one observation batch or observations list is required.",
                "recoverable": True,
                "reliable_no_result": True,
            },
        )
    try:
        decisions = tuple(
            ObservationReviewDecision(
                raw_record_id=decision.raw_record_id,
                status=ObservationReviewStatus(decision.status),
                reviewed_at=decision.reviewed_at,
                note=decision.note,
                reviewer_id=decision.reviewer_id,
            )
            for decision in request.decisions
        )
        result = review_observation_batches(batch_payloads, decisions)
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

    manifest = result.manifest.to_dict()
    return ObservationReviewResponseDto(
        review_version=OBSERVATION_REVIEW_VERSION,
        records=[
            ObservationReviewRecordDto(
                raw_record_id=record.raw_record_id,
                status=record.decision.status.value,
                duplicate=record.duplicate,
                valid_for_import=record.valid_for_import,
                exported=record.accepted_for_export,
                classification_method=record.original_record.get("classification_method"),
                outcome_id=record.original_record.get("outcome_id"),
                unclassified=bool(record.original_record.get("unclassified", False)),
                synthetic=bool(record.original_record.get("synthetic", False)),
                action_id=record.original_record.get("action_id"),
                source_outcome_set_id=record.original_record.get("source_outcome_set_id"),
                warnings=list(record.warnings),
            )
            for record in result.records
        ],
        accepted_export=result.accepted_export,
        review_manifest=manifest,
        warnings=list(result.warnings),
    )


@router.post("/build-empirical-datasets", response_model=CuratedObservationBuildResponseDto)
def build_empirical_datasets(request: CuratedObservationBuildRequestDto) -> CuratedObservationBuildResponseDto:
    try:
        result = build_empirical_datasets_from_curated_export(
            request.accepted_export,
            dataset_id_prefix=request.dataset_id_prefix,
        )
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
    payload = result.to_dict()
    return CuratedObservationBuildResponseDto(
        build_version=result.build_version,
        built_at=result.built_at,
        source_record_count=result.source_record_count,
        imported_record_count=result.imported_record_count,
        accepted_record_count=result.accepted_record_count,
        duplicate_record_count=result.duplicate_record_count,
        unclassified_record_count=result.unclassified_record_count,
        invalid_record_count=result.invalid_record_count,
        dataset_count=result.dataset_count,
        dataset_ids=list(result.dataset_ids),
        datasets=payload["datasets"],
        rejected_records=[
            CuratedObservationRejectedRecordDto(raw_record_id=record.raw_record_id, reason=record.reason)
            for record in result.rejected_records
        ],
        warnings=list(result.warnings),
    )


@router.post("/empirical-datasets/register", response_model=EmpiricalDatasetRegisterResponseDto)
def register_empirical_dataset(
    request: EmpiricalDatasetRegisterRequestDto,
    registry: EmpiricalProbabilityDatasetRegistry = Depends(get_empirical_probability_registry),
) -> EmpiricalDatasetRegisterResponseDto:
    result = registry.register_raw_payload(request.dataset)
    if result.status == EmpiricalDatasetRegistrationStatus.REJECTED:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "Empirical probability dataset registration was rejected.",
                "recoverable": True,
                "reliable_no_result": True,
                "warnings": list(result.warnings),
            },
        )
    return EmpiricalDatasetRegisterResponseDto(
        registry_version=EMPIRICAL_DATASET_REGISTRY_VERSION,
        status=result.status.value,
        dataset_id=result.dataset_id,
        dataset=_dataset_summary_to_dto(result.summary),
        warnings=list(result.warnings),
    )


@router.get("/empirical-datasets", response_model=EmpiricalDatasetListResponseDto)
def list_empirical_datasets(
    registry: EmpiricalProbabilityDatasetRegistry = Depends(get_empirical_probability_registry),
) -> EmpiricalDatasetListResponseDto:
    return EmpiricalDatasetListResponseDto(
        registry_version=EMPIRICAL_DATASET_REGISTRY_VERSION,
        datasets=[_dataset_summary_to_dto(summary) for summary in registry.list_summaries()],
        warnings=("Registered empirical datasets remain inactive until an Advisor request explicitly selects a dataset ID.",),
    )


def _validate_item_context(request: CraftObservationRecordRequestDto, before_item, after_item) -> None:
    if before_item.item_class != after_item.item_class:
        _bad_request("before and after item_class must match.")
    if request.item_class and before_item.item_class != request.item_class:
        _bad_request("request item_class does not match parsed before/after items.")
    identity_fields = ("rarity", "base_type", "item_level", "required_level")
    for field_name in identity_fields:
        if getattr(before_item, field_name) != getattr(after_item, field_name):
            _bad_request(f"before and after item {field_name} must match for recorder evidence.")
    before_implicits = tuple(modifier.raw_text for modifier in before_item.implicit_modifiers)
    after_implicits = tuple(modifier.raw_text for modifier in after_item.implicit_modifiers)
    if before_implicits != after_implicits:
        _bad_request("before and after implicit modifiers must match for recorder evidence.")


def _trusted_outcome_set(
    request: CraftObservationRecordRequestDto,
    before_item,
    orchestrator: CraftAdvisorOrchestrator,
    modifier_dataset_version: str,
):
    try:
        action = next(
            action
            for action in orchestrator.craft_action_engine.dataset.actions
            if action.action_id == request.action_id
        )
    except StopIteration as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"Unknown craft action: {request.action_id}",
                "recoverable": True,
                "reliable_no_result": True,
            },
        ) from exc
    affix_state = orchestrator.affix_state_resolver.resolve(before_item)
    applicability = orchestrator.craft_action_engine.evaluate_action(action, before_item, affix_state)
    return orchestrator.outcome_engine.enumerate_outcomes(
        before_item,
        affix_state,
        action,
        applicability,
        orchestrator.game_data_repository,
        modifier_dataset_version,
    )


def _trusted_crafting_dataset_version(
    request: CraftObservationRecordRequestDto,
    orchestrator: CraftAdvisorOrchestrator,
) -> str:
    dataset_id = orchestrator.craft_action_engine.dataset.dataset_id
    if request.crafting_dataset_version and request.crafting_dataset_version != dataset_id:
        _bad_request("request crafting_dataset_version does not match backend crafting dataset.")
    return dataset_id


def _trusted_modifier_dataset_version(
    request: CraftObservationRecordRequestDto,
    orchestrator: CraftAdvisorOrchestrator,
) -> str:
    dataset_ids = tuple(sorted(orchestrator.game_data_repository._datasets))
    if not dataset_ids:
        _bad_request("backend game-data repository has no loaded modifier dataset.")
    if request.modifier_dataset_version:
        if request.modifier_dataset_version not in dataset_ids:
            _bad_request("request modifier_dataset_version does not match a backend modifier dataset.")
        return request.modifier_dataset_version
    if len(dataset_ids) != 1:
        _bad_request("modifier_dataset_version is required when multiple backend datasets are loaded.")
    return dataset_ids[0]


def _trusted_source_outcome_set_id(outcome_set) -> str:
    payload = "|".join(
        (
            outcome_set.action_id,
            outcome_set.outcome_space_completeness.value,
            *(state.outcome_id for state in sorted(outcome_set.hypothetical_states, key=lambda item: item.outcome_id)),
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"backend-outcome-set:{outcome_set.action_id}:{digest}"


def _bad_request(message: str) -> None:
    raise HTTPException(
        status_code=400,
        detail={
            "code": "VALIDATION_ERROR",
            "message": message,
            "recoverable": True,
            "reliable_no_result": True,
        },
    )


def _dataset_summary_to_dto(summary) -> EmpiricalDatasetSummaryDto | None:
    if summary is None:
        return None
    return EmpiricalDatasetSummaryDto(
        dataset_id=summary.dataset_id,
        action_id=summary.action_id,
        source_outcome_set_id=summary.source_outcome_set_id,
        game=summary.game,
        league=summary.league,
        sample_size=summary.sample_size,
        unclassified_count=summary.unclassified_count,
        outcome_count=summary.outcome_count,
        retrieved_at=summary.retrieved_at,
        synthetic=summary.synthetic,
        item_class=summary.item_class,
        game_version=summary.game_version,
        crafting_dataset_version=summary.crafting_dataset_version,
        modifier_dataset_version=summary.modifier_dataset_version,
        verification_status=summary.verification_status.value,
        methodology=summary.methodology,
        source_uri=summary.source_uri,
        source_type=summary.source_type.value if summary.source_type is not None else None,
        warnings=list(summary.warnings),
    )
