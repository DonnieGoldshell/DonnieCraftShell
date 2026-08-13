"""Manual craft observation recorder API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .common import ApiModel


class OutcomeCandidateDto(ApiModel):
    outcome_id: str
    removed_modifier_raw_text: str | None = None


class CraftObservationRecordRequestDto(ApiModel):
    before_clipboard_text: str
    after_clipboard_text: str
    action_id: str
    source_outcome_set_id: str
    item_class: str = "Quivers"
    league: str
    observed_at: datetime
    source_id: str = "api-manual-craft-observation"
    game: str = "Path of Exile 2"
    game_version: str | None = None
    crafting_dataset_version: str | None = None
    modifier_dataset_version: str | None = None
    source_uri: str | None = None
    synthetic: bool = False
    manual_outcome_id: str | None = None
    manual_reason: str | None = None
    outcome_candidates: list[OutcomeCandidateDto] = Field(default_factory=list)


class ObservationClassificationDto(ApiModel):
    method: str
    outcome_id: str | None = None
    reason: str
    warnings: list[str] = []


class CraftObservationRecordResponseDto(ApiModel):
    raw_record_id: str
    classification: ObservationClassificationDto
    before_item_fingerprint: str
    after_item_fingerprint: str
    export_record: dict
    warnings: list[str] = []


class CraftObservationExportRequestDto(ApiModel):
    observations: list[dict]


class CraftObservationExportResponseDto(ApiModel):
    recorder_version: str
    exported_at: datetime
    observations: list[dict]
    warnings: list[str] = []
