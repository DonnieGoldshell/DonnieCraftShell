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


class ObservationReviewDecisionDto(ApiModel):
    raw_record_id: str
    status: str = "PENDING"
    reviewed_at: datetime | None = None
    note: str | None = None
    reviewer_id: str | None = None


class ObservationReviewRequestDto(ApiModel):
    batches: list[dict] = Field(default_factory=list)
    observations: list[dict] = Field(default_factory=list)
    decisions: list[ObservationReviewDecisionDto] = Field(default_factory=list)


class ObservationReviewRecordDto(ApiModel):
    raw_record_id: str
    status: str
    duplicate: bool
    valid_for_import: bool
    exported: bool
    classification_method: str | None = None
    outcome_id: str | None = None
    unclassified: bool = False
    synthetic: bool = False
    action_id: str | None = None
    source_outcome_set_id: str | None = None
    warnings: list[str] = []


class ObservationReviewResponseDto(ApiModel):
    review_version: str
    records: list[ObservationReviewRecordDto]
    accepted_export: dict
    review_manifest: dict
    warnings: list[str] = []


class ObservationWorkspacePersistenceStatusDto(ApiModel):
    storage_version: str
    storage_mode: str
    persistence_enabled: bool
    loaded_record_count: int
    loaded_decision_count: int
    skipped_entry_count: int = 0
    warnings: list[str] = []


class ObservationWorkspaceRecordSummaryDto(ApiModel):
    raw_record_id: str
    review_status: str
    action_id: str | None = None
    source_outcome_set_id: str | None = None
    outcome_id: str | None = None
    unclassified: bool = False
    synthetic: bool = False
    observed_at: str | None = None
    classification_method: str | None = None
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None
    note: str | None = None
    warnings: list[str] = []


class ObservationWorkspaceEntryDto(ApiModel):
    raw_record_id: str
    record: dict
    decision: ObservationReviewDecisionDto
    summary: ObservationWorkspaceRecordSummaryDto


class ObservationWorkspaceSaveRequestDto(ApiModel):
    record: dict


class ObservationWorkspaceSaveResponseDto(ApiModel):
    workspace_version: str
    status: str
    raw_record_id: str | None = None
    entry: ObservationWorkspaceEntryDto | None = None
    persistence: ObservationWorkspacePersistenceStatusDto
    warnings: list[str] = []


class ObservationWorkspaceListResponseDto(ApiModel):
    workspace_version: str
    entries: list[ObservationWorkspaceEntryDto]
    persistence: ObservationWorkspacePersistenceStatusDto
    warnings: list[str] = []


class ObservationWorkspaceReviewRequestDto(ApiModel):
    decisions: list[ObservationReviewDecisionDto]


class ObservationWorkspaceReviewResponseDto(ApiModel):
    workspace_version: str
    entries: list[ObservationWorkspaceEntryDto]
    review: ObservationReviewResponseDto
    persistence: ObservationWorkspacePersistenceStatusDto
    warnings: list[str] = []


class ObservationWorkspaceAcceptedExportResponseDto(ApiModel):
    workspace_version: str
    review: ObservationReviewResponseDto
    accepted_export: dict
    persistence: ObservationWorkspacePersistenceStatusDto
    warnings: list[str] = []


class ObservationWorkspaceBackupResponseDto(ApiModel):
    workspace_version: str
    backup: dict
    persistence: ObservationWorkspacePersistenceStatusDto
    warnings: list[str] = []


class ObservationWorkspaceRestoreRequestDto(ApiModel):
    backup: dict
    mode: str = "MERGE"


class ObservationWorkspaceRestoreSummaryDto(ApiModel):
    status: str
    mode: str
    records_received: int
    records_imported: int
    records_already_present: int
    records_conflicting: int
    records_invalid: int
    decisions_received: int
    decisions_imported: int
    decisions_invalid: int
    resulting_record_count: int
    resulting_decision_count: int
    warnings: list[str] = []


class ObservationWorkspaceRestoreResponseDto(ApiModel):
    workspace_version: str
    restore: ObservationWorkspaceRestoreSummaryDto
    entries: list[ObservationWorkspaceEntryDto]
    persistence: ObservationWorkspacePersistenceStatusDto
    warnings: list[str] = []


class CuratedObservationBuildRequestDto(ApiModel):
    accepted_export: dict
    dataset_id_prefix: str = "empirical-probability"


class CuratedObservationRejectedRecordDto(ApiModel):
    raw_record_id: str | None = None
    reason: str


class CuratedObservationBuildResponseDto(ApiModel):
    build_version: str
    built_at: datetime
    source_record_count: int
    imported_record_count: int
    accepted_record_count: int
    duplicate_record_count: int
    unclassified_record_count: int
    invalid_record_count: int
    dataset_count: int
    dataset_ids: list[str]
    datasets: list[dict]
    rejected_records: list[CuratedObservationRejectedRecordDto] = []
    warnings: list[str] = []


class EmpiricalDatasetSummaryDto(ApiModel):
    dataset_id: str
    action_id: str
    source_outcome_set_id: str
    game: str
    league: str
    sample_size: int
    unclassified_count: int
    outcome_count: int
    retrieved_at: datetime
    synthetic: bool
    item_class: str | None = None
    game_version: str | None = None
    crafting_dataset_version: str | None = None
    modifier_dataset_version: str | None = None
    verification_status: str
    methodology: str
    source_uri: str | None = None
    source_type: str | None = None
    warnings: list[str] = []


class EmpiricalDatasetRegisterRequestDto(ApiModel):
    dataset: dict


class EmpiricalRegistryPersistenceStatusDto(ApiModel):
    storage_version: str
    storage_mode: str
    persistence_enabled: bool
    loaded_dataset_count: int
    skipped_dataset_count: int = 0
    warnings: list[str] = []


class EmpiricalDatasetRegisterResponseDto(ApiModel):
    registry_version: str
    status: str
    dataset_id: str | None = None
    dataset: EmpiricalDatasetSummaryDto | None = None
    persistence: EmpiricalRegistryPersistenceStatusDto
    warnings: list[str] = []


class EmpiricalDatasetListResponseDto(ApiModel):
    registry_version: str
    datasets: list[EmpiricalDatasetSummaryDto]
    persistence: EmpiricalRegistryPersistenceStatusDto
    warnings: list[str] = []
