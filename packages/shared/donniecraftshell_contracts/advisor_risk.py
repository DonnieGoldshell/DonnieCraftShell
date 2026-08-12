"""Risk and bankroll policy layer for Advisor decisions.

Task 12B keeps raw economic ranking separate from risk-adjusted policy. It
never mutates or recalculates ExpectedValueResult.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from .advisor_decision import (
    AdvisorCandidate,
    AdvisorCandidateStatus,
    AdvisorDecision,
    AdvisorDecisionType,
)
from .domain import DataProvenance, EconomicValue
from .economy import EXALTED_ECONOMIC_UNIT, normalized_exalted_value
from .scenario_analysis import ValuationCompleteness


RISK_POLICY_VERSION = "dc-risk-policy-v1"


class RiskProfile(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"


class RiskAssessmentStatus(str, Enum):
    ACCEPTABLE = "ACCEPTABLE"
    CAUTION = "CAUTION"
    REJECTED = "REJECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class AdvisorRiskContext:
    bankroll: EconomicValue | None = None
    risk_profile: RiskProfile = RiskProfile.BALANCED
    maximum_bankroll_exposure: Decimal | None = None
    maximum_acceptable_loss: EconomicValue | None = None
    minimum_bankroll_reserve: EconomicValue | None = None
    user_overrides: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        if self.bankroll is not None:
            _require_normalized(self.bankroll, "bankroll")
            if self.bankroll.amount <= Decimal("0"):
                raise ValueError("bankroll must be positive")
        if self.maximum_acceptable_loss is not None:
            _require_normalized(self.maximum_acceptable_loss, "maximum acceptable loss")
            if self.maximum_acceptable_loss.amount < Decimal("0"):
                raise ValueError("maximum acceptable loss cannot be negative")
        if self.minimum_bankroll_reserve is not None:
            _require_normalized(self.minimum_bankroll_reserve, "minimum bankroll reserve")
            if self.minimum_bankroll_reserve.amount < Decimal("0"):
                raise ValueError("minimum bankroll reserve cannot be negative")
        if self.maximum_bankroll_exposure is not None:
            value = _decimal(self.maximum_bankroll_exposure, "maximum bankroll exposure")
            if value < Decimal("0"):
                raise ValueError("maximum bankroll exposure cannot be negative")
            object.__setattr__(self, "maximum_bankroll_exposure", value)


@dataclass(frozen=True)
class RiskPolicy:
    policy_id: str
    version: str = RISK_POLICY_VERSION
    risk_profile: RiskProfile = RiskProfile.BALANCED
    max_bankroll_exposure: Decimal | None = None
    max_downside_vs_current: EconomicValue | None = None
    minimum_bankroll_reserve: EconomicValue | None = None
    require_bankroll_for_craft_recommendation: bool = True
    reject_partial_downside: bool = False

    def __post_init__(self) -> None:
        if self.max_bankroll_exposure is not None:
            value = _decimal(self.max_bankroll_exposure, "max bankroll exposure")
            if value < Decimal("0"):
                raise ValueError("max bankroll exposure cannot be negative")
            object.__setattr__(self, "max_bankroll_exposure", value)
        if self.max_downside_vs_current is not None:
            _require_normalized(self.max_downside_vs_current, "max downside vs current")
        if self.minimum_bankroll_reserve is not None:
            _require_normalized(self.minimum_bankroll_reserve, "minimum bankroll reserve")


@dataclass(frozen=True)
class CapitalExposure:
    craft_cost: EconomicValue | None
    current_item_value: EconomicValue | None
    total_economic_exposure: EconomicValue | None
    bankroll_exposure: Decimal | None
    scenario_downside: EconomicValue | None
    downside_is_complete: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdvisorRiskAssessment:
    candidate_id: str
    status: RiskAssessmentStatus
    capital_exposure: CapitalExposure
    triggered_policy_rules: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    policy_version: str = RISK_POLICY_VERSION
    provenance: tuple[DataProvenance, ...] = ()


@dataclass(frozen=True)
class RiskAdjustedAdvisorCandidate:
    original_candidate: AdvisorCandidate
    raw_economic_rank: int | None
    risk_assessment: AdvisorRiskAssessment
    eligible_after_risk: bool
    risk_adjusted_status: RiskAssessmentStatus
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RiskAdjustedAdvisorDecision:
    raw_decision: AdvisorDecision
    risk_adjusted_decision_type: AdvisorDecisionType
    raw_winner_candidate_id: str | None
    selected_candidate_id: str | None
    risk_policy_changed_outcome: bool
    risk_adjusted_candidates: tuple[RiskAdjustedAdvisorCandidate, ...]
    decision_reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    risk_policy_id: str = ""
    risk_policy_version: str = RISK_POLICY_VERSION
    advisor_algorithm_version: str = ""
    generated_at: datetime | None = None
    provenance: tuple[DataProvenance, ...] = ()


class AdvisorRiskPolicyEngine:
    def __init__(self, policy: RiskPolicy | None = None):
        self.policy = policy

    def apply(
        self,
        raw_decision: AdvisorDecision,
        risk_context: AdvisorRiskContext | None,
        generated_at: datetime | None = None,
    ) -> RiskAdjustedAdvisorDecision:
        generated_at = generated_at or datetime.now(timezone.utc)
        if raw_decision.decision_type == AdvisorDecisionType.NO_RECOMMENDATION:
            return RiskAdjustedAdvisorDecision(
                raw_decision=raw_decision,
                risk_adjusted_decision_type=AdvisorDecisionType.NO_RECOMMENDATION,
                raw_winner_candidate_id=raw_decision.selected_candidate_id,
                selected_candidate_id=None,
                risk_policy_changed_outcome=False,
                risk_adjusted_candidates=(),
                decision_reasons=("Raw Advisor decision is NO_RECOMMENDATION; risk policy cannot promote non-rankable actions.",),
                risk_policy_id=(self.policy.policy_id if self.policy else ""),
                risk_policy_version=(self.policy.version if self.policy else RISK_POLICY_VERSION),
                advisor_algorithm_version=raw_decision.algorithm_version,
                generated_at=generated_at,
                provenance=raw_decision.provenance,
            )

        policy = self.policy or policy_for_profile(risk_context.risk_profile if risk_context else RiskProfile.BALANCED)
        if risk_context is not None:
            policy = _policy_with_context_overrides(policy, risk_context)
        risk_candidates = _raw_ranked_craft_candidates(raw_decision)
        adjusted = tuple(
            _assess_candidate(candidate, index + 1, policy, risk_context)
            for index, candidate in enumerate(risk_candidates)
        )
        sell_candidate = raw_decision.sell_now_candidate
        surviving = tuple(item for item in adjusted if item.eligible_after_risk)
        if surviving:
            selected = surviving[0].original_candidate
            return RiskAdjustedAdvisorDecision(
                raw_decision=raw_decision,
                risk_adjusted_decision_type=AdvisorDecisionType.CRAFT,
                raw_winner_candidate_id=raw_decision.selected_candidate_id,
                selected_candidate_id=selected.candidate_id,
                risk_policy_changed_outcome=selected.candidate_id != raw_decision.selected_candidate_id,
                risk_adjusted_candidates=adjusted,
                decision_reasons=(
                    f"{selected.action_id} survives {policy.risk_profile.value} risk policy without changing raw EV values.",
                ),
                risk_policy_id=policy.policy_id,
                risk_policy_version=policy.version,
                advisor_algorithm_version=raw_decision.algorithm_version,
                generated_at=generated_at,
                provenance=raw_decision.provenance,
            )
        if sell_candidate is not None and sell_candidate.rankable:
            return RiskAdjustedAdvisorDecision(
                raw_decision=raw_decision,
                risk_adjusted_decision_type=AdvisorDecisionType.SELL_NOW,
                raw_winner_candidate_id=raw_decision.selected_candidate_id,
                selected_candidate_id=sell_candidate.candidate_id,
                risk_policy_changed_outcome=raw_decision.selected_candidate_id != sell_candidate.candidate_id,
                risk_adjusted_candidates=adjusted,
                decision_reasons=("No EV-ready craft candidate survives risk policy; SELL NOW adds no new crafting capital exposure.",),
                warnings=("SELL NOW is not risk-free in absolute market terms; it adds no new craft material exposure.",),
                risk_policy_id=policy.policy_id,
                risk_policy_version=policy.version,
                advisor_algorithm_version=raw_decision.algorithm_version,
                generated_at=generated_at,
                provenance=raw_decision.provenance,
            )
        return RiskAdjustedAdvisorDecision(
            raw_decision=raw_decision,
            risk_adjusted_decision_type=AdvisorDecisionType.NO_RECOMMENDATION,
            raw_winner_candidate_id=raw_decision.selected_candidate_id,
            selected_candidate_id=None,
            risk_policy_changed_outcome=raw_decision.decision_type != AdvisorDecisionType.NO_RECOMMENDATION,
            risk_adjusted_candidates=adjusted,
            decision_reasons=("No candidate survives risk policy and SELL NOW baseline is not rankable.",),
            risk_policy_id=policy.policy_id,
            risk_policy_version=policy.version,
            advisor_algorithm_version=raw_decision.algorithm_version,
            generated_at=generated_at,
            provenance=raw_decision.provenance,
        )


def policy_for_profile(profile: RiskProfile) -> RiskPolicy:
    if profile == RiskProfile.CONSERVATIVE:
        return RiskPolicy(
            policy_id="dc-risk-policy-v1-conservative",
            risk_profile=profile,
            max_bankroll_exposure=Decimal("0.20"),
            max_downside_vs_current=None,
            reject_partial_downside=True,
        )
    if profile == RiskProfile.AGGRESSIVE:
        return RiskPolicy(
            policy_id="dc-risk-policy-v1-aggressive",
            risk_profile=profile,
            max_bankroll_exposure=Decimal("0.80"),
            max_downside_vs_current=None,
            reject_partial_downside=False,
        )
    return RiskPolicy(
        policy_id="dc-risk-policy-v1-balanced",
        risk_profile=profile,
        max_bankroll_exposure=Decimal("0.50"),
        max_downside_vs_current=None,
        reject_partial_downside=False,
    )


def _policy_with_context_overrides(policy: RiskPolicy, context: AdvisorRiskContext) -> RiskPolicy:
    return RiskPolicy(
        policy_id=policy.policy_id,
        version=policy.version,
        risk_profile=context.risk_profile,
        max_bankroll_exposure=context.maximum_bankroll_exposure if context.maximum_bankroll_exposure is not None else policy.max_bankroll_exposure,
        max_downside_vs_current=context.maximum_acceptable_loss if context.maximum_acceptable_loss is not None else policy.max_downside_vs_current,
        minimum_bankroll_reserve=context.minimum_bankroll_reserve if context.minimum_bankroll_reserve is not None else policy.minimum_bankroll_reserve,
        require_bankroll_for_craft_recommendation=policy.require_bankroll_for_craft_recommendation,
        reject_partial_downside=policy.reject_partial_downside,
    )


def _raw_ranked_craft_candidates(decision: AdvisorDecision) -> tuple[AdvisorCandidate, ...]:
    candidates = tuple(
        candidate
        for candidate in decision.craft_candidates
        if candidate.status == AdvisorCandidateStatus.RANKABLE_EV
        and candidate.expected_value_result is not None
        and candidate.expected_value_result.net_expected_value is not None
    )
    return tuple(sorted(candidates, key=lambda item: item.expected_value_result.net_expected_value.amount, reverse=True))


def _assess_candidate(
    candidate: AdvisorCandidate,
    raw_rank: int,
    policy: RiskPolicy,
    context: AdvisorRiskContext | None,
) -> RiskAdjustedAdvisorCandidate:
    exposure = _capital_exposure(candidate, context)
    triggered: list[str] = []
    reasons: list[str] = []
    warnings: list[str] = list(exposure.warnings)
    status = RiskAssessmentStatus.ACCEPTABLE
    if policy.require_bankroll_for_craft_recommendation and context is None:
        status = RiskAssessmentStatus.INSUFFICIENT_DATA
        reasons.append("Bankroll is missing; bankroll-specific risk policy cannot be evaluated.")
    elif policy.require_bankroll_for_craft_recommendation and context is not None and context.bankroll is None:
        status = RiskAssessmentStatus.INSUFFICIENT_DATA
        reasons.append("Bankroll is missing; missing bankroll is not treated as infinite bankroll.")
    if exposure.bankroll_exposure is not None and policy.max_bankroll_exposure is not None:
        if exposure.bankroll_exposure > policy.max_bankroll_exposure:
            status = RiskAssessmentStatus.REJECTED
            triggered.append("MAX_BANKROLL_EXPOSURE")
            reasons.append(
                f"Craft requires {exposure.bankroll_exposure:.2%} of available bankroll; {policy.risk_profile.value} policy permits at most {policy.max_bankroll_exposure:.2%}."
            )
    if exposure.craft_cost is not None and context is not None:
        reserve = policy.minimum_bankroll_reserve
        if reserve is not None and context.bankroll is not None and context.bankroll.amount - exposure.craft_cost.amount < reserve.amount:
            status = RiskAssessmentStatus.REJECTED
            triggered.append("MINIMUM_BANKROLL_RESERVE")
            reasons.append("Craft would violate configured minimum bankroll reserve.")
    if policy.reject_partial_downside and not exposure.downside_is_complete:
        if status == RiskAssessmentStatus.ACCEPTABLE:
            status = RiskAssessmentStatus.CAUTION
        triggered.append("PARTIAL_DOWNSIDE")
        reasons.append("Downside evidence is partial and is not treated as maximum possible loss.")
    if policy.max_downside_vs_current is not None and exposure.scenario_downside is not None:
        if exposure.scenario_downside.amount > policy.max_downside_vs_current.amount:
            status = RiskAssessmentStatus.REJECTED
            triggered.append("MAX_DOWNSIDE")
            reasons.append("Worst currently valuated scenario exceeds configured downside limit.")
    if not reasons:
        reasons.append("Candidate passes configured risk gates without changing raw EV.")
    return RiskAdjustedAdvisorCandidate(
        original_candidate=candidate,
        raw_economic_rank=raw_rank,
        risk_assessment=AdvisorRiskAssessment(
            candidate_id=candidate.candidate_id,
            status=status,
            capital_exposure=exposure,
            triggered_policy_rules=tuple(triggered),
            reasons=tuple(reasons),
            warnings=tuple(warnings),
            policy_version=policy.version,
            provenance=candidate.provenance,
        ),
        eligible_after_risk=status in {RiskAssessmentStatus.ACCEPTABLE, RiskAssessmentStatus.CAUTION},
        risk_adjusted_status=status,
        reasons=tuple(reasons),
    )


def _capital_exposure(candidate: AdvisorCandidate, context: AdvisorRiskContext | None) -> CapitalExposure:
    craft_cost = candidate.action_cost
    current_value = candidate.current_valuation.estimated_value if candidate.current_valuation else None
    total = None
    if craft_cost is not None and current_value is not None:
        total = EconomicValue(craft_cost.amount + current_value.amount, EXALTED_ECONOMIC_UNIT)
    bankroll_exposure = None
    if context is not None and context.bankroll is not None and craft_cost is not None:
        bankroll_exposure = craft_cost.amount / context.bankroll.amount
    downside = None
    complete = False
    warnings: list[str] = []
    scenario = candidate.scenario_analysis
    if scenario is not None and scenario.downside_relative_to_current is not None:
        downside_amount = abs(min(scenario.downside_relative_to_current.amount, Decimal("0")))
        downside = EconomicValue(downside_amount, EXALTED_ECONOMIC_UNIT)
        complete = scenario.valuation_completeness == ValuationCompleteness.COMPLETE
        if not complete:
            warnings.append("Downside is based on worst currently valuated scenario, not maximum possible loss.")
    return CapitalExposure(
        craft_cost=craft_cost,
        current_item_value=current_value,
        total_economic_exposure=total,
        bankroll_exposure=bankroll_exposure,
        scenario_downside=downside,
        downside_is_complete=complete,
        warnings=tuple(warnings),
    )


def _require_normalized(value: EconomicValue, field_name: str) -> None:
    if value.unit != EXALTED_ECONOMIC_UNIT:
        raise ValueError(f"{field_name} must use Exalted economic units")


def _decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    return Decimal(value)
