"""Scenario analysis and decision-readiness contracts.

This layer composes valuation, crafting candidates, outcome sets, and
probability models. It intentionally does not calculate EV, rank actions, or
recommend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from .craft_action_candidates import CraftActionCandidate
from .crafting_actions import CraftApplicabilityStatus
from .craft_outcomes import CraftOutcomeSet
from .domain import DataProvenance, EconomicValue
from .economy import normalized_exalted_value
from .probability import OutcomeProbabilityModel, ProbabilityCompleteness, can_calculate_expected_value
from .valuation import ValuationEstimateType, ValuationReadiness, ValuationResult, decimal_median


class DecisionReadiness(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    SCENARIO_ONLY = "SCENARIO_ONLY"
    EV_READY = "EV_READY"


class ValuationCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


@dataclass(frozen=True)
class OutcomeValuation:
    outcome_id: str
    valuation: ValuationResult | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioValue:
    outcome_id: str
    gross_value: EconomicValue
    net_after_action_cost: EconomicValue | None = None
    valuation_result: ValuationResult | None = None


@dataclass(frozen=True)
class ScenarioAnalysis:
    analysis_id: str
    source_item_id: str
    action_id: str
    current_valuation: ValuationResult | None
    action_material_cost: object | None
    applicability_status: CraftApplicabilityStatus
    outcome_count: int
    valued_outcome_count: int
    unvalued_outcome_count: int
    probability_completeness: ProbabilityCompleteness
    valuation_completeness: ValuationCompleteness
    decision_readiness: DecisionReadiness
    best_valuated_outcome: ScenarioValue | None = None
    worst_valuated_outcome: ScenarioValue | None = None
    median_valuated_outcome: EconomicValue | None = None
    upside_relative_to_current: EconomicValue | None = None
    downside_relative_to_current: EconomicValue | None = None
    probability_readiness: bool = False
    valuation_readiness: bool = False
    ev_readiness: bool = False
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    dataset_versions: tuple[str, ...] = ()
    economy_snapshot_ids: tuple[str, ...] = ()
    valuation_evidence_ids: tuple[str, ...] = ()
    probability_model_id: str | None = None
    outcome_set_id: str | None = None
    generated_at: datetime | None = None
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        if hasattr(self, "expected_value"):
            raise ValueError("ScenarioAnalysis must not expose expected value")


class ScenarioAnalysisService:
    def analyze_action(
        self,
        current_valuation: ValuationResult | None,
        action_candidate: CraftActionCandidate,
        outcome_set: CraftOutcomeSet,
        probability_model: OutcomeProbabilityModel,
        outcome_valuations: tuple[OutcomeValuation, ...],
        generated_at: datetime | None = None,
    ) -> ScenarioAnalysis:
        generated_at = generated_at or datetime.now(timezone.utc)
        usable = _usable_outcome_valuations(outcome_valuations)
        values = tuple(item.valuation.estimated_value.amount for item in usable)
        outcome_count = len(outcome_set.hypothetical_states)
        valued_count = len(usable)
        unvalued_count = max(outcome_count - valued_count, 0)
        valuation_completeness = _valuation_completeness(outcome_count, valued_count)
        probability_ready = can_calculate_expected_value(probability_model)
        current_ready = _valuation_is_usable(current_valuation)
        cost_ready = action_candidate.material_cost.complete and action_candidate.material_cost.total is not None
        valuation_ready = current_ready and valuation_completeness == ValuationCompleteness.COMPLETE
        ev_ready = (
            action_candidate.applicability.status == CraftApplicabilityStatus.APPLICABLE
            and cost_ready
            and probability_ready
            and valuation_ready
            and _probability_outcomes_are_valued(probability_model, usable)
        )
        readiness, reasons = _decision_readiness(
            action_candidate,
            outcome_count,
            valued_count,
            probability_ready,
            valuation_ready,
            cost_ready,
            ev_ready,
            current_ready,
        )
        scenario_values = tuple(_scenario_value(item, action_candidate) for item in usable)
        best = max(scenario_values, key=lambda item: item.gross_value.amount, default=None)
        worst = min(scenario_values, key=lambda item: item.gross_value.amount, default=None)
        median = normalized_exalted_value(decimal_median(values)) if values else None
        warnings = list(action_candidate.warnings)
        warnings.extend(outcome_set.warnings)
        warnings.extend(probability_model.warnings)
        warnings.extend(warning for item in outcome_valuations for warning in item.warnings)
        if unvalued_count:
            warnings.append("Best, worst, and median scenarios use valuated outcomes only; unvalued outcomes remain explicit.")
        if probability_model.probability_completeness != ProbabilityCompleteness.COMPLETE:
            warnings.append("Scenario statistics are descriptive only because probability completeness is not COMPLETE.")
        if readiness == DecisionReadiness.EV_READY:
            warnings.append("EV readiness is true, but Task 11A intentionally does not calculate EV.")

        current_amount = current_valuation.estimated_value.amount if current_ready and current_valuation is not None else None
        return ScenarioAnalysis(
            analysis_id=_analysis_id(outcome_set, probability_model, action_candidate),
            source_item_id=outcome_set.source_item_analysis_id,
            action_id=action_candidate.action.action_id,
            current_valuation=current_valuation,
            action_material_cost=action_candidate.material_cost,
            applicability_status=action_candidate.applicability.status,
            outcome_count=outcome_count,
            valued_outcome_count=valued_count,
            unvalued_outcome_count=unvalued_count,
            probability_completeness=probability_model.probability_completeness,
            valuation_completeness=valuation_completeness,
            decision_readiness=readiness,
            best_valuated_outcome=best,
            worst_valuated_outcome=worst,
            median_valuated_outcome=median,
            upside_relative_to_current=_delta(best.gross_value.amount, current_amount) if best and current_amount is not None else None,
            downside_relative_to_current=_delta(worst.gross_value.amount, current_amount) if worst and current_amount is not None else None,
            probability_readiness=probability_ready,
            valuation_readiness=valuation_ready,
            ev_readiness=ev_ready,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
            dataset_versions=tuple(sorted({*outcome_set.dataset_versions, *probability_model.dataset_versions})),
            economy_snapshot_ids=_economy_snapshot_ids(current_valuation, tuple(item.valuation for item in usable), action_candidate),
            valuation_evidence_ids=_valuation_evidence_ids(current_valuation, tuple(item.valuation for item in usable)),
            probability_model_id=probability_model.source_outcome_set_id,
            outcome_set_id=f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}",
            generated_at=generated_at,
            provenance=outcome_set.provenance + probability_model.provenance,
        )

    def analyze_candidates(
        self,
        analyses: tuple[tuple[ValuationResult | None, CraftActionCandidate, CraftOutcomeSet, OutcomeProbabilityModel, tuple[OutcomeValuation, ...]], ...],
        generated_at: datetime | None = None,
    ) -> tuple[ScenarioAnalysis, ...]:
        return tuple(
            self.analyze_action(current, candidate, outcomes, probabilities, valuations, generated_at)
            for current, candidate, outcomes, probabilities, valuations in analyses
        )


def _usable_outcome_valuations(outcome_valuations: tuple[OutcomeValuation, ...]) -> tuple[OutcomeValuation, ...]:
    return tuple(
        item
        for item in outcome_valuations
        if item.valuation is not None and _valuation_is_usable(item.valuation)
    )


def _valuation_is_usable(valuation: ValuationResult | None) -> bool:
    return (
        valuation is not None
        and valuation.estimate_type == ValuationEstimateType.LISTING_DERIVED
        and valuation.estimated_value is not None
        and valuation.readiness in {ValuationReadiness.READY, ValuationReadiness.PARTIAL}
    )


def _valuation_completeness(outcome_count: int, valued_count: int) -> ValuationCompleteness:
    if valued_count == 0:
        return ValuationCompleteness.NONE
    if valued_count == outcome_count:
        return ValuationCompleteness.COMPLETE
    return ValuationCompleteness.PARTIAL


def _probability_outcomes_are_valued(
    probability_model: OutcomeProbabilityModel,
    usable: tuple[OutcomeValuation, ...],
) -> bool:
    valued_ids = {item.outcome_id for item in usable}
    probability_ids = {item.outcome_id for item in probability_model.outcome_probabilities}
    return bool(probability_ids) and probability_ids.issubset(valued_ids)


def _decision_readiness(
    action_candidate: CraftActionCandidate,
    outcome_count: int,
    valued_count: int,
    probability_ready: bool,
    valuation_ready: bool,
    cost_ready: bool,
    ev_ready: bool,
    current_ready: bool,
) -> tuple[DecisionReadiness, tuple[str, ...]]:
    reasons: list[str] = []
    if action_candidate.applicability.status == CraftApplicabilityStatus.NOT_APPLICABLE:
        reasons.append("Action applicability is NOT_APPLICABLE.")
        return DecisionReadiness.NOT_APPLICABLE, tuple(reasons)
    if valued_count == 0:
        reasons.append("No usable outcome valuations are available.")
        return DecisionReadiness.INSUFFICIENT_DATA, tuple(reasons)
    if ev_ready:
        reasons.extend(
            (
                "Action is APPLICABLE.",
                "Action cost is complete.",
                "Probability model is COMPLETE with valid mass.",
                "Current and outcome valuations are complete enough for future EV calculation.",
            )
        )
        return DecisionReadiness.EV_READY, tuple(reasons)
    reasons.append(f"Valuation coverage is {valued_count}/{outcome_count}.")
    if not probability_ready:
        reasons.append("Probability model is not EV-ready.")
    if not valuation_ready:
        reasons.append("Valuation inputs are not complete enough for EV.")
    if not cost_ready:
        reasons.append("Action material cost is incomplete.")
    if not current_ready:
        reasons.append("Current item listing-derived valuation is unavailable.")
    return DecisionReadiness.SCENARIO_ONLY, tuple(reasons)


def _scenario_value(item: OutcomeValuation, action_candidate: CraftActionCandidate) -> ScenarioValue:
    assert item.valuation is not None
    assert item.valuation.estimated_value is not None
    cost = action_candidate.material_cost.total.amount if action_candidate.material_cost.total is not None else None
    net = _delta(item.valuation.estimated_value.amount, cost) if cost is not None else None
    return ScenarioValue(
        outcome_id=item.outcome_id,
        gross_value=item.valuation.estimated_value,
        net_after_action_cost=net,
        valuation_result=item.valuation,
    )


def _delta(left: Decimal, right: Decimal | None) -> EconomicValue | None:
    if right is None:
        return None
    return EconomicValue(left - right, "EXALTED_ECONOMIC_UNIT")


def _economy_snapshot_ids(
    current_valuation: ValuationResult | None,
    outcome_valuations: tuple[ValuationResult, ...],
    action_candidate: CraftActionCandidate,
) -> tuple[str, ...]:
    ids = set(current_valuation.economy_snapshot_ids if current_valuation else ())
    for valuation in outcome_valuations:
        ids.update(valuation.economy_snapshot_ids)
    for line in action_candidate.material_cost.lines:
        if line.quote is not None:
            ids.add(line.quote.snapshot_id)
    return tuple(sorted(ids))


def _valuation_evidence_ids(
    current_valuation: ValuationResult | None,
    outcome_valuations: tuple[ValuationResult, ...],
) -> tuple[str, ...]:
    ids = set(current_valuation.source_evidence_ids if current_valuation else ())
    for valuation in outcome_valuations:
        ids.update(valuation.source_evidence_ids)
    return tuple(sorted(ids))


def _analysis_id(
    outcome_set: CraftOutcomeSet,
    probability_model: OutcomeProbabilityModel,
    action_candidate: CraftActionCandidate,
) -> str:
    return f"scenario:{outcome_set.source_item_analysis_id}:{action_candidate.action.action_id}:{probability_model.source_outcome_set_id}"
