"""Strict Expected Value calculation contracts.

Task 11B calculates EV only for scenario analyses that are already EV_READY.
It does not rank actions, recommend, estimate probabilities, or fill missing
valuations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from .domain import DataProvenance, EconomicValue
from .economy import EXALTED_ECONOMIC_UNIT
from .probability import PROBABILITY_MASS_TOLERANCE, OutcomeProbabilityModel, ProbabilityCompleteness
from .scenario_analysis import DecisionReadiness, OutcomeValuation, ScenarioAnalysis
from .valuation import ValuationResult


EXPECTED_VALUE_ALGORITHM_VERSION = "dc-ev-v1"


class ExpectedValueStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class OutcomeExpectedValueContribution:
    outcome_id: str
    probability: Decimal
    valuation: EconomicValue
    weighted_contribution: EconomicValue
    valuation_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        probability = _decimal(self.probability, "outcome probability")
        if probability < Decimal("0") or probability > Decimal("1"):
            raise ValueError("outcome probability must be between 0 and 1")
        _require_normalized(self.valuation, "outcome valuation")
        _require_normalized(self.weighted_contribution, "weighted contribution")
        object.__setattr__(self, "probability", probability)


@dataclass(frozen=True)
class ExpectedValueResult:
    status: ExpectedValueStatus
    result_id: str
    action_id: str
    scenario_analysis_id: str
    source_item_id: str
    gross_expected_outcome_value: EconomicValue | None = None
    craft_cost: EconomicValue | None = None
    net_expected_value: EconomicValue | None = None
    current_item_value: EconomicValue | None = None
    expected_gain_vs_sell_now: EconomicValue | None = None
    roi_on_craft_cost: Decimal | None = None
    low_net_expected_value: EconomicValue | None = None
    high_net_expected_value: EconomicValue | None = None
    outcome_contributions: tuple[OutcomeExpectedValueContribution, ...] = ()
    probability_model_id: str | None = None
    valuation_evidence_ids: tuple[str, ...] = ()
    economy_snapshot_ids: tuple[str, ...] = ()
    dataset_versions: tuple[str, ...] = ()
    methodology_version: str = EXPECTED_VALUE_ALGORITHM_VERSION
    warnings: tuple[str, ...] = ()
    unavailable_reasons: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    calculated_at: datetime | None = None

    @property
    def available(self) -> bool:
        return self.status == ExpectedValueStatus.AVAILABLE


class ExpectedValueEngine:
    def calculate(
        self,
        scenario_analysis: ScenarioAnalysis,
        probability_model: OutcomeProbabilityModel,
        outcome_valuations: tuple[OutcomeValuation, ...],
        calculated_at: datetime | None = None,
    ) -> ExpectedValueResult:
        calculated_at = calculated_at or datetime.now(timezone.utc)
        unavailable = _readiness_failures(scenario_analysis, probability_model, outcome_valuations)
        common = {
            "result_id": f"ev:{scenario_analysis.analysis_id}:{EXPECTED_VALUE_ALGORITHM_VERSION}",
            "action_id": scenario_analysis.action_id,
            "scenario_analysis_id": scenario_analysis.analysis_id,
            "source_item_id": scenario_analysis.source_item_id,
            "probability_model_id": probability_model.source_outcome_set_id,
            "valuation_evidence_ids": scenario_analysis.valuation_evidence_ids,
            "economy_snapshot_ids": scenario_analysis.economy_snapshot_ids,
            "dataset_versions": scenario_analysis.dataset_versions,
            "provenance": scenario_analysis.provenance,
            "calculated_at": calculated_at,
        }
        if unavailable:
            return ExpectedValueResult(
                status=ExpectedValueStatus.NOT_AVAILABLE,
                warnings=("EV calculation refused; prerequisites are incomplete or invalid.",),
                unavailable_reasons=tuple(unavailable),
                **common,
            )

        valuation_by_outcome = {item.outcome_id: item.valuation for item in outcome_valuations if item.valuation is not None}
        contributions = []
        gross = Decimal("0")
        low_gross = Decimal("0")
        high_gross = Decimal("0")
        bounds_available = True
        for outcome_probability in probability_model.outcome_probabilities:
            assert outcome_probability.probability is not None
            valuation = valuation_by_outcome[outcome_probability.outcome_id]
            assert valuation.estimated_value is not None
            _require_normalized(valuation.estimated_value, "outcome valuation")
            weighted = outcome_probability.probability * valuation.estimated_value.amount
            gross += weighted
            contributions.append(
                OutcomeExpectedValueContribution(
                    outcome_id=outcome_probability.outcome_id,
                    probability=outcome_probability.probability,
                    valuation=valuation.estimated_value,
                    weighted_contribution=EconomicValue(weighted, EXALTED_ECONOMIC_UNIT),
                    valuation_evidence_ids=valuation.source_evidence_ids,
                )
            )
            if valuation.plausible_low is None or valuation.plausible_high is None:
                bounds_available = False
            else:
                _require_normalized(valuation.plausible_low, "outcome plausible low")
                _require_normalized(valuation.plausible_high, "outcome plausible high")
                low_gross += outcome_probability.probability * valuation.plausible_low.amount
                high_gross += outcome_probability.probability * valuation.plausible_high.amount

        contribution_sum = sum((item.weighted_contribution.amount for item in contributions), Decimal("0"))
        if abs(contribution_sum - gross) > PROBABILITY_MASS_TOLERANCE:
            return ExpectedValueResult(
                status=ExpectedValueStatus.NOT_AVAILABLE,
                warnings=("EV calculation refused; contribution sum invariant failed.",),
                unavailable_reasons=("Outcome contribution sum does not match gross EV.",),
                **common,
            )

        assert scenario_analysis.action_material_cost is not None
        craft_cost = scenario_analysis.action_material_cost.total
        assert craft_cost is not None
        current_value = scenario_analysis.current_valuation.estimated_value
        assert current_value is not None
        _require_normalized(craft_cost, "craft cost")
        _require_normalized(current_value, "current item value")
        net = gross - craft_cost.amount
        gain = net - current_value.amount
        roi = None if craft_cost.amount == Decimal("0") else gain / craft_cost.amount
        return ExpectedValueResult(
            status=ExpectedValueStatus.AVAILABLE,
            gross_expected_outcome_value=EconomicValue(gross, EXALTED_ECONOMIC_UNIT),
            craft_cost=craft_cost,
            net_expected_value=EconomicValue(net, EXALTED_ECONOMIC_UNIT),
            current_item_value=current_value,
            expected_gain_vs_sell_now=EconomicValue(gain, EXALTED_ECONOMIC_UNIT),
            roi_on_craft_cost=roi,
            low_net_expected_value=EconomicValue(low_gross - craft_cost.amount, EXALTED_ECONOMIC_UNIT) if bounds_available else None,
            high_net_expected_value=EconomicValue(high_gross - craft_cost.amount, EXALTED_ECONOMIC_UNIT) if bounds_available else None,
            outcome_contributions=tuple(contributions),
            warnings=(
                "Expected Gain vs Sell Now uses listing-derived current valuation, not guaranteed realized profit.",
                "No recommendation or action ranking is produced.",
            ),
            **common,
        )


def _readiness_failures(
    scenario_analysis: ScenarioAnalysis,
    probability_model: OutcomeProbabilityModel,
    outcome_valuations: tuple[OutcomeValuation, ...],
) -> list[str]:
    failures: list[str] = []
    if scenario_analysis.decision_readiness != DecisionReadiness.EV_READY or not scenario_analysis.ev_readiness:
        failures.append("ScenarioAnalysis is not EV_READY.")
    if scenario_analysis.current_valuation is None or scenario_analysis.current_valuation.estimated_value is None:
        failures.append("Current item valuation is missing.")
    elif not _is_normalized(scenario_analysis.current_valuation.estimated_value):
        failures.append("Current item valuation is not normalized in Exalted economic units.")
    cost = getattr(scenario_analysis.action_material_cost, "total", None)
    complete = getattr(scenario_analysis.action_material_cost, "complete", False)
    if not complete or cost is None:
        failures.append("Craft material cost is incomplete.")
    elif not _is_normalized(cost):
        failures.append("Craft material cost is not normalized in Exalted economic units.")
    if probability_model.probability_completeness != ProbabilityCompleteness.COMPLETE:
        failures.append("Probability model is not COMPLETE.")
    if probability_model.total_known_probability_mass is None or abs(probability_model.total_known_probability_mass - Decimal("1")) > PROBABILITY_MASS_TOLERANCE:
        failures.append("Probability mass is not valid for EV.")
    if any(item.probability is None for item in probability_model.outcome_probabilities):
        failures.append("One or more probability-bearing outcomes has missing probability.")
    valuation_by_outcome = {item.outcome_id: item.valuation for item in outcome_valuations if item.valuation is not None}
    probability_ids = {item.outcome_id for item in probability_model.outcome_probabilities}
    valuation_ids = set(valuation_by_outcome)
    if probability_ids != valuation_ids:
        failures.append("Outcome IDs do not align exactly between probability model and valuations.")
    for outcome_id, valuation in valuation_by_outcome.items():
        if valuation.estimated_value is None:
            failures.append(f"Outcome valuation missing estimated value for {outcome_id}.")
        elif not _is_normalized(valuation.estimated_value):
            failures.append(f"Outcome valuation is not normalized for {outcome_id}.")
    if not scenario_analysis.dataset_versions:
        failures.append("ScenarioAnalysis has no dataset version references.")
    if not scenario_analysis.economy_snapshot_ids:
        failures.append("ScenarioAnalysis has no economy snapshot references.")
    if not scenario_analysis.valuation_evidence_ids:
        failures.append("ScenarioAnalysis has no valuation evidence references.")
    if not probability_model.source_outcome_set_id:
        failures.append("Probability model identity is missing.")
    return failures


def _is_normalized(value: EconomicValue) -> bool:
    return value.unit == EXALTED_ECONOMIC_UNIT


def _require_normalized(value: EconomicValue, field_name: str) -> None:
    if not _is_normalized(value):
        raise ValueError(f"{field_name} must use Exalted economic units")


def _decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    return Decimal(value)
