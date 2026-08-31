import unittest
from datetime import datetime, timezone
from decimal import Decimal

from packages.shared.donniecraftshell_contracts.advisor_decision import (
    ADVISOR_ALGORITHM_VERSION,
    AdvisorCandidate,
    AdvisorCandidateStatus,
    AdvisorCandidateType,
    AdvisorDecision,
    AdvisorDecisionType,
)
from packages.shared.donniecraftshell_contracts.advisor_risk import RiskAdjustedAdvisorDecision
from packages.shared.donniecraftshell_contracts.craft_investment import (
    CraftInvestmentCostBasis,
    CraftInvestmentCostBasisStatus,
    CurrentMarketValuation,
)
from packages.shared.donniecraftshell_contracts.domain import EconomicValue
from packages.shared.donniecraftshell_contracts.decision_economics import (
    STOP_CONTINUE_ALGORITHM_VERSION,
    StopContinueDecisionEconomicsEngine,
    StopContinueReadiness,
)
from packages.shared.donniecraftshell_contracts.economy import normalized_exalted_value
from packages.shared.donniecraftshell_contracts.expected_value import ExpectedValueResult, ExpectedValueStatus


AS_OF = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)


class StopContinueDecisionEconomicsTests(unittest.TestCase):
    def test_point_current_valuation_and_ev_ready_craft_can_choose_sell_now(self):
        decision = self._raw_decision(
            AdvisorDecisionType.SELL_NOW,
            self._craft_candidate("craft-a", gross="110", cost="20", net="90", gain="-10"),
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(self._point_market("100"), decision, generated_at=AS_OF)

        self.assertEqual(result.decision_type, AdvisorDecisionType.SELL_NOW)
        self.assertEqual(result.readiness, StopContinueReadiness.READY)
        self.assertEqual(result.sell_now_value.amount, Decimal("100"))
        self.assertEqual(result.expected_post_craft_value.amount, Decimal("110"))
        self.assertEqual(result.expected_incremental_craft_cost.amount, Decimal("20"))
        self.assertEqual(result.expected_net_after_craft.amount, Decimal("90"))
        self.assertEqual(result.gain_loss_vs_sell_now.amount, Decimal("-10"))

    def test_point_current_valuation_and_ev_ready_craft_can_choose_craft(self):
        decision = self._raw_decision(
            AdvisorDecisionType.CRAFT,
            self._craft_candidate("craft-a", gross="140", cost="20", net="120", gain="20"),
            selected_candidate_id="advisor-candidate:craft:craft-a",
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(self._point_market("100"), decision, generated_at=AS_OF)

        self.assertEqual(result.decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(result.selected_action_id, "craft-a")
        self.assertEqual(result.best_continue_action_id, "craft-a")
        self.assertEqual(result.gain_loss_vs_sell_now.amount, Decimal("20"))

    def test_supported_range_only_cannot_create_point_recommendation(self):
        decision = self._raw_decision(
            AdvisorDecisionType.CRAFT,
            self._craft_candidate("craft-a", gross="140", cost="20", net="120", gain="20"),
            selected_candidate_id="advisor-candidate:craft:craft-a",
        )
        market = CurrentMarketValuation(
            status="SUPPORTED_RANGE_ONLY",
            supported_low=normalized_exalted_value("45"),
            supported_high=normalized_exalted_value("450"),
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(market, decision, generated_at=AS_OF)

        self.assertEqual(result.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(result.readiness, StopContinueReadiness.NO_POINT_SELL_BASELINE)
        self.assertIsNone(result.sell_now_value)
        self.assertTrue(any("point market valuation" in blocker for blocker in result.blockers))

    def test_insufficient_market_evidence_returns_no_recommendation(self):
        result = StopContinueDecisionEconomicsEngine().evaluate(
            CurrentMarketValuation(status="INSUFFICIENT_MARKET_EVIDENCE"),
            self._raw_decision(AdvisorDecisionType.NO_RECOMMENDATION),
            generated_at=AS_OF,
        )

        self.assertEqual(result.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(result.readiness, StopContinueReadiness.NO_POINT_SELL_BASELINE)

    def test_non_ev_ready_action_cannot_force_sell_or_craft(self):
        non_rankable = AdvisorCandidate(
            candidate_id="advisor-candidate:craft:scenario-only",
            candidate_type=AdvisorCandidateType.CRAFT_ACTION,
            status=AdvisorCandidateStatus.NON_RANKABLE_SCENARIO,
            action_id="scenario-only",
        )
        result = StopContinueDecisionEconomicsEngine().evaluate(
            self._point_market("100"),
            self._raw_decision(AdvisorDecisionType.NO_RECOMMENDATION, non_rankable),
            generated_at=AS_OF,
        )

        self.assertEqual(result.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(result.readiness, StopContinueReadiness.NO_EV_READY_CONTINUATION)

    def test_missing_prospective_action_cost_blocks_comparison(self):
        candidate = self._craft_candidate("craft-a", gross="140", cost="20", net="120", gain="20")
        broken_ev = ExpectedValueResult(
            status=ExpectedValueStatus.AVAILABLE,
            result_id="ev:broken",
            action_id="craft-a",
            scenario_analysis_id="scenario",
            source_item_id="item",
            gross_expected_outcome_value=normalized_exalted_value("140"),
            craft_cost=None,
            net_expected_value=normalized_exalted_value("120"),
            expected_gain_vs_sell_now=normalized_exalted_value("20"),
        )
        candidate = AdvisorCandidate(
            **{**candidate.__dict__, "expected_value_result": broken_ev}
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(
            self._point_market("100"),
            self._raw_decision(AdvisorDecisionType.CRAFT, candidate, selected_candidate_id=candidate.candidate_id),
            generated_at=AS_OF,
        )

        self.assertEqual(result.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(result.readiness, StopContinueReadiness.INCOMPLETE_PROSPECTIVE_COST)
        self.assertIsNone(result.expected_incremental_craft_cost)

    def test_legacy_median_or_broad_midpoint_cannot_bypass_market_authority(self):
        market = CurrentMarketValuation(
            status="SUPPORTED_RANGE_ONLY",
            supported_low=normalized_exalted_value("45"),
            supported_high=normalized_exalted_value("450"),
            legacy_statistical_median=normalized_exalted_value("450"),
        )
        decision = self._raw_decision(
            AdvisorDecisionType.CRAFT,
            self._craft_candidate("craft-a", gross="140", cost="20", net="120", gain="20"),
            selected_candidate_id="advisor-candidate:craft:craft-a",
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(market, decision, generated_at=AS_OF)

        self.assertEqual(result.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertIsNone(result.sell_now_value)
        self.assertTrue(any("Legacy/manual median" in warning for warning in result.warnings))

    def test_historical_crafting_spend_is_not_double_counted_as_prospective_cost(self):
        cost_basis = CraftInvestmentCostBasis(
            ledger_id="current",
            status=CraftInvestmentCostBasisStatus.COMPLETE,
            total_invested=normalized_exalted_value("1000"),
            known_invested=normalized_exalted_value("1000"),
            base_acquisition_total=normalized_exalted_value("700"),
            crafting_spend_total=normalized_exalted_value("300"),
            included_entry_ids=("base", "spent"),
        )
        decision = self._raw_decision(
            AdvisorDecisionType.CRAFT,
            self._craft_candidate("craft-a", gross="140", cost="20", net="120", gain="20"),
            selected_candidate_id="advisor-candidate:craft:craft-a",
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(self._point_market("100"), decision, cost_basis, generated_at=AS_OF)

        self.assertEqual(result.expected_incremental_craft_cost.amount, Decimal("20"))
        self.assertEqual(result.total_invested.amount, Decimal("1000"))

    def test_incomplete_historical_cost_basis_does_not_block_forward_marginal_decision(self):
        cost_basis = CraftInvestmentCostBasis(
            ledger_id="current",
            status=CraftInvestmentCostBasisStatus.INCOMPLETE,
            total_invested=None,
            known_invested=normalized_exalted_value("30"),
            base_acquisition_total=normalized_exalted_value("0"),
            crafting_spend_total=normalized_exalted_value("30"),
            included_entry_ids=("spent",),
            warnings=("No explicit base-acquisition entry.",),
        )
        decision = self._raw_decision(
            AdvisorDecisionType.CRAFT,
            self._craft_candidate("craft-a", gross="140", cost="20", net="120", gain="20"),
            selected_candidate_id="advisor-candidate:craft:craft-a",
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(self._point_market("100"), decision, cost_basis, generated_at=AS_OF)

        self.assertEqual(result.decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(result.cost_basis_status, CraftInvestmentCostBasisStatus.INCOMPLETE)
        self.assertTrue(any("profit/capital claims remain incomplete" in warning for warning in result.warnings))

    def test_decision_margin_is_inherited_not_reapplied(self):
        decision = self._raw_decision(
            AdvisorDecisionType.SELL_NOW,
            self._craft_candidate("craft-a", gross="110.5", cost="10", net="100.5", gain="0.5"),
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(self._point_market("100"), decision, generated_at=AS_OF)

        self.assertEqual(result.decision_type, AdvisorDecisionType.SELL_NOW)
        self.assertEqual(result.gain_loss_vs_sell_now.amount, Decimal("0.5"))
        self.assertEqual(result.decision_margin_source, "AdvisorDecisionEngine")

    def test_risk_adjusted_veto_prevents_stop_continue_craft_headline(self):
        candidate = self._craft_candidate("craft-a", gross="140", cost="20", net="120", gain="20")
        raw_decision = self._raw_decision(
            AdvisorDecisionType.CRAFT,
            candidate,
            selected_candidate_id=candidate.candidate_id,
        )
        risk_decision = RiskAdjustedAdvisorDecision(
            raw_decision=raw_decision,
            risk_adjusted_decision_type=AdvisorDecisionType.SELL_NOW,
            raw_winner_candidate_id=candidate.candidate_id,
            selected_candidate_id="advisor-candidate:sell-now",
            risk_policy_changed_outcome=True,
            risk_adjusted_candidates=(),
            decision_reasons=("Synthetic risk veto.",),
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(
            self._point_market("100"),
            raw_decision,
            risk_adjusted_decision=risk_decision,
            generated_at=AS_OF,
        )

        self.assertEqual(result.decision_type, AdvisorDecisionType.SELL_NOW)
        self.assertIsNone(result.selected_action_id)
        self.assertEqual(result.best_continue_action_id, "craft-a")
        self.assertTrue(any("risk policy rejects" in reason for reason in result.reasons))

    def test_risk_adjusted_second_best_craft_becomes_stop_continue_craft(self):
        craft_a = self._craft_candidate("craft-a", gross="160", cost="20", net="140", gain="40")
        craft_b = self._craft_candidate("craft-b", gross="135", cost="15", net="120", gain="20")
        raw_decision = self._raw_decision(
            AdvisorDecisionType.CRAFT,
            craft_a,
            craft_b,
            selected_candidate_id=craft_a.candidate_id,
        )
        risk_decision = RiskAdjustedAdvisorDecision(
            raw_decision=raw_decision,
            risk_adjusted_decision_type=AdvisorDecisionType.CRAFT,
            raw_winner_candidate_id=craft_a.candidate_id,
            selected_candidate_id=craft_b.candidate_id,
            risk_policy_changed_outcome=True,
            risk_adjusted_candidates=(),
            decision_reasons=("Synthetic second-best craft survives risk policy.",),
        )

        result = StopContinueDecisionEconomicsEngine().evaluate(
            self._point_market("100"),
            raw_decision,
            risk_adjusted_decision=risk_decision,
            generated_at=AS_OF,
        )

        self.assertEqual(result.decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(result.selected_action_id, "craft-b")
        self.assertEqual(result.best_continue_action_id, "craft-a")
        self.assertEqual(result.expected_net_after_craft.amount, Decimal("120"))
        self.assertEqual(result.gain_loss_vs_sell_now.amount, Decimal("20"))

    def test_algorithm_version_is_retained(self):
        result = StopContinueDecisionEconomicsEngine().evaluate(
            self._point_market("100"),
            self._raw_decision(
                AdvisorDecisionType.SELL_NOW,
                self._craft_candidate("craft-a", gross="110", cost="20", net="90", gain="-10"),
            ),
            generated_at=AS_OF,
        )

        self.assertEqual(result.algorithm_version, STOP_CONTINUE_ALGORITHM_VERSION)
        self.assertIn(STOP_CONTINUE_ALGORITHM_VERSION, result.decision_id)

    def _point_market(self, amount: str) -> CurrentMarketValuation:
        return CurrentMarketValuation(
            status="ESTIMATED_MARKET_VALUE",
            estimated_value=normalized_exalted_value(amount),
            confidence_level="MEDIUM",
        )

    def _craft_candidate(self, action_id: str, gross: str, cost: str, net: str, gain: str) -> AdvisorCandidate:
        ev = ExpectedValueResult(
            status=ExpectedValueStatus.AVAILABLE,
            result_id=f"ev:{action_id}",
            action_id=action_id,
            scenario_analysis_id="scenario",
            source_item_id="item",
            gross_expected_outcome_value=normalized_exalted_value(gross),
            craft_cost=normalized_exalted_value(cost),
            net_expected_value=normalized_exalted_value(net),
            current_item_value=normalized_exalted_value("100"),
            expected_gain_vs_sell_now=EconomicValue(Decimal(gain), "EXALTED_ECONOMIC_UNIT"),
        )
        return AdvisorCandidate(
            candidate_id=f"advisor-candidate:craft:{action_id}",
            candidate_type=AdvisorCandidateType.CRAFT_ACTION,
            status=AdvisorCandidateStatus.RANKABLE_EV,
            action_id=action_id,
            expected_value_result=ev,
            expected_gain_vs_sell_now=ev.expected_gain_vs_sell_now,
            action_cost=ev.craft_cost,
        )

    def _raw_decision(
        self,
        decision_type: AdvisorDecisionType,
        *craft_candidates: AdvisorCandidate,
        selected_candidate_id: str | None = None,
    ) -> AdvisorDecision:
        return AdvisorDecision(
            decision_id=f"advisor:{decision_type.value}",
            decision_type=decision_type,
            selected_candidate_id=selected_candidate_id or ("advisor-candidate:sell-now" if decision_type == AdvisorDecisionType.SELL_NOW else None),
            sell_now_candidate=None,
            craft_candidates=craft_candidates,
            rankable_candidates=craft_candidates,
            non_rankable_candidates=(),
            decision_confidence=None,
            decision_reasons=("synthetic decision economics test",),
            generated_at=AS_OF,
            algorithm_version=ADVISOR_ALGORITHM_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
