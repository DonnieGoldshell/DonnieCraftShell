"""Manual craft observation recorder routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from packages.shared.donniecraftshell_contracts.craft_outcomes import (
    CraftOutcomeOperation,
    CraftOutcomeSet,
    HypotheticalItemState,
    ItemStateDelta,
    OutcomeProbabilityStatus,
    OutcomeSpaceCompleteness,
)
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftApplicabilityStatus
from packages.shared.donniecraftshell_contracts.domain import (
    AffixType,
    GameContext,
    ItemModifier,
    ModifierOrigin,
)
from packages.shared.donniecraftshell_contracts.observation_recorder import (
    CraftObservationRecorder,
    OBSERVATION_RECORDER_VERSION,
    ObservationDraft,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item

from services.api.app.schemas.observations import (
    CraftObservationExportRequestDto,
    CraftObservationExportResponseDto,
    CraftObservationRecordRequestDto,
    CraftObservationRecordResponseDto,
    ObservationClassificationDto,
)


router = APIRouter(prefix="/api/v1/observations", tags=["observations"])


@router.post("/record", response_model=CraftObservationRecordResponseDto)
def record_observation(request: CraftObservationRecordRequestDto) -> CraftObservationRecordResponseDto:
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

    recorder = CraftObservationRecorder()
    outcome_set = _outcome_set_from_request(request)
    if request.manual_outcome_id or request.manual_reason:
        classification = recorder.classify_manually(
            request.manual_outcome_id,
            tuple(candidate.outcome_id for candidate in request.outcome_candidates),
            request.manual_reason or "",
        )
    else:
        classification = recorder.classify_automatically(before.item, after.item, outcome_set)

    recorded = recorder.record(
        ObservationDraft(
            action_id=request.action_id,
            source_outcome_set_id=request.source_outcome_set_id,
            item_class=request.item_class,
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


def _outcome_set_from_request(request: CraftObservationRecordRequestDto) -> CraftOutcomeSet:
    states = tuple(
        HypotheticalItemState(
            outcome_id=candidate.outcome_id,
            source_item_analysis_id=request.source_outcome_set_id.split(":", 1)[0],
            action_id=request.action_id,
            deltas=(
                ItemStateDelta(
                    operation=CraftOutcomeOperation.REMOVE_MODIFIER,
                    removed_modifier=ItemModifier(
                        raw_text=candidate.removed_modifier_raw_text,
                        affix_type=AffixType.UNKNOWN,
                        origin=ModifierOrigin.NATURAL,
                    ),
                ),
            )
            if candidate.removed_modifier_raw_text
            else (),
        )
        for candidate in request.outcome_candidates
    )
    return CraftOutcomeSet(
        action_id=request.action_id,
        source_item_analysis_id=request.source_outcome_set_id.split(":", 1)[0],
        applicability_status=CraftApplicabilityStatus.APPLICABLE,
        outcome_definition=None,
        hypothetical_states=states,
        outcome_space_completeness=OutcomeSpaceCompleteness.PARTIAL,
        probability_completeness=OutcomeProbabilityStatus.UNKNOWN,
    )
