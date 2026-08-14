"""Durable local workspace for recorded craft observations and review state.

The workspace stores raw recorder records and separate review decisions. It does
not curate, aggregate, calculate probabilities, or activate Advisor evidence.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .observation_review import (
    OBSERVATION_REVIEW_VERSION,
    ObservationReviewDecision,
    ObservationReviewStatus,
    review_observation_batches,
)


OBSERVATION_WORKSPACE_VERSION = "dc-observation-workspace-v1"
OBSERVATION_WORKSPACE_STORAGE_VERSION = "dc-observation-workspace-storage-v1"


class ObservationWorkspaceSaveStatus(str, Enum):
    SAVED = "SAVED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    REJECTED = "REJECTED"


class ObservationWorkspaceRestoreMode(str, Enum):
    MERGE = "MERGE"
    REPLACE = "REPLACE"


class ObservationWorkspaceRestoreStatus(str, Enum):
    RESTORED = "RESTORED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ObservationWorkspacePersistenceStatus:
    storage_version: str
    storage_mode: str
    persistence_enabled: bool
    loaded_record_count: int
    loaded_decision_count: int
    skipped_entry_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservationWorkspaceRecordSummary:
    raw_record_id: str
    review_status: ObservationReviewStatus
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
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservationWorkspaceEntry:
    raw_record_id: str
    record: dict[str, Any]
    decision: ObservationReviewDecision
    summary: ObservationWorkspaceRecordSummary


@dataclass(frozen=True)
class ObservationWorkspaceSaveResult:
    status: ObservationWorkspaceSaveStatus
    raw_record_id: str | None = None
    entry: ObservationWorkspaceEntry | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservationWorkspaceRestoreResult:
    status: ObservationWorkspaceRestoreStatus
    mode: ObservationWorkspaceRestoreMode
    records_received: int = 0
    records_imported: int = 0
    records_already_present: int = 0
    records_conflicting: int = 0
    records_invalid: int = 0
    decisions_received: int = 0
    decisions_imported: int = 0
    decisions_invalid: int = 0
    resulting_record_count: int = 0
    resulting_decision_count: int = 0
    warnings: tuple[str, ...] = ()


class ObservationWorkspaceRepository:
    def __init__(
        self,
        records: tuple[dict[str, Any], ...] = (),
        decisions: tuple[ObservationReviewDecision, ...] = (),
    ) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._fingerprints: dict[str, str] = {}
        self._decisions: dict[str, ObservationReviewDecision] = {}
        for record in records:
            result = self.save_record(record)
            if result.status == ObservationWorkspaceSaveStatus.REJECTED:
                raise ValueError("; ".join(result.warnings))
        for decision in decisions:
            self.save_decision(decision)

    def save_record(self, record: dict[str, Any]) -> ObservationWorkspaceSaveResult:
        try:
            copied = _json_payload_copy(record)
            raw_record_id = _raw_record_id(copied)
        except Exception as exc:
            return ObservationWorkspaceSaveResult(
                status=ObservationWorkspaceSaveStatus.REJECTED,
                warnings=(f"Observation workspace record was rejected: {exc}",),
            )
        fingerprint = _record_fingerprint(copied)
        existing = self._records.get(raw_record_id)
        if existing is not None:
            if self._fingerprints[raw_record_id] == fingerprint:
                return ObservationWorkspaceSaveResult(
                    status=ObservationWorkspaceSaveStatus.ALREADY_EXISTS,
                    raw_record_id=raw_record_id,
                    entry=self.get_entry(raw_record_id),
                    warnings=("Identical observation record was already stored.",),
                )
            return ObservationWorkspaceSaveResult(
                status=ObservationWorkspaceSaveStatus.REJECTED,
                raw_record_id=raw_record_id,
                warnings=(f"Conflicting observation content for raw_record_id {raw_record_id} was rejected.",),
            )
        self._records[raw_record_id] = copied
        self._fingerprints[raw_record_id] = fingerprint
        self._decisions.setdefault(raw_record_id, ObservationReviewDecision(raw_record_id=raw_record_id))
        return ObservationWorkspaceSaveResult(
            status=ObservationWorkspaceSaveStatus.SAVED,
            raw_record_id=raw_record_id,
            entry=self.get_entry(raw_record_id),
            warnings=("Stored observation remains pending until explicitly reviewed.",),
        )

    def save_decision(self, decision: ObservationReviewDecision) -> ObservationWorkspaceSaveResult:
        if decision.raw_record_id not in self._records:
            return ObservationWorkspaceSaveResult(
                status=ObservationWorkspaceSaveStatus.REJECTED,
                raw_record_id=decision.raw_record_id,
                warnings=(f"Review decision references unknown raw_record_id {decision.raw_record_id}.",),
            )
        self._decisions[decision.raw_record_id] = decision
        return ObservationWorkspaceSaveResult(
            status=ObservationWorkspaceSaveStatus.SAVED,
            raw_record_id=decision.raw_record_id,
            entry=self.get_entry(decision.raw_record_id),
            warnings=("Review decision was stored separately from the raw observation.",),
        )

    def get_entry(self, raw_record_id: str) -> ObservationWorkspaceEntry | None:
        record = self._records.get(raw_record_id)
        if record is None:
            return None
        decision = self._decisions.get(raw_record_id, ObservationReviewDecision(raw_record_id=raw_record_id))
        copied = deepcopy(record)
        return ObservationWorkspaceEntry(
            raw_record_id=raw_record_id,
            record=copied,
            decision=decision,
            summary=_summary(copied, decision),
        )

    def list_entries(self) -> tuple[ObservationWorkspaceEntry, ...]:
        return tuple(
            entry
            for raw_record_id in sorted(self._records)
            if (entry := self.get_entry(raw_record_id)) is not None
        )

    def review_result(self):
        return review_observation_batches(
            ({"observations": [entry.record for entry in self.list_entries()]},),
            tuple(entry.decision for entry in self.list_entries()),
        )

    def export_backup(self) -> dict[str, Any]:
        return _workspace_envelope(self._records, self._decisions)

    def restore_backup(
        self,
        backup: dict[str, Any],
        mode: ObservationWorkspaceRestoreMode = ObservationWorkspaceRestoreMode.MERGE,
    ) -> ObservationWorkspaceRestoreResult:
        try:
            parsed_mode = ObservationWorkspaceRestoreMode(mode)
        except ValueError:
            return ObservationWorkspaceRestoreResult(
                status=ObservationWorkspaceRestoreStatus.REJECTED,
                mode=ObservationWorkspaceRestoreMode.MERGE,
                resulting_record_count=len(self._records),
                resulting_decision_count=len(self._decisions),
                warnings=(f"Unsupported observation workspace restore mode: {mode}.",),
            )
        validated = _validate_backup(backup)
        if validated.warnings:
            return ObservationWorkspaceRestoreResult(
                status=ObservationWorkspaceRestoreStatus.REJECTED,
                mode=parsed_mode,
                records_received=validated.records_received,
                records_invalid=validated.records_invalid,
                decisions_received=validated.decisions_received,
                decisions_invalid=validated.decisions_invalid,
                resulting_record_count=len(self._records),
                resulting_decision_count=len(self._decisions),
                warnings=validated.warnings,
            )

        target_records: dict[str, dict[str, Any]]
        target_fingerprints: dict[str, str]
        target_decisions: dict[str, ObservationReviewDecision]
        records_imported = 0
        records_already_present = 0
        records_conflicting = 0
        warnings: list[str] = []

        if parsed_mode == ObservationWorkspaceRestoreMode.REPLACE:
            target_records = {}
            target_fingerprints = {}
            target_decisions = {}
        else:
            target_records = deepcopy(self._records)
            target_fingerprints = dict(self._fingerprints)
            target_decisions = dict(self._decisions)

        for raw_record_id, record in validated.records.items():
            fingerprint = _record_fingerprint(record)
            existing = target_records.get(raw_record_id)
            if existing is None:
                target_records[raw_record_id] = deepcopy(record)
                target_fingerprints[raw_record_id] = fingerprint
                records_imported += 1
                continue
            if target_fingerprints[raw_record_id] == fingerprint:
                records_already_present += 1
                continue
            records_conflicting += 1
            warnings.append(f"Conflicting observation content for raw_record_id {raw_record_id} was rejected.")

        if records_conflicting:
            return ObservationWorkspaceRestoreResult(
                status=ObservationWorkspaceRestoreStatus.REJECTED,
                mode=parsed_mode,
                records_received=validated.records_received,
                records_imported=0,
                records_already_present=records_already_present,
                records_conflicting=records_conflicting,
                decisions_received=validated.decisions_received,
                resulting_record_count=len(self._records),
                resulting_decision_count=len(self._decisions),
                warnings=tuple(warnings),
            )

        for raw_record_id in target_records:
            target_decisions.setdefault(raw_record_id, ObservationReviewDecision(raw_record_id=raw_record_id))

        decisions_imported = 0
        for raw_record_id, decision in validated.decisions.items():
            target_decisions[raw_record_id] = decision
            decisions_imported += 1

        self._records = target_records
        self._fingerprints = target_fingerprints
        self._decisions = target_decisions
        return ObservationWorkspaceRestoreResult(
            status=ObservationWorkspaceRestoreStatus.RESTORED,
            mode=parsed_mode,
            records_received=validated.records_received,
            records_imported=records_imported,
            records_already_present=records_already_present,
            records_conflicting=0,
            decisions_received=validated.decisions_received,
            decisions_imported=decisions_imported,
            resulting_record_count=len(self._records),
            resulting_decision_count=len(self._decisions),
            warnings=tuple(warnings),
        )

    def persistence_status(self) -> ObservationWorkspacePersistenceStatus:
        return ObservationWorkspacePersistenceStatus(
            storage_version=OBSERVATION_WORKSPACE_STORAGE_VERSION,
            storage_mode="IN_MEMORY",
            persistence_enabled=False,
            loaded_record_count=len(self._records),
            loaded_decision_count=len(self._decisions),
            warnings=("Observation workspace persistence is disabled; records exist only for this process.",),
        )


class FileBackedObservationWorkspaceRepository(ObservationWorkspaceRepository):
    def __init__(self, storage_path: str | Path) -> None:
        self._storage_path = Path(storage_path)
        self._load_warnings: list[str] = []
        self._skipped_entry_count = 0
        self._loading = True
        records, decisions = self._load()
        super().__init__(records, decisions)
        self._loading = False

    def save_record(self, record: dict[str, Any]) -> ObservationWorkspaceSaveResult:
        before = self._snapshot_state()
        result = super().save_record(record)
        if result.status == ObservationWorkspaceSaveStatus.SAVED and not self._loading:
            try:
                self._persist()
            except Exception as exc:
                self._restore_state(before)
                return ObservationWorkspaceSaveResult(
                    status=ObservationWorkspaceSaveStatus.REJECTED,
                    raw_record_id=result.raw_record_id,
                    warnings=(f"Observation workspace persistence failed; record was not saved: {exc}",),
                )
        return result

    def save_decision(self, decision: ObservationReviewDecision) -> ObservationWorkspaceSaveResult:
        before = self._snapshot_state()
        result = super().save_decision(decision)
        if result.status == ObservationWorkspaceSaveStatus.SAVED and not self._loading:
            try:
                self._persist()
            except Exception as exc:
                self._restore_state(before)
                return ObservationWorkspaceSaveResult(
                    status=ObservationWorkspaceSaveStatus.REJECTED,
                    raw_record_id=decision.raw_record_id,
                    entry=self.get_entry(decision.raw_record_id),
                    warnings=(f"Observation workspace persistence failed; review decision was not saved: {exc}",),
                )
        return result

    def restore_backup(
        self,
        backup: dict[str, Any],
        mode: ObservationWorkspaceRestoreMode = ObservationWorkspaceRestoreMode.MERGE,
    ) -> ObservationWorkspaceRestoreResult:
        before = self._snapshot_state()
        result = super().restore_backup(backup, mode)
        if result.status == ObservationWorkspaceRestoreStatus.RESTORED and not self._loading:
            try:
                self._persist()
            except Exception as exc:
                self._restore_state(before)
                return ObservationWorkspaceRestoreResult(
                    status=ObservationWorkspaceRestoreStatus.REJECTED,
                    mode=result.mode,
                    records_received=result.records_received,
                    records_imported=0,
                    records_already_present=result.records_already_present,
                    records_conflicting=result.records_conflicting,
                    records_invalid=result.records_invalid,
                    decisions_received=result.decisions_received,
                    decisions_imported=0,
                    decisions_invalid=result.decisions_invalid,
                    resulting_record_count=len(self._records),
                    resulting_decision_count=len(self._decisions),
                    warnings=(f"Observation workspace persistence failed; backup restore was not saved: {exc}",),
                )
        return result

    def persistence_status(self) -> ObservationWorkspacePersistenceStatus:
        return ObservationWorkspacePersistenceStatus(
            storage_version=OBSERVATION_WORKSPACE_STORAGE_VERSION,
            storage_mode="FILE",
            persistence_enabled=True,
            loaded_record_count=len(self._records),
            loaded_decision_count=len(self._decisions),
            skipped_entry_count=self._skipped_entry_count,
            warnings=tuple(self._load_warnings),
        )

    def _load(self) -> tuple[tuple[dict[str, Any], ...], tuple[ObservationReviewDecision, ...]]:
        if not self._storage_path.exists():
            return (), ()
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._skip(f"Observation workspace storage could not be read and was skipped: {exc}")
            return (), ()
        if not isinstance(payload, dict):
            self._skip("Observation workspace storage root must be an object; persisted entries were skipped.")
            return (), ()
        if payload.get("workspace_version") != OBSERVATION_WORKSPACE_VERSION:
            self._skip("Observation workspace_version is missing or incompatible; persisted entries were skipped.")
            return (), ()
        if payload.get("storage_version") != OBSERVATION_WORKSPACE_STORAGE_VERSION:
            self._skip("Observation workspace storage_version is missing or incompatible; persisted entries were skipped.")
            return (), ()
        records = payload.get("records", ())
        decisions = payload.get("decisions", ())
        if not isinstance(records, list):
            self._skip("Observation workspace records must be a list; persisted records were skipped.")
            records = []
        if not isinstance(decisions, list):
            self._skip("Observation workspace decisions must be a list; persisted decisions were skipped.")
            decisions = []
        loaded_records: list[dict[str, Any]] = []
        loaded_ids: set[str] = set()
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                self._skip(f"Persisted observation record #{index} is not an object and was skipped.")
                continue
            try:
                raw_record_id = _raw_record_id(record)
            except Exception as exc:
                self._skip(f"Persisted observation record #{index} was skipped: {exc}")
                continue
            if raw_record_id in loaded_ids:
                self._skip(f"Duplicate persisted observation record {raw_record_id} was skipped.")
                continue
            loaded_ids.add(raw_record_id)
            loaded_records.append(_json_payload_copy(record))
        loaded_decisions: list[ObservationReviewDecision] = []
        for index, decision in enumerate(decisions, start=1):
            if not isinstance(decision, dict):
                self._skip(f"Persisted review decision #{index} is not an object and was skipped.")
                continue
            try:
                raw_record_id = str(decision["raw_record_id"])
                if raw_record_id not in loaded_ids:
                    self._skip(f"Persisted review decision for absent raw_record_id {raw_record_id} was skipped.")
                    continue
                loaded_decisions.append(
                    ObservationReviewDecision(
                        raw_record_id=raw_record_id,
                        status=ObservationReviewStatus(decision.get("status", "PENDING")),
                        reviewed_at=_datetime_or_none(decision.get("reviewed_at")),
                        note=decision.get("note"),
                        reviewer_id=decision.get("reviewer_id"),
                    )
                )
            except Exception as exc:
                self._skip(f"Persisted review decision #{index} was skipped: {exc}")
        return tuple(loaded_records), tuple(loaded_decisions)

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _workspace_envelope(self._records, self._decisions)
        encoded = json.dumps(payload, indent=2, sort_keys=True)
        temporary_path = self._storage_path.with_name(f"{self._storage_path.name}.tmp")
        temporary_path.write_text(encoded, encoding="utf-8")
        temporary_path.replace(self._storage_path)

    def _skip(self, warning: str) -> None:
        self._skipped_entry_count += 1
        self._load_warnings.append(warning)

    def _snapshot_state(
        self,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, ObservationReviewDecision]]:
        return (deepcopy(self._records), dict(self._fingerprints), dict(self._decisions))

    def _restore_state(
        self,
        snapshot: tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, ObservationReviewDecision]],
    ) -> None:
        self._records, self._fingerprints, self._decisions = snapshot


def _raw_record_id(record: dict[str, Any]) -> str:
    raw_record_id = record.get("raw_record_id")
    if not isinstance(raw_record_id, str) or not raw_record_id:
        raise ValueError("record requires raw_record_id")
    return raw_record_id


def _record_fingerprint(record: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()


def _json_payload_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, sort_keys=True))


@dataclass(frozen=True)
class _ValidatedBackup:
    records: dict[str, dict[str, Any]]
    decisions: dict[str, ObservationReviewDecision]
    records_received: int
    records_invalid: int
    decisions_received: int
    decisions_invalid: int
    warnings: tuple[str, ...]


def _workspace_envelope(
    records: dict[str, dict[str, Any]],
    decisions: dict[str, ObservationReviewDecision],
) -> dict[str, Any]:
    return {
        "workspace_version": OBSERVATION_WORKSPACE_VERSION,
        "storage_version": OBSERVATION_WORKSPACE_STORAGE_VERSION,
        "records": [deepcopy(records[raw_record_id]) for raw_record_id in sorted(records)],
        "decisions": [
            _decision_to_dict(decisions[raw_record_id])
            for raw_record_id in sorted(decisions)
            if raw_record_id in records
        ],
    }


def _validate_backup(backup: dict[str, Any]) -> _ValidatedBackup:
    warnings: list[str] = []
    if not isinstance(backup, dict):
        return _ValidatedBackup({}, {}, 0, 0, 0, 0, ("Observation workspace backup root must be an object.",))
    if backup.get("workspace_version") != OBSERVATION_WORKSPACE_VERSION:
        warnings.append("Observation workspace backup workspace_version is missing or incompatible.")
    if backup.get("storage_version") != OBSERVATION_WORKSPACE_STORAGE_VERSION:
        warnings.append("Observation workspace backup storage_version is missing or incompatible.")
    records_payload = backup.get("records", ())
    decisions_payload = backup.get("decisions", ())
    if not isinstance(records_payload, list):
        warnings.append("Observation workspace backup records must be a list.")
        records_payload = []
    if not isinstance(decisions_payload, list):
        warnings.append("Observation workspace backup decisions must be a list.")
        decisions_payload = []

    records: dict[str, dict[str, Any]] = {}
    fingerprints: dict[str, str] = {}
    records_invalid = 0
    for index, record in enumerate(records_payload, start=1):
        if not isinstance(record, dict):
            records_invalid += 1
            warnings.append(f"Backup observation record #{index} is not an object.")
            continue
        try:
            copied = _json_payload_copy(record)
            raw_record_id = _raw_record_id(copied)
            fingerprint = _record_fingerprint(copied)
        except Exception as exc:
            records_invalid += 1
            warnings.append(f"Backup observation record #{index} is invalid: {exc}.")
            continue
        if raw_record_id in records:
            records_invalid += 1
            if fingerprints[raw_record_id] == fingerprint:
                warnings.append(f"Duplicate backup observation record {raw_record_id} was rejected.")
            else:
                warnings.append(f"Conflicting duplicate backup observation record {raw_record_id} was rejected.")
            continue
        records[raw_record_id] = copied
        fingerprints[raw_record_id] = fingerprint

    decisions: dict[str, ObservationReviewDecision] = {}
    decisions_invalid = 0
    for index, decision in enumerate(decisions_payload, start=1):
        if not isinstance(decision, dict):
            decisions_invalid += 1
            warnings.append(f"Backup review decision #{index} is not an object.")
            continue
        try:
            raw_record_id = str(decision["raw_record_id"])
            if raw_record_id not in records:
                raise ValueError(f"review decision references absent raw_record_id {raw_record_id}")
            if raw_record_id in decisions:
                raise ValueError(f"duplicate review decision for raw_record_id {raw_record_id}")
            decisions[raw_record_id] = ObservationReviewDecision(
                raw_record_id=raw_record_id,
                status=ObservationReviewStatus(decision.get("status", "PENDING")),
                reviewed_at=_datetime_or_none(decision.get("reviewed_at")),
                note=decision.get("note"),
                reviewer_id=decision.get("reviewer_id"),
            )
        except Exception as exc:
            decisions_invalid += 1
            warnings.append(f"Backup review decision #{index} is invalid: {exc}.")
    return _ValidatedBackup(
        records=records,
        decisions=decisions,
        records_received=len(records_payload),
        records_invalid=records_invalid,
        decisions_received=len(decisions_payload),
        decisions_invalid=decisions_invalid,
        warnings=tuple(warnings),
    )


def _summary(record: dict[str, Any], decision: ObservationReviewDecision) -> ObservationWorkspaceRecordSummary:
    return ObservationWorkspaceRecordSummary(
        raw_record_id=decision.raw_record_id,
        review_status=decision.status,
        action_id=record.get("action_id"),
        source_outcome_set_id=record.get("source_outcome_set_id"),
        outcome_id=record.get("outcome_id"),
        unclassified=bool(record.get("unclassified", False)),
        synthetic=bool(record.get("synthetic", False)),
        observed_at=record.get("observed_at"),
        classification_method=record.get("classification_method"),
        reviewer_id=decision.reviewer_id,
        reviewed_at=decision.reviewed_at,
        note=decision.note,
        warnings=tuple(record.get("warnings", ())),
    )


def _decision_to_dict(decision: ObservationReviewDecision) -> dict[str, Any]:
    return {
        "raw_record_id": decision.raw_record_id,
        "status": decision.status.value,
        "reviewed_at": decision.reviewed_at.isoformat() if decision.reviewed_at else None,
        "note": decision.note,
        "reviewer_id": decision.reviewer_id,
        "review_version": OBSERVATION_REVIEW_VERSION,
    }


def _datetime_or_none(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("reviewed_at must be an ISO datetime string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
