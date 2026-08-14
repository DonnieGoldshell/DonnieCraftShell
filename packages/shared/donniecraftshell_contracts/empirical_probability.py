"""Empirical probability evidence pipeline for crafting outcomes.

This module turns explicit offline outcome-count observations into
ProbabilityEvidence. It never infers uniform probabilities from an outcome
space and never fabricates observations for missing outcomes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .craft_outcomes import CraftOutcomeSet
from .domain import Confidence, ConfidenceLevel, DataProvenance, ParsedItem, SourceType, VerificationStatus
from .probability import (
    CurrentResearchProbabilityProvider,
    OutcomeProbability,
    OutcomeProbabilityModel,
    ProbabilityCompleteness,
    ProbabilityContext,
    ProbabilityEvidence,
    ProbabilityInterval,
    ProbabilityType,
)


EMPIRICAL_PROBABILITY_METHODOLOGY_VERSION = "dc-empirical-probability-v1"
EMPIRICAL_PROBABILITY_WARNING = "Empirical estimates are not official mechanical probabilities."
EMPIRICAL_DATASET_REGISTRY_VERSION = "dc-empirical-dataset-registry-v1"
EMPIRICAL_DATASET_REGISTRY_STORAGE_VERSION = "dc-empirical-dataset-registry-storage-v1"


@dataclass(frozen=True)
class EmpiricalProbabilityReadinessPolicy:
    """DonnieCraftShell policy thresholds for empirical evidence readiness."""

    minimum_sample_size_for_complete: int = 30
    wilson_z: Decimal = Decimal("1.96")
    policy_version: str = "dc-empirical-readiness-policy-v1"

    def __post_init__(self) -> None:
        if self.minimum_sample_size_for_complete < 1:
            raise ValueError("minimum_sample_size_for_complete must be at least 1")
        z = _decimal(self.wilson_z, "wilson_z")
        if z <= Decimal("0"):
            raise ValueError("wilson_z must be positive")
        object.__setattr__(self, "wilson_z", z)


@dataclass(frozen=True)
class EmpiricalOutcomeCount:
    outcome_id: str
    observed_count: int
    raw_record_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.outcome_id:
            raise ValueError("empirical outcome count requires outcome_id")
        if self.observed_count < 0:
            raise ValueError("observed_count cannot be negative")


@dataclass(frozen=True)
class RawEmpiricalProbabilityDataset:
    dataset_id: str
    action_id: str
    source_outcome_set_id: str
    game: str
    league: str
    retrieved_at: datetime
    observations: tuple[EmpiricalOutcomeCount, ...]
    unclassified_count: int = 0
    source_uri: str | None = None
    source_type: SourceType = SourceType.MANUAL_RESEARCH
    synthetic: bool = False
    item_class: str | None = None
    game_version: str | None = None
    crafting_dataset_version: str | None = None
    modifier_dataset_version: str | None = None
    methodology: str | None = None
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    notes: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.dataset_id:
            raise ValueError("empirical probability dataset_id is required")
        if not self.action_id:
            raise ValueError("empirical probability action_id is required")
        if not self.source_outcome_set_id:
            raise ValueError("source_outcome_set_id is required")
        if not self.game:
            raise ValueError("game is required")
        if not self.league:
            raise ValueError("league is required")
        if self.unclassified_count < 0:
            raise ValueError("unclassified_count cannot be negative")
        if not self.observations and self.unclassified_count == 0:
            raise ValueError("empirical dataset must preserve at least one observation or unclassified count")


@dataclass(frozen=True)
class EmpiricalProbabilityDataset:
    dataset_id: str
    action_id: str
    source_outcome_set_id: str
    game: str
    league: str
    retrieved_at: datetime
    outcome_counts: tuple[EmpiricalOutcomeCount, ...]
    unclassified_count: int
    sample_size: int
    provenance: tuple[DataProvenance, ...]
    synthetic: bool = False
    item_class: str | None = None
    game_version: str | None = None
    crafting_dataset_version: str | None = None
    modifier_dataset_version: str | None = None
    methodology: str = EMPIRICAL_PROBABILITY_METHODOLOGY_VERSION
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.dataset_id:
            raise ValueError("empirical probability dataset_id is required")
        if self.sample_size != sum(count.observed_count for count in self.outcome_counts) + self.unclassified_count:
            raise ValueError("sample_size must equal classified plus unclassified observations")
        if self.sample_size <= 0:
            raise ValueError("sample_size must be positive")
        seen: set[str] = set()
        for count in self.outcome_counts:
            if count.outcome_id in seen:
                raise ValueError(f"duplicate empirical outcome count for {count.outcome_id}")
            seen.add(count.outcome_id)


class EmpiricalDatasetRegistrationStatus(str, Enum):
    REGISTERED = "REGISTERED"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class EmpiricalProbabilityDatasetSummary:
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
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    methodology: str = EMPIRICAL_PROBABILITY_METHODOLOGY_VERSION
    source_uri: str | None = None
    source_type: SourceType | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmpiricalDatasetRegistrationResult:
    status: EmpiricalDatasetRegistrationStatus
    dataset_id: str | None
    summary: EmpiricalProbabilityDatasetSummary | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmpiricalRegistryPersistenceStatus:
    storage_version: str
    storage_mode: str
    persistence_enabled: bool
    loaded_dataset_count: int
    skipped_dataset_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmpiricalProbabilityRepository:
    datasets: tuple[EmpiricalProbabilityDataset, ...]
    skipped_dataset_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_json_files(
        cls,
        paths: tuple[str | Path, ...],
        allow_synthetic: bool = False,
    ) -> "EmpiricalProbabilityRepository":
        datasets: list[EmpiricalProbabilityDataset] = []
        skipped: list[str] = []
        warnings: list[str] = []
        for path in paths:
            dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(path))
            if dataset.synthetic and not allow_synthetic:
                skipped.append(dataset.dataset_id)
                warnings.append(f"Skipped synthetic empirical probability dataset {dataset.dataset_id}.")
                continue
            datasets.append(dataset)
        return cls(tuple(datasets), tuple(skipped), tuple(warnings))

    def to_provider(
        self,
        readiness_policy: EmpiricalProbabilityReadinessPolicy | None = None,
        allow_synthetic: bool = False,
    ) -> "EmpiricalProbabilityProvider":
        return EmpiricalProbabilityProvider(
            self.datasets,
            readiness_policy=readiness_policy,
            allow_synthetic=allow_synthetic,
        )


class EmpiricalProbabilityDatasetRegistry:
    """In-process registry for explicitly selected empirical probability datasets.

    Registration alone never activates a dataset for Advisor analysis. The
    Advisor request must still carry the desired evidence dataset ID.
    """

    def __init__(self, datasets: tuple[EmpiricalProbabilityDataset, ...] = ()) -> None:
        self._datasets: dict[str, EmpiricalProbabilityDataset] = {}
        self._fingerprints: dict[str, str] = {}
        self._registration_payloads: dict[str, dict[str, Any]] = {}
        for dataset in datasets:
            result = self.register_dataset(dataset)
            if result.status == EmpiricalDatasetRegistrationStatus.REJECTED:
                raise ValueError("; ".join(result.warnings))

    @classmethod
    def from_repository(cls, repository: EmpiricalProbabilityRepository) -> "EmpiricalProbabilityDatasetRegistry":
        return cls(repository.datasets)

    def register_raw_payload(self, payload: dict[str, Any]) -> EmpiricalDatasetRegistrationResult:
        try:
            dataset = normalize_empirical_probability_dataset(raw_empirical_probability_dataset_from_dict(payload))
        except Exception as exc:
            return EmpiricalDatasetRegistrationResult(
                status=EmpiricalDatasetRegistrationStatus.REJECTED,
                dataset_id=None,
                warnings=(f"Malformed empirical probability dataset payload: {exc}",),
            )
        return self.register_dataset(dataset, raw_payload=payload)

    def register_dataset(
        self,
        dataset: EmpiricalProbabilityDataset,
        raw_payload: dict[str, Any] | None = None,
    ) -> EmpiricalDatasetRegistrationResult:
        fingerprint = _dataset_fingerprint(dataset)
        existing = self._datasets.get(dataset.dataset_id)
        if existing is not None:
            if self._fingerprints[dataset.dataset_id] == fingerprint:
                return EmpiricalDatasetRegistrationResult(
                    status=EmpiricalDatasetRegistrationStatus.ALREADY_REGISTERED,
                    dataset_id=dataset.dataset_id,
                    summary=_dataset_summary(existing),
                    warnings=("Dataset ID was already registered with identical content; registration is idempotent.",),
                )
            return EmpiricalDatasetRegistrationResult(
                status=EmpiricalDatasetRegistrationStatus.REJECTED,
                dataset_id=dataset.dataset_id,
                warnings=("Dataset ID is already registered with different content; conflicting empirical evidence was rejected.",),
            )
        self._datasets[dataset.dataset_id] = dataset
        self._fingerprints[dataset.dataset_id] = fingerprint
        self._registration_payloads[dataset.dataset_id] = _json_payload_copy(
            raw_payload or empirical_probability_dataset_to_raw_dict(dataset)
        )
        return EmpiricalDatasetRegistrationResult(
            status=EmpiricalDatasetRegistrationStatus.REGISTERED,
            dataset_id=dataset.dataset_id,
            summary=_dataset_summary(dataset),
            warnings=dataset.warnings,
        )

    def get_dataset(self, dataset_id: str) -> EmpiricalProbabilityDataset | None:
        return self._datasets.get(dataset_id)

    def list_summaries(self) -> tuple[EmpiricalProbabilityDatasetSummary, ...]:
        return tuple(_dataset_summary(self._datasets[dataset_id]) for dataset_id in sorted(self._datasets))

    def persistence_status(self) -> EmpiricalRegistryPersistenceStatus:
        return EmpiricalRegistryPersistenceStatus(
            storage_version=EMPIRICAL_DATASET_REGISTRY_STORAGE_VERSION,
            storage_mode="IN_MEMORY",
            persistence_enabled=False,
            loaded_dataset_count=len(self._datasets),
            warnings=("Registry persistence is disabled; datasets exist only for this process.",),
        )

    def to_provider(
        self,
        readiness_policy: EmpiricalProbabilityReadinessPolicy | None = None,
        allow_synthetic: bool = False,
    ) -> "EmpiricalProbabilityProvider":
        return EmpiricalProbabilityProvider(
            tuple(self._datasets[dataset_id] for dataset_id in sorted(self._datasets)),
            readiness_policy=readiness_policy,
            allow_synthetic=allow_synthetic,
        )


class FileBackedEmpiricalProbabilityDatasetRegistry(EmpiricalProbabilityDatasetRegistry):
    """Local JSON-backed registry for single-user/operator workflows."""

    def __init__(
        self,
        storage_path: str | Path,
        datasets: tuple[EmpiricalProbabilityDataset, ...] = (),
    ) -> None:
        self._storage_path = Path(storage_path)
        self._load_warnings: list[str] = []
        self._skipped_dataset_count = 0
        super().__init__()
        for dataset, payload in self._load_persisted_datasets():
            result = super().register_dataset(dataset, raw_payload=payload)
            if result.status == EmpiricalDatasetRegistrationStatus.REJECTED:
                self._skipped_dataset_count += 1
                self._load_warnings.extend(result.warnings)
        for dataset in datasets:
            result = super().register_dataset(dataset)
            if result.status == EmpiricalDatasetRegistrationStatus.REJECTED:
                self._load_warnings.extend(result.warnings)

    @classmethod
    def from_repository(
        cls,
        repository: EmpiricalProbabilityRepository,
        storage_path: str | Path,
    ) -> "FileBackedEmpiricalProbabilityDatasetRegistry":
        return cls(storage_path, repository.datasets)

    def register_dataset(
        self,
        dataset: EmpiricalProbabilityDataset,
        raw_payload: dict[str, Any] | None = None,
    ) -> EmpiricalDatasetRegistrationResult:
        before_payloads = dict(self._registration_payloads)
        result = super().register_dataset(dataset, raw_payload=raw_payload)
        if result.status == EmpiricalDatasetRegistrationStatus.REGISTERED:
            try:
                self._persist()
            except Exception as exc:
                self._datasets.pop(dataset.dataset_id, None)
                self._fingerprints.pop(dataset.dataset_id, None)
                self._registration_payloads = before_payloads
                return EmpiricalDatasetRegistrationResult(
                    status=EmpiricalDatasetRegistrationStatus.REJECTED,
                    dataset_id=dataset.dataset_id,
                    warnings=(f"Empirical registry persistence failed; dataset was not registered: {exc}",),
                )
        return result

    def persistence_status(self) -> EmpiricalRegistryPersistenceStatus:
        return EmpiricalRegistryPersistenceStatus(
            storage_version=EMPIRICAL_DATASET_REGISTRY_STORAGE_VERSION,
            storage_mode="FILE",
            persistence_enabled=True,
            loaded_dataset_count=len(self._datasets),
            skipped_dataset_count=self._skipped_dataset_count,
            warnings=tuple(self._load_warnings),
        )

    def _load_persisted_datasets(self) -> tuple[tuple[EmpiricalProbabilityDataset, dict[str, Any]], ...]:
        if not self._storage_path.exists():
            return ()
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._skipped_dataset_count += 1
            self._load_warnings.append(f"Empirical registry storage could not be read and was skipped: {exc}")
            return ()
        if not isinstance(payload, dict):
            self._skipped_dataset_count += 1
            self._load_warnings.append("Empirical registry storage root must be an object; persisted datasets were skipped.")
            return ()
        records = payload.get("datasets", ())
        if not isinstance(records, list):
            self._skipped_dataset_count += 1
            self._load_warnings.append("Empirical registry storage datasets must be a list; persisted datasets were skipped.")
            return ()
        datasets: list[tuple[EmpiricalProbabilityDataset, dict[str, Any]]] = []
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                self._skipped_dataset_count += 1
                self._load_warnings.append(f"Persisted empirical dataset #{index} is not an object and was skipped.")
                continue
            try:
                raw = raw_empirical_probability_dataset_from_dict(record)
                datasets.append((normalize_empirical_probability_dataset(raw), record))
            except Exception as exc:
                self._skipped_dataset_count += 1
                dataset_id = record.get("dataset_id", f"#{index}")
                self._load_warnings.append(f"Persisted empirical dataset {dataset_id} was skipped: {exc}")
        return tuple(datasets)

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "registry_version": EMPIRICAL_DATASET_REGISTRY_VERSION,
            "storage_version": EMPIRICAL_DATASET_REGISTRY_STORAGE_VERSION,
            "datasets": [
                self._registration_payloads[dataset_id]
                for dataset_id in sorted(self._registration_payloads)
            ],
        }
        encoded = json.dumps(payload, indent=2, sort_keys=True)
        temporary_path = self._storage_path.with_name(f"{self._storage_path.name}.tmp")
        temporary_path.write_text(encoded, encoding="utf-8")
        temporary_path.replace(self._storage_path)


class EmpiricalProbabilityRegistryProvider:
    """ProbabilityProvider backed by the current contents of a dataset registry."""

    def __init__(
        self,
        registry: EmpiricalProbabilityDatasetRegistry,
        readiness_policy: EmpiricalProbabilityReadinessPolicy | None = None,
        allow_synthetic: bool = False,
    ) -> None:
        self._registry = registry
        self._readiness_policy = readiness_policy
        self._allow_synthetic = allow_synthetic

    def get_probability_model(
        self,
        item: ParsedItem,
        outcome_set: CraftOutcomeSet,
        context: ProbabilityContext | None = None,
    ) -> OutcomeProbabilityModel:
        return self._registry.to_provider(
            readiness_policy=self._readiness_policy,
            allow_synthetic=self._allow_synthetic,
        ).get_probability_model(item, outcome_set, context)


def load_raw_empirical_probability_dataset(path: str | Path) -> RawEmpiricalProbabilityDataset:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw_empirical_probability_dataset_from_dict(data)


def empirical_probability_dataset_to_raw_dict(dataset: EmpiricalProbabilityDataset) -> dict[str, Any]:
    provenance = dataset.provenance[0] if dataset.provenance else None
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
        "source_uri": provenance.source_uri if provenance is not None else None,
        "source_type": provenance.source_type.value if provenance is not None else SourceType.MANUAL_RESEARCH.value,
        "synthetic": dataset.synthetic,
        "verification_status": dataset.verification_status.value,
        "methodology": dataset.methodology,
        "notes": provenance.notes if provenance is not None else None,
        "warnings": list(dataset.warnings),
        "unclassified_count": dataset.unclassified_count,
        "observations": [
            {
                "outcome_id": observation.outcome_id,
                "observed_count": observation.observed_count,
                "raw_record_ids": list(observation.raw_record_ids),
                "warnings": list(observation.warnings),
            }
            for observation in dataset.outcome_counts
        ],
    }


def raw_empirical_probability_dataset_from_dict(data: dict[str, Any]) -> RawEmpiricalProbabilityDataset:
    observations = tuple(
        EmpiricalOutcomeCount(
            outcome_id=str(record["outcome_id"]),
            observed_count=int(record["observed_count"]),
            raw_record_ids=tuple(str(value) for value in record.get("raw_record_ids", ())),
            warnings=tuple(str(value) for value in record.get("warnings", ())),
        )
        for record in data.get("observations", ())
    )
    return RawEmpiricalProbabilityDataset(
        dataset_id=str(data["dataset_id"]),
        action_id=str(data["action_id"]),
        source_outcome_set_id=str(data["source_outcome_set_id"]),
        game=str(data["game"]),
        league=str(data["league"]),
        retrieved_at=_datetime(data["retrieved_at"]),
        observations=observations,
        unclassified_count=int(data.get("unclassified_count", 0)),
        source_uri=data.get("source_uri"),
        source_type=SourceType(data.get("source_type", SourceType.MANUAL_RESEARCH.value)),
        synthetic=bool(data.get("synthetic", False)),
        item_class=data.get("item_class"),
        game_version=data.get("game_version"),
        crafting_dataset_version=data.get("crafting_dataset_version"),
        modifier_dataset_version=data.get("modifier_dataset_version"),
        methodology=data.get("methodology"),
        verification_status=VerificationStatus(data.get("verification_status", VerificationStatus.NEEDS_VERIFICATION.value)),
        notes=data.get("notes"),
        warnings=tuple(str(value) for value in data.get("warnings", ())),
    )


def normalize_empirical_probability_dataset(
    raw: RawEmpiricalProbabilityDataset,
) -> EmpiricalProbabilityDataset:
    provenance = (
        DataProvenance(
            source_id=raw.dataset_id,
            source_type=raw.source_type,
            source_uri=raw.source_uri,
            retrieved_at=raw.retrieved_at,
            game_version=raw.game_version,
            league=raw.league,
            verification_status=raw.verification_status,
            notes=raw.notes,
        ),
    )
    warnings = list(raw.warnings)
    if raw.synthetic:
        warnings.append("Synthetic test-only empirical evidence must not be loaded as production probability data.")
    return EmpiricalProbabilityDataset(
        dataset_id=raw.dataset_id,
        action_id=raw.action_id,
        source_outcome_set_id=raw.source_outcome_set_id,
        game=raw.game,
        league=raw.league,
        retrieved_at=raw.retrieved_at,
        outcome_counts=raw.observations,
        unclassified_count=raw.unclassified_count,
        sample_size=sum(count.observed_count for count in raw.observations) + raw.unclassified_count,
        provenance=provenance,
        synthetic=raw.synthetic,
        item_class=raw.item_class,
        game_version=raw.game_version,
        crafting_dataset_version=raw.crafting_dataset_version,
        modifier_dataset_version=raw.modifier_dataset_version,
        methodology=raw.methodology or EMPIRICAL_PROBABILITY_METHODOLOGY_VERSION,
        verification_status=raw.verification_status,
        warnings=tuple(warnings),
    )


class EmpiricalProbabilityProvider:
    """Return empirical models only when context-compatible evidence is supplied."""

    def __init__(
        self,
        datasets: tuple[EmpiricalProbabilityDataset, ...],
        readiness_policy: EmpiricalProbabilityReadinessPolicy | None = None,
        fallback_provider: CurrentResearchProbabilityProvider | None = None,
        allow_synthetic: bool = False,
    ) -> None:
        self._datasets = datasets
        self._readiness_policy = readiness_policy or EmpiricalProbabilityReadinessPolicy()
        self._fallback_provider = fallback_provider or CurrentResearchProbabilityProvider()
        self._allow_synthetic = allow_synthetic

    def get_probability_model(
        self,
        item: ParsedItem,
        outcome_set: CraftOutcomeSet,
        context: ProbabilityContext | None = None,
    ) -> OutcomeProbabilityModel:
        context = context or ProbabilityContext()
        dataset = self._find_dataset(item, outcome_set, context)
        if dataset is None:
            model = self._fallback_provider.get_probability_model(item, outcome_set, context)
            if context.evidence_dataset_version:
                return OutcomeProbabilityModel(
                    action_id=model.action_id,
                    source_outcome_set_id=model.source_outcome_set_id,
                    outcome_probabilities=model.outcome_probabilities,
                    probability_completeness=model.probability_completeness,
                    methodology_summary=model.methodology_summary,
                    dataset_versions=model.dataset_versions,
                    provenance=model.provenance,
                    warnings=(
                        *model.warnings,
                        f"Requested empirical probability dataset {context.evidence_dataset_version} is not registered or does not match this action/outcome set.",
                    ),
                    deterministic_operations=model.deterministic_operations,
                )
            return model
        if dataset.synthetic and not self._allow_synthetic:
            model = self._fallback_provider.get_probability_model(item, outcome_set, context)
            return OutcomeProbabilityModel(
                action_id=model.action_id,
                source_outcome_set_id=model.source_outcome_set_id,
                outcome_probabilities=model.outcome_probabilities,
                probability_completeness=ProbabilityCompleteness.UNKNOWN,
                methodology_summary="Synthetic empirical evidence was present but not enabled for this provider.",
                dataset_versions=tuple(value for value in (*model.dataset_versions, dataset.dataset_id) if value),
                provenance=(*model.provenance, *dataset.provenance),
                warnings=(
                    *model.warnings,
                    "Synthetic empirical probability datasets require explicit test-only injection.",
                ),
                deterministic_operations=model.deterministic_operations,
            )
        incompatible = _context_warnings(item, dataset, context)
        if incompatible:
            model = self._fallback_provider.get_probability_model(item, outcome_set, context)
            return OutcomeProbabilityModel(
                action_id=model.action_id,
                source_outcome_set_id=model.source_outcome_set_id,
                outcome_probabilities=model.outcome_probabilities,
                probability_completeness=ProbabilityCompleteness.UNKNOWN,
                methodology_summary="Empirical evidence exists but is not context-compatible with this outcome set.",
                dataset_versions=tuple(value for value in (*model.dataset_versions, dataset.dataset_id) if value),
                provenance=(*model.provenance, *dataset.provenance),
                warnings=(*model.warnings, *incompatible),
                deterministic_operations=model.deterministic_operations,
            )
        return _model_from_dataset(outcome_set, dataset, self._readiness_policy, context)

    def _find_dataset(
        self,
        item: ParsedItem,
        outcome_set: CraftOutcomeSet,
        context: ProbabilityContext,
    ) -> EmpiricalProbabilityDataset | None:
        if not context.evidence_dataset_version:
            return None
        source_outcome_set_id = _outcome_set_identity(outcome_set)
        for dataset in self._datasets:
            if dataset.action_id != outcome_set.action_id:
                continue
            if dataset.source_outcome_set_id != source_outcome_set_id:
                continue
            if context.evidence_dataset_version and dataset.dataset_id != context.evidence_dataset_version:
                continue
            return dataset
        return None


def _model_from_dataset(
    outcome_set: CraftOutcomeSet,
    dataset: EmpiricalProbabilityDataset,
    readiness_policy: EmpiricalProbabilityReadinessPolicy,
    context: ProbabilityContext,
) -> OutcomeProbabilityModel:
    outcome_ids = tuple(state.outcome_id for state in outcome_set.hypothetical_states)
    outcome_id_set = set(outcome_ids)
    counts_by_id = {count.outcome_id: count for count in dataset.outcome_counts}
    unmapped_count = sum(count.observed_count for count in dataset.outcome_counts if count.outcome_id not in outcome_id_set)
    denominator = dataset.sample_size
    warnings = [EMPIRICAL_PROBABILITY_WARNING, *dataset.warnings]
    if dataset.synthetic:
        warnings.append("Synthetic empirical fixture is test-only.")
    if dataset.unclassified_count:
        warnings.append(f"{dataset.unclassified_count} observations were unclassified and remain in the denominator.")
    if unmapped_count:
        warnings.append(f"{unmapped_count} observations do not map to this outcome set and remain in the denominator.")
    missing_outcomes = tuple(outcome_id for outcome_id in outcome_ids if outcome_id not in counts_by_id)
    if missing_outcomes:
        warnings.append("Some outcome IDs have no explicit empirical count; missing probabilities remain UNKNOWN.")
    if denominator < readiness_policy.minimum_sample_size_for_complete:
        warnings.append(
            f"Sample size {denominator} is below {readiness_policy.minimum_sample_size_for_complete}; completeness is PARTIAL."
        )

    probabilities = tuple(
        _outcome_probability(outcome_id, counts_by_id.get(outcome_id), denominator, dataset, readiness_policy)
        for outcome_id in outcome_ids
    )
    complete = (
        not missing_outcomes
        and dataset.unclassified_count == 0
        and unmapped_count == 0
        and denominator >= readiness_policy.minimum_sample_size_for_complete
    )
    return OutcomeProbabilityModel(
        action_id=outcome_set.action_id,
        source_outcome_set_id=_outcome_set_identity(outcome_set),
        outcome_probabilities=probabilities,
        probability_completeness=ProbabilityCompleteness.COMPLETE if complete else ProbabilityCompleteness.PARTIAL,
        methodology_summary=(
            f"{dataset.methodology}; point estimates are observed frequencies and intervals use "
            f"Wilson score one-vs-rest bounds ({readiness_policy.policy_version})."
        ),
        dataset_versions=tuple(
            value
            for value in (
                context.crafting_dataset_version,
                context.modifier_dataset_version,
                dataset.crafting_dataset_version,
                dataset.modifier_dataset_version,
                dataset.dataset_id,
                *outcome_set.dataset_versions,
            )
            if value
        ),
        provenance=(*outcome_set.provenance, *dataset.provenance),
        warnings=tuple(warnings),
    )


def _outcome_probability(
    outcome_id: str,
    count: EmpiricalOutcomeCount | None,
    denominator: int,
    dataset: EmpiricalProbabilityDataset,
    readiness_policy: EmpiricalProbabilityReadinessPolicy,
) -> OutcomeProbability:
    if count is None:
        return OutcomeProbability(
            outcome_id=outcome_id,
            probability=None,
            warnings=("No empirical observation count exists for this outcome; UNKNOWN is not zero.",),
        )
    probability = _decimal(count.observed_count, "observed_count") / _decimal(denominator, "denominator")
    interval = _wilson_interval(count.observed_count, denominator, readiness_policy.wilson_z)
    evidence_warnings = tuple(
        warning
        for warning in (
            EMPIRICAL_PROBABILITY_WARNING,
            "Synthetic test-only evidence." if dataset.synthetic else None,
            *count.warnings,
        )
        if warning
    )
    evidence = ProbabilityEvidence(
        evidence_id=f"probability:empirical:{dataset.dataset_id}:{outcome_id}",
        probability_type=ProbabilityType.EMPIRICAL_ESTIMATE,
        action_id=dataset.action_id,
        outcome_id=outcome_id,
        probability=probability,
        methodology=dataset.methodology,
        provenance=dataset.provenance,
        retrieved_at=dataset.retrieved_at,
        game_version=dataset.game_version,
        crafting_dataset_version=dataset.crafting_dataset_version,
        modifier_dataset_version=dataset.modifier_dataset_version,
        evidence_dataset_version=dataset.dataset_id,
        confidence=Confidence(
            level=ConfidenceLevel.LOW if dataset.synthetic else ConfidenceLevel.UNKNOWN,
            reasons=("Empirical observation count; not official mechanical probability.",),
            sample_size=denominator,
        ),
        sample_size=denominator,
        uncertainty_interval=interval,
        notes=f"Observed {count.observed_count} of {denominator} denominator observations.",
        warnings=evidence_warnings,
    )
    return OutcomeProbability(
        outcome_id=outcome_id,
        probability=probability,
        evidence=(evidence,),
        confidence=evidence.confidence,
        warnings=evidence_warnings,
    )


def _wilson_interval(successes: int, sample_size: int, z: Decimal) -> ProbabilityInterval:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive for Wilson interval")
    n = _decimal(sample_size, "sample_size")
    p = _decimal(successes, "successes") / n
    z2 = z * z
    denominator = Decimal("1") + z2 / n
    center = (p + z2 / (Decimal("2") * n)) / denominator
    margin_term = (p * (Decimal("1") - p) + z2 / (Decimal("4") * n)) / n
    margin = z * margin_term.sqrt() / denominator
    lower = max(Decimal("0"), center - margin)
    upper = min(Decimal("1"), center + margin)
    return ProbabilityInterval(lower=lower, upper=upper)


def _context_warnings(
    item: ParsedItem,
    dataset: EmpiricalProbabilityDataset,
    context: ProbabilityContext,
) -> tuple[str, ...]:
    warnings: list[str] = []
    item_class = getattr(item, "item_class", None)
    if dataset.item_class and item_class and dataset.item_class != item_class:
        warnings.append(f"Empirical dataset item_class {dataset.item_class} does not match item class {item_class}.")
    if context.league and dataset.league != context.league:
        warnings.append(f"Empirical dataset league {dataset.league} does not match requested league {context.league}.")
    if context.game_version and dataset.game_version and dataset.game_version != context.game_version:
        warnings.append("Empirical dataset game version does not match the requested context.")
    if (
        context.crafting_dataset_version
        and dataset.crafting_dataset_version
        and dataset.crafting_dataset_version != context.crafting_dataset_version
    ):
        warnings.append("Empirical dataset crafting version does not match the requested context.")
    if (
        context.modifier_dataset_version
        and dataset.modifier_dataset_version
        and dataset.modifier_dataset_version != context.modifier_dataset_version
    ):
        warnings.append("Empirical dataset modifier version does not match the requested context.")
    return tuple(warnings)


def _outcome_set_identity(outcome_set: CraftOutcomeSet) -> str:
    return f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}"


def _dataset_summary(dataset: EmpiricalProbabilityDataset) -> EmpiricalProbabilityDatasetSummary:
    provenance = dataset.provenance[0] if dataset.provenance else None
    return EmpiricalProbabilityDatasetSummary(
        dataset_id=dataset.dataset_id,
        action_id=dataset.action_id,
        source_outcome_set_id=dataset.source_outcome_set_id,
        game=dataset.game,
        league=dataset.league,
        sample_size=dataset.sample_size,
        unclassified_count=dataset.unclassified_count,
        outcome_count=len(dataset.outcome_counts),
        retrieved_at=dataset.retrieved_at,
        synthetic=dataset.synthetic,
        item_class=dataset.item_class,
        game_version=dataset.game_version,
        crafting_dataset_version=dataset.crafting_dataset_version,
        modifier_dataset_version=dataset.modifier_dataset_version,
        verification_status=dataset.verification_status,
        methodology=dataset.methodology,
        source_uri=provenance.source_uri if provenance is not None else None,
        source_type=provenance.source_type if provenance is not None else None,
        warnings=dataset.warnings,
    )


def _dataset_fingerprint(dataset: EmpiricalProbabilityDataset) -> str:
    payload = {
        "dataset_id": dataset.dataset_id,
        "action_id": dataset.action_id,
        "source_outcome_set_id": dataset.source_outcome_set_id,
        "game": dataset.game,
        "league": dataset.league,
        "retrieved_at": dataset.retrieved_at.isoformat(),
        "outcome_counts": [
            {
                "outcome_id": count.outcome_id,
                "observed_count": count.observed_count,
                "raw_record_ids": list(count.raw_record_ids),
                "warnings": list(count.warnings),
            }
            for count in sorted(dataset.outcome_counts, key=lambda item: item.outcome_id)
        ],
        "unclassified_count": dataset.unclassified_count,
        "synthetic": dataset.synthetic,
        "item_class": dataset.item_class,
        "game_version": dataset.game_version,
        "crafting_dataset_version": dataset.crafting_dataset_version,
        "modifier_dataset_version": dataset.modifier_dataset_version,
        "methodology": dataset.methodology,
        "verification_status": dataset.verification_status.value,
        "provenance": [
            {
                "source_id": item.source_id,
                "source_type": item.source_type.value,
                "source_uri": item.source_uri,
                "retrieved_at": item.retrieved_at.isoformat() if item.retrieved_at else None,
                "game_version": item.game_version,
                "league": item.league,
                "verification_status": item.verification_status.value,
                "notes": item.notes,
            }
            for item in dataset.provenance
        ],
        "warnings": list(dataset.warnings),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_payload_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, sort_keys=True))


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    return Decimal(value)
