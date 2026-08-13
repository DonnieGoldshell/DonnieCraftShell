"""Manual craft observation recorder routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
from packages.shared.donniecraftshell_contracts.domain import GameContext
from packages.shared.donniecraftshell_contracts.observation_recorder import (
    CraftObservationRecorder,
    OBSERVATION_RECORDER_VERSION,
    ObservationDraft,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item

from services.api.app.dependencies.advisor import get_advisor_orchestrator
from services.api.app.schemas.observations import (
    CraftObservationExportRequestDto,
    CraftObservationExportResponseDto,
    CraftObservationRecordRequestDto,
    CraftObservationRecordResponseDto,
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
    outcome_set = _trusted_outcome_set(request, before.item, orchestrator)

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
            source_outcome_set_id=request.source_outcome_set_id,
            item_class=before.item.item_class or "",
            league=request.league,
            before_item=before.item,
            after_item=after.item,
            observed_at=request.observed_at,
            source_id=request.source_id,
            game=request.game,
            game_version=request.game_version,
            crafting_dataset_version=request.crafting_dataset_version,
            modifier_dataset_version=request.modifier_dataset_version,
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


def _trusted_outcome_set(request: CraftObservationRecordRequestDto, before_item, orchestrator: CraftAdvisorOrchestrator):
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
        request.modifier_dataset_version,
    )


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
