"""Offline import workflow for empirical crafting observations."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .domain import SourceType, VerificationStatus
from .empirical_probability import RawEmpiricalProbabilityDataset, raw_empirical_probability_dataset_from_dict


EMPIRICAL_OBSERVATION_IMPORT_VERSION = "dc-empirical-observation-import-v1"


@dataclass(frozen=True)
class EmpiricalCraftingObservation:
    raw_record_id: str
    action_id: str
    source_outcome_set_id: str
    item_class: str
    league: str
    observed_at: datetime
    source_id: str
    source_type: SourceType
    outcome_id: str | None = None
    unclassified: bool = False
    game: str = "Path of Exile 2"
    game_version: str | None = None
    crafting_dataset_version: str | None = None
    modifier_dataset_version: str | None = None
    source_uri: str | None = None
    synthetic: bool = False
    notes: str | None = None
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION

    def __post_init__(self) -> None:
        required = {
            "raw_record_id": self.raw_record_id,
            "action_id": self.action_id,
            "source_outcome_set_id": self.source_outcome_set_id,
            "item_class": self.item_class,
            "league": self.league,
            "game": self.game,
            "source_id": self.source_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"observation missing required fields: {', '.join(missing)}")
        if self.unclassified and self.outcome_id:
            raise ValueError("unclassified observation must not include outcome_id")
        if not self.unclassified and not self.outcome_id:
            raise ValueError("classified observation requires outcome_id")


@dataclass(frozen=True)
class ObservationValidationIssue:
    raw_record_id: str | None
    reason: str


@dataclass(frozen=True)
class ObservationImportBatch:
    observations: tuple[EmpiricalCraftingObservation, ...]
    rejected_records: tuple[ObservationValidationIssue, ...] = ()
    source_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmpiricalObservationAggregationResult:
    datasets: tuple[RawEmpiricalProbabilityDataset, ...]
    accepted_record_count: int
    duplicate_record_count: int
    unclassified_record_count: int
    rejected_records: tuple[ObservationValidationIssue, ...]
    warnings: tuple[str, ...] = ()


def load_empirical_observation_files(paths: tuple[str | Path, ...]) -> ObservationImportBatch:
    observations: list[EmpiricalCraftingObservation] = []
    rejected: list[ObservationValidationIssue] = []
    for path in paths:
        current = Path(path)
        records = _read_records(current)
        for index, record in enumerate(records, start=1):
            try:
                observations.append(empirical_observation_from_dict(record))
            except Exception as exc:
                rejected.append(
                    ObservationValidationIssue(
                        raw_record_id=str(record.get("raw_record_id")) if isinstance(record, dict) else None,
                        reason=f"{current}:{index}: {exc}",
                    )
                )
    return ObservationImportBatch(
        observations=tuple(observations),
        rejected_records=tuple(rejected),
        source_paths=tuple(str(Path(path)) for path in paths),
    )


def empirical_observation_from_dict(data: dict[str, Any]) -> EmpiricalCraftingObservation:
    return EmpiricalCraftingObservation(
        raw_record_id=str(data.get("raw_record_id", "")),
        action_id=str(data.get("action_id", "")),
        source_outcome_set_id=str(data.get("source_outcome_set_id", "")),
        item_class=str(data.get("item_class", "")),
        league=str(data.get("league", "")),
        observed_at=_datetime(str(data["observed_at"])) if data.get("observed_at") else _missing_datetime(),
        source_id=str(data.get("source_id", "")),
        source_type=SourceType(data.get("source_type", SourceType.MANUAL_RESEARCH.value)),
        outcome_id=(str(data["outcome_id"]) if data.get("outcome_id") else None),
        unclassified=_bool(data.get("unclassified", False)),
        game=str(data.get("game", "Path of Exile 2")),
        game_version=data.get("game_version") or None,
        crafting_dataset_version=data.get("crafting_dataset_version") or None,
        modifier_dataset_version=data.get("modifier_dataset_version") or None,
        source_uri=data.get("source_uri") or None,
        synthetic=_bool(data.get("synthetic", False)),
        notes=data.get("notes") or None,
        verification_status=VerificationStatus(data.get("verification_status", VerificationStatus.NEEDS_VERIFICATION.value)),
    )


def aggregate_observations(
    batch: ObservationImportBatch,
    retrieved_at: datetime | None = None,
    dataset_id_prefix: str = "empirical-probability",
) -> EmpiricalObservationAggregationResult:
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    seen_ids: set[str] = set()
    duplicate_count = 0
    accepted: list[EmpiricalCraftingObservation] = []
    warnings = list(_context_warnings(batch.observations))
    for observation in batch.observations:
        if observation.raw_record_id in seen_ids:
            duplicate_count += 1
            warnings.append(f"Duplicate raw_record_id {observation.raw_record_id} ignored.")
            continue
        seen_ids.add(observation.raw_record_id)
        accepted.append(observation)

    groups: dict[tuple[Any, ...], list[EmpiricalCraftingObservation]] = {}
    for observation in accepted:
        groups.setdefault(_context_key(observation), []).append(observation)

    datasets = tuple(
        _dataset_from_group(records, retrieved_at, dataset_id_prefix)
        for _, records in sorted(groups.items(), key=lambda item: _dataset_id_for_context(item[0], dataset_id_prefix))
    )
    return EmpiricalObservationAggregationResult(
        datasets=datasets,
        accepted_record_count=len(accepted),
        duplicate_record_count=duplicate_count,
        unclassified_record_count=sum(1 for item in accepted if item.unclassified),
        rejected_records=batch.rejected_records,
        warnings=tuple(warnings),
    )


def raw_empirical_probability_dataset_to_dict(dataset: RawEmpiricalProbabilityDataset) -> dict[str, Any]:
    return {
        "dataset_id": dataset.dataset_id,
        "action_id": dataset.action_id,
        "source_outcome_set_id": dataset.source_outcome_set_id,
        "game": dataset.game,
        "league": dataset.league,
        "item_class": dataset.item_class,
        "game_version": dataset.game_version,
        "crafting_dataset_version": dataset.crafting_dataset_version,
        "modifier_dataset_version": dataset.modifier_dataset_version,
        "retrieved_at": dataset.retrieved_at.isoformat(),
        "source_uri": dataset.source_uri,
        "source_type": dataset.source_type.value,
        "synthetic": dataset.synthetic,
        "verification_status": dataset.verification_status.value,
        "methodology": dataset.methodology,
        "notes": dataset.notes,
        "warnings": list(dataset.warnings),
        "unclassified_count": dataset.unclassified_count,
        "observations": [
            {
                "outcome_id": observation.outcome_id,
                "observed_count": observation.observed_count,
                "raw_record_ids": list(observation.raw_record_ids),
                "warnings": list(observation.warnings),
            }
            for observation in dataset.observations
        ],
    }


def write_aggregated_empirical_dataset(
    dataset: RawEmpiricalProbabilityDataset,
    output_path: str | Path,
    overwrite: bool = False,
) -> Path:
    path = Path(output_path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing empirical dataset: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(raw_empirical_probability_dataset_to_dict(dataset), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _dataset_from_group(
    records: list[EmpiricalCraftingObservation],
    retrieved_at: datetime,
    dataset_id_prefix: str,
) -> RawEmpiricalProbabilityDataset:
    first = records[0]
    counts: dict[str, list[str]] = {}
    unclassified_count = 0
    source_ids = sorted({record.source_id for record in records})
    source_uris = sorted({record.source_uri for record in records if record.source_uri})
    warnings: list[str] = []
    if any(record.game_version is None for record in records):
        warnings.append("Some observations have unknown game_version; readiness should remain conservative.")
    if any(record.crafting_dataset_version is None for record in records):
        warnings.append("Some observations have unknown crafting_dataset_version.")
    if any(record.modifier_dataset_version is None for record in records):
        warnings.append("Some observations have unknown modifier_dataset_version.")
    for record in records:
        if record.unclassified:
            unclassified_count += 1
        else:
            assert record.outcome_id is not None
            counts.setdefault(record.outcome_id, []).append(record.raw_record_id)

    observations = [
        {
            "outcome_id": outcome_id,
            "observed_count": len(raw_ids),
            "raw_record_ids": sorted(raw_ids),
        }
        for outcome_id, raw_ids in sorted(counts.items())
    ]
    payload = {
        "dataset_id": _dataset_id_for_context(_context_key(first), dataset_id_prefix),
        "action_id": first.action_id,
        "source_outcome_set_id": first.source_outcome_set_id,
        "game": first.game,
        "league": first.league,
        "item_class": first.item_class,
        "game_version": first.game_version,
        "crafting_dataset_version": first.crafting_dataset_version,
        "modifier_dataset_version": first.modifier_dataset_version,
        "retrieved_at": retrieved_at.isoformat(),
        "source_uri": source_uris[0] if len(source_uris) == 1 else None,
        "source_type": first.source_type.value,
        "synthetic": first.synthetic,
        "verification_status": first.verification_status.value,
        "methodology": f"{EMPIRICAL_OBSERVATION_IMPORT_VERSION}: aggregated raw crafting observations",
        "notes": f"Aggregated from source ids: {', '.join(source_ids)}",
        "warnings": warnings,
        "unclassified_count": unclassified_count,
        "observations": observations,
    }
    return raw_empirical_probability_dataset_from_dict(payload)


def _read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "observations" in data:
            data = data["observations"]
        if not isinstance(data, list):
            raise ValueError("JSON observation file must contain a list or {observations: [...]}")
        return [dict(record) for record in data]
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return [dict(record) for record in csv.DictReader(handle)]
    raise ValueError(f"Unsupported observation file extension: {path.suffix}")


def _context_key(observation: EmpiricalCraftingObservation) -> tuple[Any, ...]:
    return (
        observation.action_id,
        observation.source_outcome_set_id,
        observation.game,
        observation.league,
        observation.item_class,
        observation.game_version,
        observation.crafting_dataset_version,
        observation.modifier_dataset_version,
        observation.synthetic,
    )


def _dataset_id_for_context(context_key: tuple[Any, ...], prefix: str) -> str:
    digest = hashlib.sha256("|".join("" if value is None else str(value) for value in context_key).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _context_warnings(records: Iterable[EmpiricalCraftingObservation]) -> tuple[str, ...]:
    synthetic_values = {record.synthetic for record in records}
    warnings: list[str] = []
    if len(synthetic_values) > 1:
        warnings.append("Synthetic and non-synthetic observations were separated by context and not mixed.")
    return tuple(warnings)


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _missing_datetime() -> datetime:
    raise ValueError("observed_at is required")


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}
