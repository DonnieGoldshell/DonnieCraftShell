"""Review and curation workflow for recorded craft observations.

The review layer sits between recorder exports and empirical probability
imports. It does not calculate probabilities and it never mutates raw
observation records.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable


OBSERVATION_REVIEW_VERSION = "dc-observation-review-v1"


class ObservationReviewStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ObservationReviewDecision:
    raw_record_id: str
    status: ObservationReviewStatus = ObservationReviewStatus.PENDING
    reviewed_at: datetime | None = None
    note: str | None = None
    reviewer_id: str | None = None

    def __post_init__(self) -> None:
        if not self.raw_record_id:
            raise ValueError("review decision requires raw_record_id")
        if self.reviewed_at is not None and self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")


@dataclass(frozen=True)
class CuratedObservationRecord:
    raw_record_id: str
    original_record: dict[str, Any]
    decision: ObservationReviewDecision
    duplicate: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def accepted_for_export(self) -> bool:
        return self.decision.status == ObservationReviewStatus.ACCEPTED and not self.duplicate


@dataclass(frozen=True)
class ObservationReviewManifest:
    review_version: str
    generated_at: datetime
    records: tuple[CuratedObservationRecord, ...]
    warnings: tuple[str, ...] = ()

    @property
    def accepted_count(self) -> int:
        return sum(1 for record in self.records if record.decision.status == ObservationReviewStatus.ACCEPTED)

    @property
    def exported_accepted_count(self) -> int:
        return sum(1 for record in self.records if record.accepted_for_export)

    @property
    def rejected_count(self) -> int:
        return sum(1 for record in self.records if record.decision.status == ObservationReviewStatus.REJECTED)

    @property
    def pending_count(self) -> int:
        return sum(1 for record in self.records if record.decision.status == ObservationReviewStatus.PENDING)

    @property
    def duplicate_count(self) -> int:
        return sum(1 for record in self.records if record.duplicate)

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_version": self.review_version,
            "generated_at": self.generated_at.isoformat(),
            "accepted_count": self.accepted_count,
            "exported_accepted_count": self.exported_accepted_count,
            "rejected_count": self.rejected_count,
            "pending_count": self.pending_count,
            "duplicate_count": self.duplicate_count,
            "warnings": list(self.warnings),
            "records": [_manifest_record(record) for record in self.records],
        }


@dataclass(frozen=True)
class ObservationCurationResult:
    records: tuple[CuratedObservationRecord, ...]
    accepted_export: dict[str, Any]
    manifest: ObservationReviewManifest
    warnings: tuple[str, ...] = ()


def review_observation_batches(
    batch_payloads: Iterable[dict[str, Any]],
    decisions: Iterable[ObservationReviewDecision] = (),
    reviewed_at: datetime | None = None,
) -> ObservationCurationResult:
    """Apply explicit review decisions to one or more recorder export batches."""

    reviewed_at = reviewed_at or datetime.now(timezone.utc)
    decision_by_id = {decision.raw_record_id: _with_reviewed_at(decision, reviewed_at) for decision in decisions}
    raw_records = tuple(_records_from_payload(payload) for payload in batch_payloads)
    records = [record for batch in raw_records for record in batch]
    seen_ids: set[str] = set()
    curated: list[CuratedObservationRecord] = []
    warnings: list[str] = []

    for index, record in enumerate(records, start=1):
        raw_record_id = str(record.get("raw_record_id", ""))
        record_warnings = list(_record_warnings(record, index))
        duplicate = False
        if raw_record_id:
            duplicate = raw_record_id in seen_ids
            if duplicate:
                record_warnings.append(f"Duplicate raw_record_id {raw_record_id} is retained in the manifest but excluded from accepted export.")
                warnings.append(f"Duplicate raw_record_id {raw_record_id} detected.")
            seen_ids.add(raw_record_id)
        decision = decision_by_id.get(
            raw_record_id,
            ObservationReviewDecision(raw_record_id=raw_record_id or f"missing-raw-record-id:{index}"),
        )
        curated.append(
            CuratedObservationRecord(
                raw_record_id=raw_record_id,
                original_record=deepcopy(record),
                decision=decision,
                duplicate=duplicate,
                warnings=tuple(record_warnings),
            )
        )

    accepted_records = tuple(record for record in curated if record.accepted_for_export)
    warnings.extend(_context_warnings(accepted_records))
    accepted_export = {
        "review_version": OBSERVATION_REVIEW_VERSION,
        "exported_at": reviewed_at.isoformat(),
        "observations": [deepcopy(record.original_record) for record in accepted_records],
        "warnings": list(dict.fromkeys(warnings)),
    }
    manifest = ObservationReviewManifest(
        review_version=OBSERVATION_REVIEW_VERSION,
        generated_at=reviewed_at,
        records=tuple(curated),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    return ObservationCurationResult(
        records=tuple(curated),
        accepted_export=accepted_export,
        manifest=manifest,
        warnings=manifest.warnings,
    )


def _records_from_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    data: Any = payload.get("observations", payload)
    if isinstance(data, dict):
        data = data.get("observations", ())
    if not isinstance(data, list):
        raise ValueError("observation review payload must contain observations as a list")
    return tuple(deepcopy(record) for record in data if isinstance(record, dict))


def _record_warnings(record: dict[str, Any], index: int) -> tuple[str, ...]:
    warnings: list[str] = []
    if not record.get("raw_record_id"):
        warnings.append(f"Record {index} is missing raw_record_id.")
    if record.get("classification_method") == "AUTOMATIC":
        warnings.append("Automatic classification still requires human acceptance before empirical import.")
    if record.get("classification_method") == "MANUAL":
        warnings.append("Manual classification remains manual evidence after curation.")
    if record.get("unclassified"):
        warnings.append("Accepted unclassified observations remain unclassified and do not become outcome counts.")
    if record.get("synthetic"):
        warnings.append("Synthetic/test-only observation must not be mixed into non-synthetic evidence without explicit review.")
    return tuple(warnings)


def _context_warnings(records: Iterable[CuratedObservationRecord]) -> tuple[str, ...]:
    accepted = tuple(records)
    warnings: list[str] = []
    synthetic_values = {bool(record.original_record.get("synthetic", False)) for record in accepted}
    if len(synthetic_values) > 1:
        warnings.append("Accepted export mixes synthetic and non-synthetic observations; import must keep these evidence contexts separate.")
    for field_name in (
        "action_id",
        "source_outcome_set_id",
        "game",
        "league",
        "item_class",
        "game_version",
        "crafting_dataset_version",
        "modifier_dataset_version",
    ):
        values = {record.original_record.get(field_name) for record in accepted if record.original_record.get(field_name) is not None}
        if len(values) > 1:
            warnings.append(f"Accepted export contains multiple {field_name} values: {', '.join(sorted(str(value) for value in values))}.")
    return tuple(warnings)


def _with_reviewed_at(decision: ObservationReviewDecision, reviewed_at: datetime) -> ObservationReviewDecision:
    if decision.status == ObservationReviewStatus.PENDING or decision.reviewed_at is not None:
        return decision
    return ObservationReviewDecision(
        raw_record_id=decision.raw_record_id,
        status=decision.status,
        reviewed_at=reviewed_at,
        note=decision.note,
        reviewer_id=decision.reviewer_id,
    )


def _manifest_record(record: CuratedObservationRecord) -> dict[str, Any]:
    original = record.original_record
    return {
        "raw_record_id": record.raw_record_id,
        "status": record.decision.status.value,
        "reviewed_at": record.decision.reviewed_at.isoformat() if record.decision.reviewed_at else None,
        "reviewer_id": record.decision.reviewer_id,
        "note": record.decision.note,
        "duplicate": record.duplicate,
        "exported": record.accepted_for_export,
        "classification_method": original.get("classification_method"),
        "outcome_id": original.get("outcome_id"),
        "unclassified": bool(original.get("unclassified", False)),
        "synthetic": bool(original.get("synthetic", False)),
        "action_id": original.get("action_id"),
        "source_outcome_set_id": original.get("source_outcome_set_id"),
        "source_id": original.get("source_id"),
        "source_type": original.get("source_type"),
        "source_uri": original.get("source_uri"),
        "observed_at": original.get("observed_at"),
        "crafting_dataset_version": original.get("crafting_dataset_version"),
        "modifier_dataset_version": original.get("modifier_dataset_version"),
        "before_item_fingerprint": original.get("before_item_fingerprint"),
        "after_item_fingerprint": original.get("after_item_fingerprint"),
        "warnings": list(record.warnings),
    }
