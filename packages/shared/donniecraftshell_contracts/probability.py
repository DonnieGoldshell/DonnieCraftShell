"""Probability evidence contracts for crafting outcome models.

This module intentionally does not calculate real Path of Exile 2 crafting
probabilities. It represents known, unknown, deterministic, and future
empirical probability evidence beside CraftOutcomeSet data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol

from .craft_outcomes import CraftOutcomeOperation, CraftOutcomeSet
from .domain import Confidence, DataProvenance, ParsedItem


PROBABILITY_MASS_TOLERANCE = Decimal("0.000000001")


class ProbabilityType(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    EXACT_MECHANICAL = "EXACT_MECHANICAL"
    DERIVED_MECHANICAL = "DERIVED_MECHANICAL"
    EMPIRICAL_ESTIMATE = "EMPIRICAL_ESTIMATE"
    UNKNOWN = "UNKNOWN"


class ProbabilityCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProbabilityInterval:
    lower: Decimal
    upper: Decimal

    def __post_init__(self) -> None:
        lower = _probability_decimal(self.lower, "interval.lower")
        upper = _probability_decimal(self.upper, "interval.upper")
        if lower > upper:
            raise ValueError("probability interval lower must be <= upper")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)


@dataclass(frozen=True)
class ProbabilityEvidence:
    evidence_id: str
    probability_type: ProbabilityType
    action_id: str
    outcome_id: str | None = None
    candidate_id: str | None = None
    probability: Decimal | None = None
    methodology: str | None = None
    provenance: tuple[DataProvenance, ...] = ()
    retrieved_at: datetime | None = None
    game_version: str | None = None
    crafting_dataset_version: str | None = None
    modifier_dataset_version: str | None = None
    evidence_dataset_version: str | None = None
    confidence: Confidence | None = None
    sample_size: int | None = None
    uncertainty_interval: ProbabilityInterval | None = None
    notes: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("probability evidence_id is required")
        if not self.action_id:
            raise ValueError("probability evidence action_id is required")
        if self.probability is not None:
            object.__setattr__(self, "probability", _probability_decimal(self.probability, "probability"))
        if self.probability_type == ProbabilityType.UNKNOWN and self.probability is not None:
            raise ValueError("UNKNOWN probability evidence must not include a numeric probability")
        if self.probability_type == ProbabilityType.DETERMINISTIC and self.probability not in {None, Decimal("1")}:
            raise ValueError("DETERMINISTIC evidence may only use probability 1 when numeric")
        if self.sample_size is not None and self.sample_size < 0:
            raise ValueError("probability evidence sample_size cannot be negative")


@dataclass(frozen=True)
class OutcomeProbability:
    outcome_id: str
    probability: Decimal | None
    evidence: tuple[ProbabilityEvidence, ...] = ()
    confidence: Confidence | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.outcome_id:
            raise ValueError("outcome probability requires outcome_id")
        if self.probability is not None:
            object.__setattr__(self, "probability", _probability_decimal(self.probability, "outcome probability"))


@dataclass(frozen=True)
class DeterministicOperationEvidence:
    action_id: str
    operation: CraftOutcomeOperation
    target_identity: str | None
    evidence: ProbabilityEvidence
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.evidence.probability_type != ProbabilityType.DETERMINISTIC:
            raise ValueError("deterministic operation evidence requires DETERMINISTIC evidence")


@dataclass(frozen=True)
class OutcomeProbabilityModel:
    action_id: str
    source_outcome_set_id: str
    outcome_probabilities: tuple[OutcomeProbability, ...]
    probability_completeness: ProbabilityCompleteness
    methodology_summary: str | None = None
    dataset_versions: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()
    deterministic_operations: tuple[DeterministicOperationEvidence, ...] = ()
    total_known_probability_mass: Decimal | None = None

    def __post_init__(self) -> None:
        known_mass = sum(
            (probability.probability for probability in self.outcome_probabilities if probability.probability is not None),
            Decimal("0"),
        )
        object.__setattr__(self, "total_known_probability_mass", known_mass)
        if known_mass > Decimal("1") + PROBABILITY_MASS_TOLERANCE:
            raise ValueError("known probability mass cannot exceed 1")
        if self.probability_completeness == ProbabilityCompleteness.COMPLETE:
            if any(probability.probability is None for probability in self.outcome_probabilities):
                raise ValueError("COMPLETE probability model requires numeric probability for every outcome")
            if abs(known_mass - Decimal("1")) > PROBABILITY_MASS_TOLERANCE:
                raise ValueError("COMPLETE probability model must have total probability mass 1")


@dataclass(frozen=True)
class ProbabilityContext:
    crafting_dataset_version: str | None = None
    modifier_dataset_version: str | None = None
    evidence_dataset_version: str | None = None
    game_version: str | None = None


class ProbabilityProvider(Protocol):
    def get_probability_model(
        self,
        item: ParsedItem,
        outcome_set: CraftOutcomeSet,
        context: ProbabilityContext | None = None,
    ) -> OutcomeProbabilityModel:
        ...


class CurrentResearchProbabilityProvider:
    """Return Task 9A-compliant models for currently supported actions.

    Real final outcome probabilities remain UNKNOWN. Essence of Hysteria can
    carry deterministic evidence for its guaranteed modifier component only.
    """

    def get_probability_model(
        self,
        item: ParsedItem,
        outcome_set: CraftOutcomeSet,
        context: ProbabilityContext | None = None,
    ) -> OutcomeProbabilityModel:
        context = context or ProbabilityContext()
        outcome_probabilities = tuple(
            OutcomeProbability(
                outcome_id=state.outcome_id,
                probability=None,
                evidence=(
                    _unknown_evidence(
                        action_id=outcome_set.action_id,
                        outcome_id=state.outcome_id,
                        context=context,
                    ),
                ),
                warnings=("No source-backed numeric probability is available for this outcome.",),
            )
            for state in outcome_set.hypothetical_states
        )
        deterministic = _deterministic_operations(outcome_set, context)
        warnings = ["No equal-distribution fallback is allowed."]
        if deterministic:
            warnings.append("Deterministic operation evidence does not make combined final outcome probabilities known.")
        return OutcomeProbabilityModel(
            action_id=outcome_set.action_id,
            source_outcome_set_id=_outcome_set_identity(outcome_set),
            outcome_probabilities=outcome_probabilities,
            probability_completeness=ProbabilityCompleteness.UNKNOWN,
            methodology_summary="Task 9A research found no source-backed numeric final outcome probabilities for current actions.",
            dataset_versions=tuple(
                value
                for value in (
                    context.crafting_dataset_version,
                    context.modifier_dataset_version,
                    context.evidence_dataset_version,
                    *outcome_set.dataset_versions,
                )
                if value
            ),
            provenance=outcome_set.provenance,
            warnings=tuple(warnings),
            deterministic_operations=deterministic,
        )


def can_calculate_expected_value(probability_model: OutcomeProbabilityModel) -> bool:
    return (
        probability_model.probability_completeness == ProbabilityCompleteness.COMPLETE
        and all(probability.probability is not None for probability in probability_model.outcome_probabilities)
        and probability_model.total_known_probability_mass is not None
        and abs(probability_model.total_known_probability_mass - Decimal("1")) <= PROBABILITY_MASS_TOLERANCE
    )


def _unknown_evidence(
    action_id: str,
    outcome_id: str | None,
    context: ProbabilityContext,
) -> ProbabilityEvidence:
    return ProbabilityEvidence(
        evidence_id=f"probability:unknown:{action_id}:{outcome_id or 'action'}",
        probability_type=ProbabilityType.UNKNOWN,
        action_id=action_id,
        outcome_id=outcome_id,
        methodology="Task 9A research: source-backed numeric probability unavailable.",
        crafting_dataset_version=context.crafting_dataset_version,
        modifier_dataset_version=context.modifier_dataset_version,
        evidence_dataset_version=context.evidence_dataset_version,
        game_version=context.game_version,
        warnings=("UNKNOWN probability is not zero.",),
    )


def _deterministic_operations(
    outcome_set: CraftOutcomeSet,
    context: ProbabilityContext,
) -> tuple[DeterministicOperationEvidence, ...]:
    deterministic: list[DeterministicOperationEvidence] = []
    if not outcome_set.action_id.endswith(":essence-of-hysteria"):
        return ()
    definition = outcome_set.outcome_definition
    if definition is None or definition.guaranteed_modifier_family_id is None:
        return ()
    evidence = ProbabilityEvidence(
        evidence_id=f"probability:deterministic:{outcome_set.action_id}:guaranteed-modifier-family",
        probability_type=ProbabilityType.DETERMINISTIC,
        action_id=outcome_set.action_id,
        candidate_id=definition.guaranteed_modifier_family_id,
        probability=Decimal("1"),
        methodology="Task 9A research: guaranteed modifier family component is deterministic; random removal remains unknown.",
        provenance=definition.provenance,
        crafting_dataset_version=context.crafting_dataset_version,
        modifier_dataset_version=context.modifier_dataset_version,
        evidence_dataset_version=context.evidence_dataset_version,
        game_version=context.game_version,
        warnings=("This does not assign probability 1 to the combined final outcome state.",),
    )
    deterministic.append(
        DeterministicOperationEvidence(
            action_id=outcome_set.action_id,
            operation=CraftOutcomeOperation.GUARANTEE_MODIFIER,
            target_identity=definition.guaranteed_modifier_family_id,
            evidence=evidence,
            warnings=("Final outcome probability remains unknown because random removal probability is unknown.",),
        )
    )
    return tuple(deterministic)


def _outcome_set_identity(outcome_set: CraftOutcomeSet) -> str:
    return f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}"


def _probability_decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    probability = Decimal(value)
    if probability < Decimal("0") or probability > Decimal("1"):
        raise ValueError(f"{field_name} must be between 0 and 1")
    return probability
