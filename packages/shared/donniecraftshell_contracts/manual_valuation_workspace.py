"""Durable local workspace for manual rare-item valuation evidence.

The workspace stores operator-entered comparable listing observations only. It
does not aggregate valuations, calculate readiness, submit Advisor evidence, or
turn listing prices into realized sale evidence.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any


MANUAL_VALUATION_WORKSPACE_VERSION = "dc-manual-valuation-workspace-v1"
MANUAL_VALUATION_WORKSPACE_STORAGE_VERSION = "dc-manual-valuation-workspace-storage-v1"


class ManualValuationWorkspaceSaveStatus(str, Enum):
    SAVED = "SAVED"
    UPDATED = "UPDATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    DELETED = "DELETED"
    CLEARED = "CLEARED"
    NOT_FOUND = "NOT_FOUND"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ManualValuationWorkspacePersistenceStatus:
    storage_version: str
    storage_mode: str
    persistence_enabled: bool
    loaded_evidence_count: int
    skipped_evidence_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManualValuationWorkspaceResult:
    status: ManualValuationWorkspaceSaveStatus
    evidence_id: str | None = None
    record: dict[str, Any] | None = None
    records: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()


class ManualValuationWorkspaceRepository:
    def __init__(self, records: tuple[dict[str, Any], ...] = ()) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._fingerprints: dict[str, str] = {}
        for record in records:
            result = self.save_record(record)
            if result.status == ManualValuationWorkspaceSaveStatus.REJECTED:
                raise ValueError("; ".join(result.warnings))

    def save_record(self, record: dict[str, Any]) -> ManualValuationWorkspaceResult:
        try:
            copied = _normalized_record(record)
        except Exception as exc:
            return ManualValuationWorkspaceResult(
                status=ManualValuationWorkspaceSaveStatus.REJECTED,
                warnings=(f"Manual valuation evidence was rejected: {exc}",),
            )
        evidence_id = copied["evidence_id"]
        fingerprint = _record_fingerprint(copied)
        existing = self._records.get(evidence_id)
        if existing is not None:
            if self._fingerprints[evidence_id] == fingerprint:
                return ManualValuationWorkspaceResult(
                    status=ManualValuationWorkspaceSaveStatus.ALREADY_EXISTS,
                    evidence_id=evidence_id,
                    record=deepcopy(existing),
                    warnings=("Identical manual valuation evidence was already stored.",),
                )
            return ManualValuationWorkspaceResult(
                status=ManualValuationWorkspaceSaveStatus.REJECTED,
                evidence_id=evidence_id,
                warnings=(f"Conflicting manual valuation evidence for evidence_id {evidence_id} was rejected.",),
            )
        self._records[evidence_id] = copied
        self._fingerprints[evidence_id] = fingerprint
        return ManualValuationWorkspaceResult(
            status=ManualValuationWorkspaceSaveStatus.SAVED,
            evidence_id=evidence_id,
            record=deepcopy(copied),
            warnings=("Stored manual valuation evidence remains inactive until explicitly submitted to Advisor.",),
        )

    def update_record(self, evidence_id: str, record: dict[str, Any]) -> ManualValuationWorkspaceResult:
        try:
            copied = _normalized_record({**record, "evidence_id": evidence_id})
        except Exception as exc:
            return ManualValuationWorkspaceResult(
                status=ManualValuationWorkspaceSaveStatus.REJECTED,
                evidence_id=evidence_id,
                warnings=(f"Manual valuation evidence update was rejected: {exc}",),
            )
        existing = self._records.get(evidence_id)
        if existing is None:
            return ManualValuationWorkspaceResult(
                status=ManualValuationWorkspaceSaveStatus.NOT_FOUND,
                evidence_id=evidence_id,
                warnings=(f"Manual valuation evidence {evidence_id} was not found.",),
            )
        copied["created_at"] = existing.get("created_at", copied["created_at"])
        copied["updated_at"] = _now_iso()
        self._records[evidence_id] = copied
        self._fingerprints[evidence_id] = _record_fingerprint(copied)
        return ManualValuationWorkspaceResult(
            status=ManualValuationWorkspaceSaveStatus.UPDATED,
            evidence_id=evidence_id,
            record=deepcopy(copied),
            warnings=("Updated manual valuation evidence remains inactive until explicitly submitted to Advisor.",),
        )

    def delete_record(self, evidence_id: str) -> ManualValuationWorkspaceResult:
        existing = self._records.pop(evidence_id, None)
        self._fingerprints.pop(evidence_id, None)
        if existing is None:
            return ManualValuationWorkspaceResult(
                status=ManualValuationWorkspaceSaveStatus.NOT_FOUND,
                evidence_id=evidence_id,
                warnings=(f"Manual valuation evidence {evidence_id} was not found.",),
            )
        return ManualValuationWorkspaceResult(
            status=ManualValuationWorkspaceSaveStatus.DELETED,
            evidence_id=evidence_id,
            record=deepcopy(existing),
            warnings=("Deleted persisted manual valuation evidence only; Advisor evidence was not changed.",),
        )

    def clear_subject(self, subject_id: str) -> ManualValuationWorkspaceResult:
        deleted = tuple(
            evidence_id
            for evidence_id, record in self._records.items()
            if record.get("subject_id") == subject_id
        )
        for evidence_id in deleted:
            self._records.pop(evidence_id, None)
            self._fingerprints.pop(evidence_id, None)
        return ManualValuationWorkspaceResult(
            status=ManualValuationWorkspaceSaveStatus.CLEARED,
            records=(),
            warnings=(f"Cleared {len(deleted)} manual valuation evidence records for {subject_id}.",),
        )

    def list_records(self, subject_id: str | None = None) -> tuple[dict[str, Any], ...]:
        return tuple(
            deepcopy(record)
            for record in sorted(self._records.values(), key=lambda item: item["evidence_id"])
            if subject_id is None or record.get("subject_id") == subject_id
        )

    def export_backup(self) -> dict[str, Any]:
        return _workspace_envelope(self._records)

    def persistence_status(self) -> ManualValuationWorkspacePersistenceStatus:
        return ManualValuationWorkspacePersistenceStatus(
            storage_version=MANUAL_VALUATION_WORKSPACE_STORAGE_VERSION,
            storage_mode="IN_MEMORY",
            persistence_enabled=False,
            loaded_evidence_count=len(self._records),
            warnings=("Manual valuation workspace persistence is disabled; evidence exists only for this process.",),
        )


class FileBackedManualValuationWorkspaceRepository(ManualValuationWorkspaceRepository):
    def __init__(self, storage_path: str | Path) -> None:
        self._storage_path = Path(storage_path)
        self._load_warnings: list[str] = []
        self._skipped_evidence_count = 0
        self._loading = True
        records = self._load()
        super().__init__(records)
        self._loading = False

    def save_record(self, record: dict[str, Any]) -> ManualValuationWorkspaceResult:
        before = self._snapshot_state()
        result = super().save_record(record)
        if result.status == ManualValuationWorkspaceSaveStatus.SAVED and not self._loading:
            persisted = self._persist_or_rollback(before, result.evidence_id, "save")
            if persisted is not None:
                return persisted
        return result

    def update_record(self, evidence_id: str, record: dict[str, Any]) -> ManualValuationWorkspaceResult:
        before = self._snapshot_state()
        result = super().update_record(evidence_id, record)
        if result.status == ManualValuationWorkspaceSaveStatus.UPDATED and not self._loading:
            persisted = self._persist_or_rollback(before, evidence_id, "update")
            if persisted is not None:
                return persisted
        return result

    def delete_record(self, evidence_id: str) -> ManualValuationWorkspaceResult:
        before = self._snapshot_state()
        result = super().delete_record(evidence_id)
        if result.status == ManualValuationWorkspaceSaveStatus.DELETED and not self._loading:
            persisted = self._persist_or_rollback(before, evidence_id, "delete")
            if persisted is not None:
                return persisted
        return result

    def clear_subject(self, subject_id: str) -> ManualValuationWorkspaceResult:
        before = self._snapshot_state()
        result = super().clear_subject(subject_id)
        if result.status == ManualValuationWorkspaceSaveStatus.CLEARED and not self._loading:
            persisted = self._persist_or_rollback(before, None, "clear")
            if persisted is not None:
                return persisted
        return result

    def persistence_status(self) -> ManualValuationWorkspacePersistenceStatus:
        return ManualValuationWorkspacePersistenceStatus(
            storage_version=MANUAL_VALUATION_WORKSPACE_STORAGE_VERSION,
            storage_mode="FILE",
            persistence_enabled=True,
            loaded_evidence_count=len(self._records),
            skipped_evidence_count=self._skipped_evidence_count,
            warnings=tuple(self._load_warnings),
        )

    def _load(self) -> tuple[dict[str, Any], ...]:
        if not self._storage_path.exists():
            return ()
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._skip(f"Manual valuation workspace storage could not be read and was skipped: {exc}")
            return ()
        if not isinstance(payload, dict):
            self._skip("Manual valuation workspace storage root must be an object; persisted evidence was skipped.")
            return ()
        if payload.get("workspace_version") != MANUAL_VALUATION_WORKSPACE_VERSION:
            self._skip("Manual valuation workspace_version is missing or incompatible; persisted evidence was skipped.")
            return ()
        if payload.get("storage_version") != MANUAL_VALUATION_WORKSPACE_STORAGE_VERSION:
            self._skip("Manual valuation workspace storage_version is missing or incompatible; persisted evidence was skipped.")
            return ()
        records = payload.get("records", ())
        if not isinstance(records, list):
            self._skip("Manual valuation workspace records must be a list; persisted evidence was skipped.")
            return ()
        loaded: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                self._skip(f"Persisted manual valuation evidence #{index} is not an object and was skipped.")
                continue
            try:
                copied = _normalized_record(record)
                evidence_id = copied["evidence_id"]
            except Exception as exc:
                self._skip(f"Persisted manual valuation evidence #{index} was skipped: {exc}")
                continue
            if evidence_id in seen:
                self._skip(f"Duplicate persisted manual valuation evidence {evidence_id} was skipped.")
                continue
            seen.add(evidence_id)
            loaded.append(copied)
        return tuple(loaded)

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(_workspace_envelope(self._records), indent=2, sort_keys=True)
        temporary_path = self._storage_path.with_name(f"{self._storage_path.name}.tmp")
        temporary_path.write_text(encoded, encoding="utf-8")
        temporary_path.replace(self._storage_path)

    def _persist_or_rollback(
        self,
        before: tuple[dict[str, dict[str, Any]], dict[str, str]],
        evidence_id: str | None,
        operation: str,
    ) -> ManualValuationWorkspaceResult | None:
        try:
            self._persist()
            return None
        except Exception as exc:
            self._restore_state(before)
            return ManualValuationWorkspaceResult(
                status=ManualValuationWorkspaceSaveStatus.REJECTED,
                evidence_id=evidence_id,
                warnings=(f"Manual valuation workspace persistence failed; {operation} was not saved: {exc}",),
            )

    def _skip(self, warning: str) -> None:
        self._skipped_evidence_count += 1
        self._load_warnings.append(warning)

    def _snapshot_state(self) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        return deepcopy(self._records), dict(self._fingerprints)

    def _restore_state(self, snapshot: tuple[dict[str, dict[str, Any]], dict[str, str]]) -> None:
        self._records, self._fingerprints = snapshot


def canonical_manual_valuation_subject_id(subject_type: str, outcome_id: str | None = None) -> str:
    if subject_type == "CURRENT_ITEM":
        if outcome_id is not None:
            raise ValueError("current-item valuation evidence must not include outcome_id")
        return "current"
    if subject_type == "HYPOTHETICAL_OUTCOME":
        if not outcome_id:
            raise ValueError("hypothetical-outcome valuation evidence requires outcome_id")
        return f"outcome:{outcome_id}"
    raise ValueError("subject_type must be CURRENT_ITEM or HYPOTHETICAL_OUTCOME")


def _normalized_record(record: dict[str, Any]) -> dict[str, Any]:
    copied = _json_payload_copy(record)
    subject_type = str(copied.get("subject_type", ""))
    outcome_id = copied.get("outcome_id")
    subject_id = str(copied.get("subject_id", ""))
    canonical_subject_id = canonical_manual_valuation_subject_id(subject_type, outcome_id)
    if subject_id != canonical_subject_id:
        raise ValueError(f"subject_id must be {canonical_subject_id}")
    if not copied.get("league"):
        raise ValueError("league is required")
    if not copied.get("strategy"):
        raise ValueError("comparable strategy is required")
    amount = Decimal(str(copied.get("amount", "")))
    if amount < 0:
        raise ValueError("listing amount cannot be negative")
    if not copied.get("currency_asset_id"):
        raise ValueError("currency_asset_id is required")
    copied["amount"] = str(amount)
    copied["outcome_id"] = outcome_id
    copied["observed_at"] = _iso_or_none(copied.get("observed_at")) or _now_iso()
    now = _now_iso()
    copied.setdefault("created_at", now)
    copied.setdefault("updated_at", copied["created_at"])
    copied["evidence_id"] = str(copied.get("evidence_id") or _derive_evidence_id(copied))
    return copied


def _derive_evidence_id(record: dict[str, Any]) -> str:
    identity = record.get("external_listing_id") or "|".join(
        (
            str(record.get("amount")),
            str(record.get("currency_asset_id")),
            str(record.get("observed_at")),
            str(record.get("item_summary") or ""),
            str(record.get("notes") or ""),
        )
    )
    digest = hashlib.sha256(
        "|".join(
            (
                record["subject_id"],
                str(record.get("league")),
                str(record.get("strategy")),
                str(identity),
            )
        ).encode("utf-8")
    ).hexdigest()[:24]
    return f"manual-valuation-evidence:{digest}"


def _record_fingerprint(record: dict[str, Any]) -> str:
    content = {
        key: value
        for key, value in record.items()
        if key not in {"created_at", "updated_at"}
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()


def _workspace_envelope(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "workspace_version": MANUAL_VALUATION_WORKSPACE_VERSION,
        "storage_version": MANUAL_VALUATION_WORKSPACE_STORAGE_VERSION,
        "records": [deepcopy(records[evidence_id]) for evidence_id in sorted(records)],
    }


def _json_payload_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, sort_keys=True, default=str))


def _iso_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO datetime string")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
