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

from .craft_outcomes import CraftOutcomeOperation, CraftOutcomeSet, OutcomeSelectionRule, OutcomeSpaceCompleteness
from .domain import Confidence, ConfidenceLevel, DataProvenance, ParsedItem, VerificationStatus


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


class AnalyticalProbabilityRuleType(str, Enum):
    UNIFORM_ENUMERATED_OUTCOMES = "UNIFORM_ENUMERATED_OUTCOMES"


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
    league: str | None = None


@dataclass(frozen=True)
class AnalyticalProbabilityRule:
    """Explicit verified-mechanic rule for deriving probabilities analytically.

    A rule is never inferred from outcome count alone. It must be supplied by a
    verified dataset/source and is scoped to one action.
    """

    rule_id: str
    action_id: str
    rule_type: AnalyticalProbabilityRuleType
    methodology: str
    provenance: tuple[DataProvenance, ...]
    probability_type: ProbabilityType = ProbabilityType.EXACT_MECHANICAL
    required_selection_rule: OutcomeSelectionRule | None = None
    required_outcome_space_completeness: OutcomeSpaceCompleteness = OutcomeSpaceCompleteness.COMPLETE
    expected_source_outcome_set_id: str | None = None
    expected_outcome_ids: tuple[str, ...] | None = None
    game_version: str | None = None
    crafting_dataset_version: str | None = None
    modifier_dataset_version: str | None = None
    evidence_dataset_version: str | None = None
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("analytical probability rule_id is required")
        if not self.action_id:
            raise ValueError("analytical probability rule action_id is required")
        if not self.methodology:
            raise ValueError("analytical probability rule methodology is required")
        if not self.provenance:
            raise ValueError("analytical probability rules require source provenance")
        if self.probability_type not in {ProbabilityType.EXACT_MECHANICAL, ProbabilityType.DERIVED_MECHANICAL}:
            raise ValueError("analytical probability rules must use exact or derived mechanical evidence")


class ProbabilityProvider(Protocol):
    def get_probability_model(
        self,
        item: ParsedItem,
        outcome_set: CraftOutcomeSet,
        context: ProbabilityContext | None = None,
    ) -> OutcomeProbabilityModel:
        ... 


class AnalyticalProbabilityProvider:
    """Derive probabilities only from explicit verified-mechanic rules."""

    def __init__(
        self,
        rules: tuple[AnalyticalProbabilityRule, ...] = (),
        fallback_provider: ProbabilityProvider | None = None,
    ) -> None:
        self._rules = rules
        self._fallback_provider = fallback_provider or CurrentResearchProbabilityProvider()

    def get_probability_model(
        self,
        item: ParsedItem,
        outcome_set: CraftOutcomeSet,
        context: ProbabilityContext | None = None,
    ) -> OutcomeProbabilityModel:
        context = context or ProbabilityContext()
        rule = self._find_rule(outcome_set)
        if rule is None:
            return self._fallback(
                item,
                outcome_set,
                context,
                f"No verified analytical probability rule is configured for {outcome_set.action_id}.",
            )
        incompatibilities = _analytical_rule_incompatibilities(rule, outcome_set)
        if incompatibilities:
            return self._fallback(item, outcome_set, context, *incompatibilities)
        return _analytical_model_from_rule(outcome_set, rule, context)

    def _find_rule(self, outcome_set: CraftOutcomeSet) -> AnalyticalProbabilityRule | None:
        for rule in self._rules:
            if rule.action_id == outcome_set.action_id:
                return rule
        return None

    def _fallback(
        self,
        item: ParsedItem,
        outcome_set: CraftOutcomeSet,
        context: ProbabilityContext,
        *warnings: str,
    ) -> OutcomeProbabilityModel:
        model = self._fallback_provider.get_probability_model(item, outcome_set, context)
        return OutcomeProbabilityModel(
            action_id=model.action_id,
            source_outcome_set_id=model.source_outcome_set_id,
            outcome_probabilities=model.outcome_probabilities,
            probability_completeness=model.probability_completeness,
            methodology_summary=model.methodology_summary,
            dataset_versions=model.dataset_versions,
            provenance=model.provenance,
            warnings=(*model.warnings, *warnings),
            deterministic_operations=model.deterministic_operations,
        )


class CompositeProbabilityProvider:
    """Apply probability providers in explicit precedence order.

    The first provider that returns numeric probability evidence wins. Later
    numeric models are reported as lower-precedence conflicts instead of being
    averaged or merged.
    """

    def __init__(self, providers: tuple[ProbabilityProvider, ...]) -> None:
        if not providers:
            raise ValueError("composite probability provider requires at least one provider")
        self._providers = providers

    def get_probability_model(
        self,
        item: ParsedItem,
        outcome_set: CraftOutcomeSet,
        context: ProbabilityContext | None = None,
    ) -> OutcomeProbabilityModel:
        models = tuple(provider.get_probability_model(item, outcome_set, context) for provider in self._providers)
        selected_index = next((index for index, model in enumerate(models) if _model_has_numeric_evidence(model)), len(models) - 1)
        selected = models[selected_index]
        warnings = list(selected.warnings)
        for index, model in enumerate(models):
            if index == selected_index or not _model_has_numeric_evidence(model):
                continue
            if _probability_payload(model) != _probability_payload(selected):
                warnings.append(
                    "Lower-precedence probability provider returned numeric evidence that was not selected; "
                    "probability providers are not averaged or merged."
                )
                break
        if tuple(warnings) == selected.warnings:
            return selected
        return OutcomeProbabilityModel(
            action_id=selected.action_id,
            source_outcome_set_id=selected.source_outcome_set_id,
            outcome_probabilities=selected.outcome_probabilities,
            probability_completeness=selected.probability_completeness,
            methodology_summary=selected.methodology_summary,
            dataset_versions=selected.dataset_versions,
            provenance=selected.provenance,
            warnings=tuple(warnings),
            deterministic_operations=selected.deterministic_operations,
        )


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


