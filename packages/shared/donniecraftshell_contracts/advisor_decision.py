"""Conservative Advisor decision contracts.

Task 12A compares SELL NOW with craft candidates using only defensible EV
results. Scenario-only actions remain visible but non-rankable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from .craft_action_candidates import CraftActionCandidate
from .crafting_actions import CraftApplicabilityStatus
from .domain import Confidence, ConfidenceLevel, DataProvenance, EconomicValue
from .economy import EXALTED_ECONOMIC_UNIT, normalized_exalted_value
from .expected_value import ExpectedValueResult, ExpectedValueStatus
from .scenario_analysis import DecisionReadiness, ScenarioAnalysis
from .valuation import ValuationEstimateType, ValuationReadiness, ValuationResult


ADVISOR_ALGORITHM_VERSION = "dc-advisor-v1"


class AdvisorDecisionType(str, Enum):
    SELL_NOW = "SELL_NOW"
    CRAFT = "CRAFT"
    NO_RECOMMENDATION = "NO_RECOMMENDATION"


class AdvisorCandidateType(str, Enum):
    SELL_NOW = "SELL_NOW"
    CRAFT_ACTION = "CRAFT_ACTION"


class AdvisorCandidateStatus(str, Enum):
    RANKABLE_BASELINE = "RANKABLE_BASELINE"
    RANKABLE_EV = "RANKABLE_EV"
    NON_RANKABLE_SCENARIO = "NON_RANKABLE_SCENARIO"
    NON_RANKABLE_NOT_APPLICABLE = "NON_RANKABLE_NOT_APPLICABLE"
    NON_RANKABLE_INSUFFICIENT_DATA = "NON_RANKABLE_INSUFFICIENT_DATA"
    NON_RANKABLE_UNKNOWN = "NON_RANKABLE_UNKNOWN"


@dataclass(frozen=True)
class AdvisorPolicy:
    policy_id: str = "advisor-policy-task12a-default"
    algorithm_version: str = ADVISOR_ALGORITHM_VERSION
    minimum_expected_gain_absolute: Decimal = Decimal("0")
    minimum_expected_gain_relative: Decimal = Decimal("0")
    allow_sell_without_ev_ready_craft: bool = False
    require_ready_current_valuation: bool = True

    def __post_init__(self) -> None:
        for field_name in ("minimum_expected_gain_absolute", "minimum_expected_gain_relative"):
            value = _decimal(getattr(self, field_name), field_name)
            if value < Decimal("0"):
                raise ValueError(f"{field_name} cannot be negative")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True)
class AdvisorRiskContext:
    bankroll: EconomicValue | None = None
    risk_profile: str | None = None
    max_acceptable_loss: EconomicValue | None = None


@dataclass(frozen=True)
class AdvisorCraftInput:
    action_candidate: CraftActionCandidate
    scenario_analysis: ScenarioAnalysis | None = None
    expected_value_result: ExpectedValueResult | None = None


@dataclass(frozen=True)
class AdvisorCandidate:
    candidate_id: str
    candidate_type: AdvisorCandidateType
    status: AdvisorCandidateStatus
    action_id: str | None = None
    applicability: CraftApplicabilityStatus | None = None
    scenario_readiness: DecisionReadiness | None = None
    expected_value_result: ExpectedValueResult | None = None
    current_valuation: ValuationResult | None = None
    baseline_value: EconomicValue | None = None
    action_cost: EconomicValue | None = None
    expected_gain_vs_sell_now: EconomicValue | None = None
    roi_on_craft_cost: Decimal | None = None
    valuation_confidence: Confidence | None = None
    probability_status: str | None = None
    economy_snapshot_ids: tuple[str, ...] = ()
    bankroll_exposure: Decimal | None = None
    warnings: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()

    @property
    def rankable(self) -> bool:
        return self.status in {AdvisorCandidateStatus.RANKABLE_BASELINE, AdvisorCandidateStatus.RANKABLE_EV}


@dataclass(frozen=True)
class AdvisorDecision:
    decision_id: str
    decision_type: AdvisorDecisionType
    selected_candidate_id: str | None
    sell_now_candidate: AdvisorCandidate | None
    craft_candidates: tuple[AdvisorCandidate, ...]
    rankable_candidates: tuple[AdvisorCandidate, ...]
    non_rankable_candidates: tuple[AdvisorCandidate, ...]
    decision_confidence: Confidence | None
    decision_reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    current_valuation_reference: tuple[str, ...] = ()
    generated_at: datetime | None = None
    provenance: tuple[DataProvenance, ...] = ()
    dataset_versions: tuple[str, ...] = ()
    economy_snapshot_ids: tuple[str, ...] = ()
    advisor_policy_id: str = "advisor-policy-task12a-default"
    algorithm_version: str = ADVISOR_ALGORITHM_VERSION


class AdvisorDecisionEngine:
    def __init__(self, policy: AdvisorPolicy | None = None):
        self.policy = policy or AdvisorPolicy()

    def decide(
        self,
        current_valuation: ValuationResult | None,
        craft_inputs: tuple[AdvisorCraftInput, ...],
        risk_context: AdvisorRiskContext | None = None,
        generated_at: datetime | None = None,
    ) -> AdvisorDecision:
        generated_at = generated_at or datetime.now(timezone.utc)
        sell_candidate = _sell_now_candidate(current_valuation, self.policy)
        craft_candidates = tuple(_craft_candidate(item, current_valuation, risk_context) for item in craft_inputs)
        all_candidates = ((sell_candidate,) if sell_candidate else ()) + craft_candidates
        rankable = tuple(candidate for candidate in all_candidates if candidate.rankable)
        non_rankable = tuple(candidate for candidate in all_candidates if not candidate.rankable)
        warnings = tuple(warning for candidate in all_candidates for warning in candidate.warnings)
        economy_ids = tuple(sorted({snapshot for candidate in all_candidates for snapshot in candidate.economy_snapshot_ids}))
        dataset_versions = tuple(
            sorted(
                {
                    version
                    for item in craft_inputs
                    for version in (
                        item.scenario_analysis.dataset_versions if item.scenario_analysis is not None else ()
                    )
                }
            )
        )

        current_ready = sell_candidate is not None and sell_candidate.status == AdvisorCandidateStatus.RANKABLE_BASELINE
        if not current_ready:
            return _decision(
                AdvisorDecisionType.NO_RECOMMENDATION,
                None,
                sell_candidate,
                craft_candidates,
                rankable,
                non_rankable,
                ("Current listing-derived valuation is not ready enough for a defensible SELL NOW baseline.",),
                warnings,
                current_valuation,
                generated_at,
                dataset_versions,
                economy_ids,
                self.policy,
            )

        ev_candidates = tuple(candidate for candidate in craft_candidates if candidate.status == AdvisorCandidateStatus.RANKABLE_EV)
        if not ev_candidates:
            if self.policy.allow_sell_without_ev_ready_craft:
                return _decision(
                    AdvisorDecisionType.SELL_NOW,
                    sell_candidate.candidate_id,
                    sell_candidate,
                    craft_candidates,
                    rankable,
                    non_rankable,
                    ("No EV-ready craft candidate is available; SELL NOW is the only rankable economic candidate.",),
                    warnings,
                    current_valuation,
                    generated_at,
                    dataset_versions,
                    economy_ids,
                    self.policy,
                )
            return _decision(
                AdvisorDecisionType.NO_RECOMMENDATION,
                None,
                sell_candidate,
                craft_candidates,
                rankable,
                non_rankable,
                ("All available craft actions are non-rankable because EV evidence is incomplete or unavailable.",),
                warnings,
                current_valuation,
                generated_at,
                dataset_versions,
                economy_ids,
                self.policy,
            )

        best_craft = max(ev_candidates, key=lambda candidate: candidate.expected_value_result.net_expected_value.amount)
        assert best_craft.expected_value_result is not None
        assert best_craft.expected_gain_vs_sell_now is not None
        margin = _required_margin(sell_candidate.baseline_value, self.policy)
        if best_craft.expected_gain_vs_sell_now.amount >= margin:
            return _decision(
                AdvisorDecisionType.CRAFT,
                best_craft.candidate_id,
                sell_candidate,
                craft_candidates,
                rankable,
                non_rankable,
                (
                    f"{best_craft.action_id} has a net expected value {best_craft.expected_gain_vs_sell_now.amount} Ex above the current listing-derived item valuation.",
                    "Only EV-ready craft candidates participated in ranking.",
                ),
                warnings,
                current_valuation,
                generated_at,
                dataset_versions,
                economy_ids,
                self.policy,
            )
        return _decision(
            AdvisorDecisionType.SELL_NOW,
            sell_candidate.candidate_id,
            sell_candidate,
            craft_candidates,
            rankable,
            non_rankable,
            ("No EV-ready craft exceeds the current listing-derived item valuation by the configured decision margin.",),
            warnings,
            current_valuation,
            generated_at,
            dataset_versions,
            economy_ids,
            self.policy,
        )


def _sell_now_candidate(current_valuation: ValuationResult | None, policy: AdvisorPolicy) -> AdvisorCandidate | None:
    if current_valuation is None:
        return None
    warnings = list(current_valuation.warnings)
    usable = (
        current_valuation.estimate_type == ValuationEstimateType.LISTING_DERIVED
        and current_valuation.estimated_value is not None
        and current_valuation.readiness in {ValuationReadiness.READY, ValuationReadiness.PARTIAL}
    )
    rankable = usable and (current_valuation.readiness == ValuationReadiness.READY or not policy.require_ready_current_valuation)
    status = AdvisorCandidateStatus.RANKABLE_BASELINE if rankable else AdvisorCandidateStatus.NON_RANKABLE_INSUFFICIENT_DATA
    if not rankable:
        warnings.append("SELL NOW baseline is visible but not rankable because current valuation readiness is insufficient.")
    return AdvisorCandidate(
        candidate_id="advisor-candidate:sell-now",
        candidate_type=AdvisorCandidateType.SELL_NOW,
        status=status,
        current_valuation=current_valuation,
        baseline_value=current_valuation.estimated_value if usable else None,
        action_cost=normalized_exalted_value(Decimal("0")),
        valuation_confidence=current_valuation.confidence,
        economy_snapshot_ids=current_valuation.economy_snapshot_ids,
        warnings=tuple(warnings),
        provenance=current_valuation.provenance,
    )


def _craft_candidate(
    item: AdvisorCraftInput,
    current_valuation: ValuationResult | None,
    risk_context: AdvisorRiskContext | None,
) -> AdvisorCandidate:
    action_candidate = item.action_candidate
    scenario = item.scenario_analysis
    ev = item.expected_value_result
    status = _craft_status(action_candidate, scenario, ev)
    warnings = list(action_candidate.warnings)
    if scenario is not None:
        warnings.extend(scenario.warnings)
    if ev is not None:
        warnings.extend(ev.warnings)
    if status != AdvisorCandidateStatus.RANKABLE_EV:
        warnings.append(_non_rankable_warning(status))
    action_cost = action_candidate.material_cost.total
    exposure = None
    if risk_context is not None and risk_context.bankroll is not None and action_cost is not None and risk_context.bankroll.amount > Decimal("0"):
        exposure = action_cost.amount / risk_context.bankroll.amount
    economy_snapshot_ids = {
        line.quote.snapshot_id
        for line in action_candidate.material_cost.lines
        if line.quote is not None
    }
    if scenario is not None:
        economy_snapshot_ids.update(scenario.economy_snapshot_ids)
    if ev is not None:
        economy_snapshot_ids.update(ev.economy_snapshot_ids)
    return AdvisorCandidate(
        candidate_id=f"advisor-candidate:craft:{action_candidate.action.action_id}",
        candidate_type=AdvisorCandidateType.CRAFT_ACTION,
        status=status,
        action_id=action_candidate.action.action_id,
        applicability=action_candidate.applicability.status,
        scenario_readiness=scenario.decision_readiness if scenario is not None else None,
        expected_value_result=ev,
        current_valuation=current_valuation,
        action_cost=action_cost,
        expected_gain_vs_sell_now=ev.expected_gain_vs_sell_now if ev and ev.status == ExpectedValueStatus.AVAILABLE else None,
        roi_on_craft_cost=ev.roi_on_craft_cost if ev and ev.status == ExpectedValueStatus.AVAILABLE else None,
        probability_status=scenario.probability_completeness.value if scenario is not None else None,
        economy_snapshot_ids=tuple(sorted(economy_snapshot_ids)),
        bankroll_exposure=exposure,
        warnings=tuple(warnings),
        provenance=action_candidate.applicability.provenance,
    )


def _craft_status(
    action_candidate: CraftActionCandidate,
    scenario: ScenarioAnalysis | None,
    ev: ExpectedValueResult | None,
) -> AdvisorCandidateStatus:
    if action_candidate.applicability.status == CraftApplicabilityStatus.NOT_APPLICABLE:
        return AdvisorCandidateStatus.NON_RANKABLE_NOT_APPLICABLE
    if action_candidate.applicability.status == CraftApplicabilityStatus.UNKNOWN:
        return AdvisorCandidateStatus.NON_RANKABLE_UNKNOWN
    if scenario is None:
        return AdvisorCandidateStatus.NON_RANKABLE_INSUFFICIENT_DATA
    if scenario.decision_readiness == DecisionReadiness.SCENARIO_ONLY:
        return AdvisorCandidateStatus.NON_RANKABLE_SCENARIO
    if scenario.decision_readiness == DecisionReadiness.NOT_APPLICABLE:
        return AdvisorCandidateStatus.NON_RANKABLE_NOT_APPLICABLE
    if scenario.decision_readiness == DecisionReadiness.INSUFFICIENT_DATA:
        return AdvisorCandidateStatus.NON_RANKABLE_INSUFFICIENT_DATA
    if (
        scenario.decision_readiness == DecisionReadiness.EV_READY
        and ev is not None
        and ev.status == ExpectedValueStatus.AVAILABLE
        and ev.expected_gain_vs_sell_now is not None
        and ev.net_expected_value is not None
    ):
        return AdvisorCandidateStatus.RANKABLE_EV
    return AdvisorCandidateStatus.NON_RANKABLE_INSUFFICIENT_DATA


def _non_rankable_warning(status: AdvisorCandidateStatus) -> str:
    return {
        AdvisorCandidateStatus.NON_RANKABLE_SCENARIO: "Scenario-only action is informative but cannot enter EV ranking.",
        AdvisorCandidateStatus.NON_RANKABLE_NOT_APPLICABLE: "Action is not applicable and cannot enter ranking.",
        AdvisorCandidateStatus.NON_RANKABLE_UNKNOWN: "Action applicability is unknown and cannot enter ranking.",
        AdvisorCandidateStatus.NON_RANKABLE_INSUFFICIENT_DATA: "Action lacks complete EV evidence and cannot enter ranking.",
    }.get(status, "Candidate is non-rankable.")


def _required_margin(baseline: EconomicValue | None, policy: AdvisorPolicy) -> Decimal:
    if baseline is None:
        return Decimal("Infinity")
    relative = baseline.amount * policy.minimum_expected_gain_relative
    return max(policy.minimum_expected_gain_absolute, relative)


def _decision(
    decision_type: AdvisorDecisionType,
    selected_candidate_id: str | None,
    sell_candidate: AdvisorCandidate | None,
    craft_candidates: tuple[AdvisorCandidate, ...],
    rankable: tuple[AdvisorCandidate, ...],
    non_rankable: tuple[AdvisorCandidate, ...],
    reasons: tuple[str, ...],
    warnings: tuple[str, ...],
    current_valuation: ValuationResult | None,
    generated_at: datetime,
    dataset_versions: tuple[str, ...],
    economy_snapshot_ids: tuple[str, ...],
    policy: AdvisorPolicy,
) -> AdvisorDecision:
    confidence = Confidence(level=ConfidenceLevel.MEDIUM if decision_type != AdvisorDecisionType.NO_RECOMMENDATION else ConfidenceLevel.LOW, reasons=reasons)
    return AdvisorDecision(
        decision_id=f"advisor-decision:{policy.algorithm_version}:{generated_at.isoformat()}",
        decision_type=decision_type,
        selected_candidate_id=selected_candidate_id,
        sell_now_candidate=sell_candidate,
        craft_candidates=craft_candidates,
        rankable_candidates=rankable,
        non_rankable_candidates=non_rankable,
        decision_confidence=confidence,
        decision_reasons=reasons,
        warnings=warnings,
        current_valuation_reference=current_valuation.source_evidence_ids if current_valuation else (),
        generated_at=generated_at,
        provenance=current_valuation.provenance if current_valuation else (),
        dataset_versions=dataset_versions,
        economy_snapshot_ids=economy_snapshot_ids,
        advisor_policy_id=policy.policy_id,
        algorithm_version=policy.algorithm_version,
    )


def _decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    return Decimal(value)
