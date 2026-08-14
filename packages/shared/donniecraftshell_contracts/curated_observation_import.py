"""Build empirical probability datasets from curated observation exports.

This module joins Task 16B accepted exports to the existing Task 15C importer.
It does not calculate probabilities, activate Advisor evidence, or persist files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .empirical_observation_import import (
    EmpiricalObservationAggregationResult,
    ObservationImportBatch,
    ObservationValidationIssue,
    aggregate_observations,
    empirical_observation_from_dict,
    raw_empirical_probability_dataset_to_dict,
)
from .empirical_probability import RawEmpiricalProbabilityDataset


CURATED_OBSERVATION_IMPORT_VERSION = "dc-curated-observation-import-v1"


@dataclass(frozen=True)
class CuratedObservationBuildResult:
    build_version: str
    built_at: datetime
    source_record_count: int
    imported_record_count: int
    accepted_record_count: int
    duplicate_record_count: int
    unclassified_record_count: int
    invalid_record_count: int
    dataset_ids: tuple[str, ...]
    datasets: tuple[RawEmpiricalProbabilityDataset, ...]
    rejected_records: tuple[ObservationValidationIssue, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def dataset_count(self) -> int:
        return len(self.datasets)

    def to_dict(self) -> dict[str, Any]:
        return {
            "build_version": self.build_version,
            "built_at": self.built_at.isoformat(),
            "source_record_count": self.source_record_count,
            "imported_record_count": self.imported_record_count,
            "accepted_record_count": self.accepted_record_count,
            "duplicate_record_count": self.duplicate_record_count,
            "unclassified_record_count": self.unclassified_record_count,
            "invalid_record_count": self.invalid_record_count,
            "dataset_count": self.dataset_count,
            "dataset_ids": list(self.dataset_ids),
            "datasets": [raw_empirical_probability_dataset_to_dict(dataset) for dataset in self.datasets],
            "rejected_records": [
                {"raw_record_id": record.raw_record_id, "reason": record.reason}
                for record in self.rejected_records
            ],
            "warnings": list(self.warnings),
        }


def build_empirical_datasets_from_curated_export(
    accepted_export: dict[str, Any],
    built_at: datetime | None = None,
    dataset_id_prefix: str = "empirical-probability",
) -> CuratedObservationBuildResult:
    """Validate and aggregate a Task 16B accepted export through Task 15C."""

    built_at = built_at or datetime.now(timezone.utc)
    if built_at.tzinfo is None:
        raise ValueError("built_at must be timezone-aware")
    records = _accepted_records(accepted_export)
    observations = []
    rejected = []
    for index, record in enumerate(records, start=1):
        try:
            observations.append(empirical_observation_from_dict(record))
        except Exception as exc:
            rejected.append(
                ObservationValidationIssue(
                    raw_record_id=str(record.get("raw_record_id")) if isinstance(record, dict) else None,
                    reason=f"accepted_export:{index}: {exc}",
                )
            )

    aggregation = aggregate_observations(
        ObservationImportBatch(tuple(observations), rejected_records=tuple(rejected)),
        retrieved_at=built_at,
        dataset_id_prefix=dataset_id_prefix,
    )
    warnings = list(accepted_export.get("warnings", ())) + list(aggregation.warnings)
    if rejected:
        warnings.append("Malformed accepted-export records were rejected before empirical aggregation.")
    warnings.append("Dataset build does not activate probability evidence or make Advisor EV-ready by itself.")
    return CuratedObservationBuildResult(
        build_version=CURATED_OBSERVATION_IMPORT_VERSION,
        built_at=built_at,
        source_record_count=len(records),
        imported_record_count=len(observations),
        accepted_record_count=aggregation.accepted_record_count,
        duplicate_record_count=aggregation.duplicate_record_count,
        unclassified_record_count=aggregation.unclassified_record_count,
        invalid_record_count=len(rejected),
        dataset_ids=tuple(dataset.dataset_id for dataset in aggregation.datasets),
        datasets=aggregation.datasets,
        rejected_records=tuple(rejected),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _accepted_records(accepted_export: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    records = accepted_export.get("observations")
    if not isinstance(records, list):
        raise ValueError("curated accepted export must contain observations as a list")
    return tuple(dict(record) for record in records if isinstance(record, dict))