def _analytical_rule_incompatibilities(
    rule: AnalyticalProbabilityRule,
    outcome_set: CraftOutcomeSet,
) -> tuple[str, ...]:
    warnings: list[str] = []
    source_outcome_set_id = _outcome_set_identity(outcome_set)
    if outcome_set.outcome_space_completeness != rule.required_outcome_space_completeness:
        warnings.append(
            "Analytical probability rule was not applied because outcome-space completeness "
            f"is {outcome_set.outcome_space_completeness.value}, not {rule.required_outcome_space_completeness.value}."
        )
    if not outcome_set.hypothetical_states:
        warnings.append("Analytical probability rule was not applied because the outcome set is empty.")
    if rule.expected_source_outcome_set_id is not None and rule.expected_source_outcome_set_id != source_outcome_set_id:
        warnings.append("Analytical probability rule was not applied because the outcome-set identity changed.")
    outcome_ids = tuple(state.outcome_id for state in outcome_set.hypothetical_states)
    if len(set(outcome_ids)) != len(outcome_ids):
        warnings.append("Analytical probability rule was not applied because outcome IDs are not unique.")
    if rule.expected_outcome_ids is not None and set(rule.expected_outcome_ids) != set(outcome_ids):
        warnings.append("Analytical probability rule was not applied because enumerated outcome IDs do not match the verified rule scope.")
    definition = outcome_set.outcome_definition
    if rule.required_selection_rule is not None:
        if definition is None or definition.selection_rule != rule.required_selection_rule:
            warnings.append("Analytical probability rule was not applied because the outcome selection rule is incompatible.")
    if rule.rule_type != AnalyticalProbabilityRuleType.UNIFORM_ENUMERATED_OUTCOMES:
        warnings.append(f"Unsupported analytical probability rule type {rule.rule_type.value}.")
    return tuple(warnings)


def _analytical_model_from_rule(
    outcome_set: CraftOutcomeSet,
    rule: AnalyticalProbabilityRule,
    context: ProbabilityContext,
) -> OutcomeProbabilityModel:
    count = len(outcome_set.hypothetical_states)
    base_probability = Decimal("1") / Decimal(count)
    probabilities = [base_probability for _ in outcome_set.hypothetical_states]
    probabilities[-1] = Decimal("1") - sum(probabilities[:-1], Decimal("0"))
    outcome_probabilities = tuple(
        OutcomeProbability(
            outcome_id=state.outcome_id,
            probability=probability,
            evidence=(
                ProbabilityEvidence(
                    evidence_id=f"probability:analytical:{rule.rule_id}:{state.outcome_id}",
                    probability_type=rule.probability_type,
                    action_id=outcome_set.action_id,
                    outcome_id=state.outcome_id,
                    probability=probability,
                    methodology=rule.methodology,
                    provenance=rule.provenance,
                    retrieved_at=rule.provenance[0].retrieved_at if rule.provenance else None,
                    game_version=rule.game_version or context.game_version,
                    crafting_dataset_version=rule.crafting_dataset_version or context.crafting_dataset_version,
                    modifier_dataset_version=rule.modifier_dataset_version or context.modifier_dataset_version,
                    evidence_dataset_version=rule.evidence_dataset_version or context.evidence_dataset_version or rule.rule_id,
                    confidence=Confidence(
                        level=ConfidenceLevel.HIGH if rule.verification_status == VerificationStatus.VERIFIED else ConfidenceLevel.MEDIUM,
                        reasons=("Analytical probability derived from an explicit verified mechanic rule.",),
                    ),
                    warnings=rule.warnings,
                ),
            ),
            confidence=Confidence(
                level=ConfidenceLevel.HIGH if rule.verification_status == VerificationStatus.VERIFIED else ConfidenceLevel.MEDIUM,
                reasons=("Analytical probability derived from an explicit verified mechanic rule.",),
            ),
            warnings=rule.warnings,
        )
        for state, probability in zip(outcome_set.hypothetical_states, probabilities)
    )
    return OutcomeProbabilityModel(
        action_id=outcome_set.action_id,
        source_outcome_set_id=_outcome_set_identity(outcome_set),
        outcome_probabilities=outcome_probabilities,
        probability_completeness=ProbabilityCompleteness.COMPLETE,
        methodology_summary=f"Verified analytical mechanic model: {rule.methodology}",
        dataset_versions=tuple(
            value
            for value in (
                context.crafting_dataset_version,
                context.modifier_dataset_version,
                context.evidence_dataset_version,
                rule.crafting_dataset_version,
                rule.modifier_dataset_version,
                rule.evidence_dataset_version,
                rule.rule_id,
                *outcome_set.dataset_versions,
            )
            if value
        ),
        provenance=(*outcome_set.provenance, *rule.provenance),
        warnings=(
            "Analytical probabilities were applied from an explicit verified mechanic rule; no fallback distribution was inferred.",
            *rule.warnings,
        ),
    )


def _model_has_numeric_evidence(model: OutcomeProbabilityModel) -> bool:
    return any(item.probability is not None for item in model.outcome_probabilities)


def _probability_payload(model: OutcomeProbabilityModel) -> tuple[tuple[str, Decimal | None], ...]:
    return tuple(sorted((item.outcome_id, item.probability) for item in model.outcome_probabilities))


def _outcome_set_identity(outcome_set: CraftOutcomeSet) -> str:
    return f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}"


def _probability_decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    probability = Decimal(value)
    if probability < Decimal("0") or probability > Decimal("1"):
        raise ValueError(f"{field_name} must be between 0 and 1")
    return probability
