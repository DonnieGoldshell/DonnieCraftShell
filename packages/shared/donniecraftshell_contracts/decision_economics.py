"""Forward sell-now versus continue-crafting decision economics.

This module composes existing market valuation authority and Advisor/EV
results. It does not calculate EV, infer probabilities, aggregate valuations,
or reconstruct historical investment spend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .advisor_decision import AdvisorCandidate, AdvisorCandidateStatus, AdvisorDecision, AdvisorDecisionType
from .advisor_risk import RiskAdjustedAdvisorDecision
from .craft_investment import (
    CraftInvestmentCostBasis,
    CraftInvestmentCostBasisStatus,
    CurrentMarketValuation,
    CurrentProfitPosition,
)
from .domain import EconomicValue
from .economy import EXALTED_ECONOMIC_UNIT
from .expected_value import ExpectedValueStatus


STOP_CONTINUE_ALGORITHM_VERSION = "dc-stop-continue-v1"


class StopContinueReadiness(str, Enum):
    READY = "READY"
    NO_POINT_SELL_BASELINE = "NO_POINT_SELL_BASELINE"
    NO_EV_READY_CONTINUATION = "NO_EV_READY_CONTINUATION"
    INCOMPLETE_PROSPECTIVE_COST = "INCOMPLETE_PROSPECTIVE_COST"
    NO_RECOMMENDATION = "NO_RECOMMENDATION"


@dataclass(frozen=True)
class StopContinueDecisionEconomics:
    decision_id: str
    decision_type: AdvisorDecisionType
    readiness: StopContinueReadiness
    selected_candidate_id: str | None
    selected_action_id: str | None
    current_market_valuation_status: str | None
    sell_now_value: EconomicValue | None = None
    best_continue_candidate_id: str | None = None
    best_continue_action_id: str | None = None
    expected_post_craft_value: EconomicValue | None = None
    expected_incremental_craft_cost: EconomicValue | None = None
    expected_net_after_craft: EconomicValue | None = None
    gain_loss_vs_sell_now: EconomicValue | None = None
    cost_basis_status: CraftInvestmentCostBasisStatus | None = None
    total_invested: EconomicValue | None = None
    current_profit_position: CurrentProfitPosition | None = None
    comparison_ready: bool = False
    decision_margin_source: str = "AdvisorDecisionEngine"
    reasons: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    algorithm_version: str = STOP_CONTINUE_ALGORITHM_VERSION
    generated_at: datetime | None = None


class StopContinueDecisionEconomicsEngine:
    """Build inspectable STOP/CONTINUE economics from existing components."""

    def evaluate(
        self,
        current_market_valuation: CurrentMarketValuation | None,
        advisor_decision: AdvisorDecision | None,
        cost_basis: CraftInvestmentCostBasis | None = None,
        current_profit_position: CurrentProfitPosition | None = None,
        risk_adjusted_decision: RiskAdjustedAdvisorDecision | None = None,
        generated_at: datetime | None = None,
    ) -> StopContinueDecisionEconomics:
        generated_at = generated_at or datetime.now(timezone.utc)
        decision_id = f"stop-continue:{STOP_CONTINUE_ALGORITHM_VERSION}:{generated_at.isoformat()}"
        warnings: list[str] = []
        if cost_basis is not None and cost_basis.status != CraftInvestmentCostBasisStatus.COMPLETE:
            warnings.append(
                "Historical cost basis is incomplete; profit/capital claims remain incomplete but forward marginal decision economics may still be evaluated."
            )

        if (
            current_market_valuation is None
            or current_market_valuation.status != "ESTIMATED_MARKET_VALUE"
            or current_market_valuation.estimated_value is None
        ):
            blockers = (
                "Authoritative current point market valuation is required for sell-now versus continue-crafting comparison.",
            )
            if current_market_valuation is not None and current_market_valuation.legacy_statistical_median is not None:
                warnings.append("Legacy/manual median is diagnostics only and was not used as a sell-now baseline.")
            return StopContinueDecisionEconomics(
                decision_id=decision_id,
                decision_type=AdvisorDecisionType.NO_RECOMMENDATION,
                readiness=StopContinueReadiness.NO_POINT_SELL_BASELINE,
                selected_candidate_id=None,
                selected_action_id=None,
                current_market_valuation_status=current_market_valuation.status if current_market_valuation else None,
                cost_basis_status=cost_basis.status if cost_basis else None,
                total_invested=cost_basis.total_invested if cost_basis else None,
                current_profit_position=current_profit_position,
                blockers=blockers,
                warnings=tuple(warnings),
                generated_at=generated_at,
            )

        _require_normalized(current_market_valuation.estimated_value, "sell-now market valuation")
        if advisor_decision is None:
            return StopContinueDecisionEconomics(
                decision_id=decision_id,
                decision_type=AdvisorDecisionType.NO_RECOMMENDATION,
                readiness=StopContinueReadiness.NO_RECOMMENDATION,
                selected_candidate_id=None,
                selected_action_id=None,
                current_market_valuation_status=current_market_valuation.status,
                sell_now_value=current_market_valuation.estimated_value,
                cost_basis_status=cost_basis.status if cost_basis else None,
                total_invested=cost_basis.total_invested if cost_basis else None,
                current_profit_position=current_profit_position,
                blockers=("Advisor decision is unavailable.",),
                warnings=tuple(warnings),
                generated_at=generated_at,
            )

        best_continue = _best_ev_ready_candidate(advisor_decision)
        if best_continue is None:
            return StopContinueDecisionEconomics(
                decision_id=decision_id,
                decision_type=AdvisorDecisionType.NO_RECOMMENDATION,
                readiness=StopContinueReadiness.NO_EV_READY_CONTINUATION,
                selected_candidate_id=None,
                selected_action_id=None,
                current_market_valuation_status=current_market_valuation.status,
                sell_now_value=current_market_valuation.estimated_value,
                cost_basis_status=cost_basis.status if cost_basis else None,
                total_invested=cost_basis.total_invested if cost_basis else None,
                current_profit_position=current_profit_position,
                blockers=("No EV-ready prospective craft action with compatible evidence is available.",),
                warnings=tuple(warnings),
                generated_at=generated_at,
            )

        selected_continue = _risk_selected_craft_candidate(advisor_decision, risk_adjusted_decision) or best_continue
        ev = selected_continue.expected_value_result
        assert ev is not None
        if ev.craft_cost is None or ev.gross_expected_outcome_value is None or ev.net_expected_value is None:
            return StopContinueDecisionEconomics(
                decision_id=decision_id,
                decision_type=AdvisorDecisionType.NO_RECOMMENDATION,
                readiness=StopContinueReadiness.INCOMPLETE_PROSPECTIVE_COST,
                selected_candidate_id=None,
                selected_action_id=None,
                current_market_valuation_status=current_market_valuation.status,
                sell_now_value=current_market_valuation.estimated_value,
                best_continue_candidate_id=best_continue.candidate_id,
                best_continue_action_id=best_continue.action_id,
                cost_basis_status=cost_basis.status if cost_basis else None,
                total_invested=cost_basis.total_invested if cost_basis else None,
                current_profit_position=current_profit_position,
                blockers=("Prospective action EV is missing post-craft value or incremental craft cost.",),
                warnings=tuple(warnings),
                generated_at=generated_at,
            )

        for field_name, value in (
            ("expected post-craft value", ev.gross_expected_outcome_value),
            ("expected incremental craft cost", ev.craft_cost),
            ("expected net after craft", ev.net_expected_value),
            ("gain/loss vs sell now", ev.expected_gain_vs_sell_now),
        ):
            if value is not None:
                _require_normalized(value, field_name)

        effective_decision_type = (
            risk_adjusted_decision.risk_adjusted_decision_type
            if risk_adjusted_decision is not None
            else advisor_decision.decision_type
        )
        effective_selected_candidate_id = (
            risk_adjusted_decision.selected_candidate_id
            if risk_adjusted_decision is not None
            else advisor_decision.selected_candidate_id
        )

        if effective_decision_type == AdvisorDecisionType.CRAFT:
            selected_candidate_id = effective_selected_candidate_id
            selected_action_id = (
                selected_continue.action_id
                if selected_candidate_id == selected_continue.candidate_id
                else None
            )
            reasons = (
                "Best supported continuation beats the authoritative sell-now baseline after prospective craft cost.",
                "Historical ledger spend was not added to the prospective incremental craft cost.",
            )
            if risk_adjusted_decision is not None:
                reasons = (
                    "Existing risk policy permits the selected continuation without mutating raw EV values.",
                    *reasons,
                )
            decision_type = AdvisorDecisionType.CRAFT
        elif effective_decision_type == AdvisorDecisionType.SELL_NOW:
            selected_candidate_id = effective_selected_candidate_id
            selected_action_id = None
            reasons = (
                "Authoritative sell-now value dominates the best EV-ready continuation under the configured Advisor policy.",
                "Historical ledger spend was not added to the prospective incremental craft cost.",
            )
            if risk_adjusted_decision is not None and advisor_decision.decision_type == AdvisorDecisionType.CRAFT:
                reasons = (
                    "Existing risk policy rejects the raw craft winner; player-facing stop/continue economics follows the risk-adjusted decision.",
                    *reasons,
                )
            decision_type = AdvisorDecisionType.SELL_NOW
        else:
            selected_candidate_id = None
            selected_action_id = None
            reasons = (
                "Advisor policy did not produce a rankable SELL_NOW or CRAFT decision despite compatible comparison evidence.",
            )
            if risk_adjusted_decision is not None:
                reasons = (
                    "Existing risk policy does not permit a player-facing craft recommendation.",
                    *reasons,
                )
            decision_type = AdvisorDecisionType.NO_RECOMMENDATION

        return StopContinueDecisionEconomics(
            decision_id=decision_id,
            decision_type=decision_type,
            readiness=StopContinueReadiness.READY if decision_type != AdvisorDecisionType.NO_RECOMMENDATION else StopContinueReadiness.NO_RECOMMENDATION,
            selected_candidate_id=selected_candidate_id,
            selected_action_id=selected_action_id,
            current_market_valuation_status=current_market_valuation.status,
            sell_now_value=current_market_valuation.estimated_value,
            best_continue_candidate_id=best_continue.candidate_id,
            best_continue_action_id=best_continue.action_id,
            expected_post_craft_value=ev.gross_expected_outcome_value,
            expected_incremental_craft_cost=ev.craft_cost,
            expected_net_after_craft=ev.net_expected_value,
            gain_loss_vs_sell_now=ev.expected_gain_vs_sell_now,
            cost_basis_status=cost_basis.status if cost_basis else None,
            total_invested=cost_basis.total_invested if cost_basis else None,
            current_profit_position=current_profit_position,
            comparison_ready=decision_type != AdvisorDecisionType.NO_RECOMMENDATION,
            reasons=reasons,
            warnings=tuple(warnings),
            generated_at=generated_at,
        )


def _best_ev_ready_candidate(decision: AdvisorDecision) -> AdvisorCandidate | None:
    candidates = [
        candidate
        for candidate in decision.craft_candidates
        if candidate.status == AdvisorCandidateStatus.RANKABLE_EV
        and candidate.expected_value_result is not None
        and candidate.expected_value_result.status == ExpectedValueStatus.AVAILABLE
        and candidate.expected_value_result.net_expected_value is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.expected_value_result.net_expected_value.amount)  # type: ignore[union-attr]


def _risk_selected_craft_candidate(
    decision: AdvisorDecision,
    risk_adjusted_decision: RiskAdjustedAdvisorDecision | None,
) -> AdvisorCandidate | None:
    if (
        risk_adjusted_decision is None
        or risk_adjusted_decision.risk_adjusted_decision_type != AdvisorDecisionType.CRAFT
        or risk_adjusted_decision.selected_candidate_id is None
    ):
        return None
    for candidate in decision.craft_candidates:
        if candidate.candidate_id == risk_adjusted_decision.selected_candidate_id:
            return candidate
    return None


def _require_normalized(value: EconomicValue, field_name: str) -> None:
    if value.unit != EXALTED_ECONOMIC_UNIT:
        raise ValueError(f"{field_name} must use Exalted economic units")
