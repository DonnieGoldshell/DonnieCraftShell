import copy
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.advisor_decision import (
    AdvisorCraftInput,
    AdvisorDecisionEngine,
    AdvisorDecisionType,
)
from packages.shared.donniecraftshell_contracts.advisor_risk import (
    RISK_POLICY_VERSION,
    AdvisorRiskContext,
    AdvisorRiskPolicyEngine,
    RiskAssessmentStatus,
    RiskPolicy,
    RiskProfile,
    policy_for_profile,
)
from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.craft_action_candidates import get_action_candidates
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.domain import EconomicValue
from packages.shared.donniecraftshell_contracts.economy import FreshnessState, normalized_exalted_value
from packages.shared.donniecraftshell_contracts.economy_costs import CraftMaterialCost
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.expected_value import ExpectedValueResult, ExpectedValueStatus
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.poe_show_economy import load_normalized_economy_snapshot
from packages.shared.donniecraftshell_contracts.probability import CurrentResearchProbabilityProvider
from packages.shared.donniecraftshell_contracts.scenario_analysis import DecisionReadiness, OutcomeValuation, ScenarioAnalysisService, ValuationCompleteness
from packages.shared.donniecraftshell_contracts.valuation import ValuationEstimateType, ValuationReadiness, ValuationResult


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
CRAFTING_DATASET = ROOT / "data" / "normalized" / "crafting" / "crafting-actions-poe2-quiver-2026-08-12-research" / "actions.json"
AFFIX_CAPACITY_DATASET = ROOT / "data" / "normalized" / "crafting" / "affix-capacity-poe2-2026-08-12-research" / "capacity.json"
CURRENCY_SNAPSHOT = ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff" / "economy_snapshot.json"
RITUAL_SNAPSHOT = ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff11a-0000-7000-8000-000000000001" / "economy_snapshot.json"
ESSENCE_SNAPSHOT = ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff11a-0000-7000-8000-000000000002" / "economy_snapshot.json"
AS_OF = datetime(2026, 8, 11, 13, 30, tzinfo=timezone.utc)
LEAGUE = "Runes of Aldur"


def parsed_fixture(name: str):
    result = parse_clipboard_item((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert result.item is not None
    return result.item


def candidate_by_id(candidates, action_id: str):
    return next(candidate for candidate in candidates if candidate.action.action_id == action_id)


class AdvisorRiskPolicyTests(unittest.TestCase):
    def setUp(self):
        self.item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        self.crafting_dataset = load_crafting_dataset(CRAFTING_DATASET)
        self.craft_engine = CraftActionEngine(self.crafting_dataset)
        self.affix_resolver = AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET))
        self.repository = EconomyRepository(
            (
                load_normalized_economy_snapshot(CURRENCY_SNAPSHOT),
                load_normalized_economy_snapshot(RITUAL_SNAPSHOT),
                load_normalized_economy_snapshot(ESSENCE_SNAPSHOT),
            )
        )
        self.affix_state = self.affix_resolver.resolve(self.item)
        self.candidates = get_action_candidates(self.item, self.affix_state, self.craft_engine, self.repository, LEAGUE, AS_OF)

    def test_bankroll_validation_and_exposure_calculation(self):
        with self.assertRaises(ValueError):
            AdvisorRiskContext(bankroll=normalized_exalted_value("0"))
        raw = self._raw_decision((self._rankable_input("craft-a", net="120", gain="20", cost="50"),))

        adjusted = AdvisorRiskPolicyEngine(policy_for_profile(RiskProfile.AGGRESSIVE)).apply(raw, AdvisorRiskContext(bankroll=normalized_exalted_value("100"), risk_profile=RiskProfile.AGGRESSIVE), AS_OF)

        self.assertEqual(adjusted.risk_adjusted_candidates[0].risk_assessment.capital_exposure.bankroll_exposure, Decimal("0.5"))

    def test_conservative_veto(self):
        raw = self._raw_decision((self._rankable_input("craft-a", net="120", gain="20", cost="50"),))

        adjusted = AdvisorRiskPolicyEngine(policy_for_profile(RiskProfile.CONSERVATIVE)).apply(raw, AdvisorRiskContext(bankroll=normalized_exalted_value("100"), risk_profile=RiskProfile.CONSERVATIVE), AS_OF)

        self.assertEqual(raw.decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(adjusted.risk_adjusted_decision_type, AdvisorDecisionType.SELL_NOW)
        self.assertEqual(adjusted.risk_adjusted_candidates[0].risk_adjusted_status, RiskAssessmentStatus.REJECTED)
        self.assertEqual(raw.craft_candidates[0].expected_value_result.expected_gain_vs_sell_now.amount, Decimal("20"))

    def test_second_best_survives_after_raw_winner_rejected(self):
        craft_a = self._rankable_input("craft-a", net="130", gain="30", cost="60")
        craft_b = self._rankable_input("craft-b", net="120", gain="20", cost="10")
        raw = self._raw_decision((craft_a, craft_b))

        adjusted = AdvisorRiskPolicyEngine(policy_for_profile(RiskProfile.CONSERVATIVE)).apply(raw, AdvisorRiskContext(bankroll=normalized_exalted_value("100"), risk_profile=RiskProfile.CONSERVATIVE), AS_OF)

        self.assertEqual(raw.selected_candidate_id, "advisor-candidate:craft:dc:test:craft-action:craft-a")
        self.assertEqual(adjusted.selected_candidate_id, "advisor-candidate:craft:dc:test:craft-action:craft-b")
        self.assertTrue(adjusted.risk_policy_changed_outcome)

    def test_aggressive_accepts_high_exposure(self):
        raw = self._raw_decision((self._rankable_input("craft-a", net="120", gain="20", cost="50"),))

        adjusted = AdvisorRiskPolicyEngine(policy_for_profile(RiskProfile.AGGRESSIVE)).apply(raw, AdvisorRiskContext(bankroll=normalized_exalted_value("100"), risk_profile=RiskProfile.AGGRESSIVE), AS_OF)

        self.assertEqual(adjusted.risk_adjusted_decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(adjusted.risk_adjusted_candidates[0].risk_adjusted_status, RiskAssessmentStatus.ACCEPTABLE)

    def test_missing_bankroll_reports_insufficient_data(self):
        raw = self._raw_decision((self._rankable_input("craft-a", net="120", gain="20", cost="10"),))

        adjusted = AdvisorRiskPolicyEngine(policy_for_profile(RiskProfile.BALANCED)).apply(raw, None, AS_OF)

        self.assertEqual(raw.decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(adjusted.risk_adjusted_decision_type, AdvisorDecisionType.SELL_NOW)
        self.assertEqual(adjusted.risk_adjusted_candidates[0].risk_adjusted_status, RiskAssessmentStatus.INSUFFICIENT_DATA)

    def test_minimum_reserve_rule(self):
        policy = RiskPolicy(
            policy_id="synthetic-reserve-policy",
            risk_profile=RiskProfile.BALANCED,
            max_bankroll_exposure=Decimal("1"),
            minimum_bankroll_reserve=normalized_exalted_value("80"),
        )
        raw = self._raw_decision((self._rankable_input("craft-a", net="120", gain="20", cost="30"),))

        adjusted = AdvisorRiskPolicyEngine(policy).apply(raw, AdvisorRiskContext(bankroll=normalized_exalted_value("100"), risk_profile=RiskProfile.BALANCED), AS_OF)

        self.assertEqual(adjusted.risk_adjusted_candidates[0].risk_adjusted_status, RiskAssessmentStatus.REJECTED)
        self.assertIn("MINIMUM_BANKROLL_RESERVE", adjusted.risk_adjusted_candidates[0].risk_assessment.triggered_policy_rules)

    def test_downside_rule_and_partial_downside_warning(self):
        policy = RiskPolicy(
            policy_id="synthetic-downside-policy",
            risk_profile=RiskProfile.BALANCED,
            max_bankroll_exposure=Decimal("1"),
            max_downside_vs_current=normalized_exalted_value("5"),
        )
        raw = self._raw_decision((self._rankable_input("craft-a", net="120", gain="20", cost="10", downside="-10", partial_downside=True),))

        adjusted = AdvisorRiskPolicyEngine(policy).apply(raw, AdvisorRiskContext(bankroll=normalized_exalted_value("100"), risk_profile=RiskProfile.BALANCED), AS_OF)

        assessment = adjusted.risk_adjusted_candidates[0].risk_assessment
        self.assertEqual(assessment.status, RiskAssessmentStatus.REJECTED)
        self.assertIn("MAX_DOWNSIDE", assessment.triggered_policy_rules)
        self.assertTrue(any("worst currently valuated scenario" in warning for warning in assessment.capital_exposure.warnings))

    def test_scenario_only_candidate_is_not_promoted_by_risk(self):
        scenario_only = AdvisorCraftInput(self._base_candidate("scenario-only"), self._scenario(DecisionReadiness.SCENARIO_ONLY), None)
        raw = AdvisorDecisionEngine().decide(self._current_value("100"), (scenario_only,), generated_at=AS_OF)

        adjusted = AdvisorRiskPolicyEngine(policy_for_profile(RiskProfile.AGGRESSIVE)).apply(raw, AdvisorRiskContext(bankroll=normalized_exalted_value("1000"), risk_profile=RiskProfile.AGGRESSIVE), AS_OF)

        self.assertEqual(raw.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(adjusted.risk_adjusted_decision_type, AdvisorDecisionType.NO_RECOMMENDATION)

    def test_quiver_6_no_ev_ready_remains_no_recommendation_for_methodology(self):
        annulment = candidate_by_id(self.candidates, "dc:poe2:craft-action:orb-of-annulment")
        outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.item, self.affix_state, annulment.action, annulment.applicability)
        probability_model = CurrentResearchProbabilityProvider().get_probability_model(self.item, outcome_set)
        valuations = tuple(OutcomeValuation(state.outcome_id, self._current_value("100")) for state in outcome_set.hypothetical_states)
        scenario = ScenarioAnalysisService().analyze_action(self._current_value("100"), annulment, outcome_set, probability_model, valuations, AS_OF)
        raw = AdvisorDecisionEngine().decide(self._current_value("100"), (AdvisorCraftInput(annulment, scenario, None),), generated_at=AS_OF)

        adjusted = AdvisorRiskPolicyEngine(policy_for_profile(RiskProfile.CONSERVATIVE)).apply(raw, AdvisorRiskContext(bankroll=normalized_exalted_value("1000"), risk_profile=RiskProfile.CONSERVATIVE), AS_OF)

        self.assertEqual(raw.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(adjusted.risk_adjusted_decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertTrue(any("risk policy cannot promote" in reason for reason in adjusted.decision_reasons))

    def test_versions_provenance_and_immutability(self):
        raw = self._raw_decision((self._rankable_input("craft-a", net="120", gain="20", cost="10"),))
        raw_before = copy.deepcopy(raw)
        context = AdvisorRiskContext(bankroll=normalized_exalted_value("100"), risk_profile=RiskProfile.AGGRESSIVE)
        context_before = copy.deepcopy(context)

        adjusted = AdvisorRiskPolicyEngine(policy_for_profile(RiskProfile.AGGRESSIVE)).apply(raw, context, AS_OF)

        self.assertEqual(raw, raw_before)
        self.assertEqual(context, context_before)
        self.assertEqual(adjusted.risk_policy_version, RISK_POLICY_VERSION)
        self.assertEqual(adjusted.advisor_algorithm_version, raw.algorithm_version)

    def _raw_decision(self, crafts):
        return AdvisorDecisionEngine().decide(self._current_value("100"), crafts, generated_at=AS_OF)

    def _rankable_input(self, action_id: str, net: str, gain: str, cost: str, downside: str = "-5", partial_downside: bool = False):
        action_id = self._action_id(action_id)
        candidate = self._base_candidate(action_id)
        candidate = self._with_synthetic_cost(candidate, cost)
        scenario = self._scenario(DecisionReadiness.EV_READY)
        scenario = replace(
            scenario,
            action_id=action_id,
            downside_relative_to_current=EconomicValue(Decimal(downside), "EXALTED_ECONOMIC_UNIT"),
            valuation_completeness=ValuationCompleteness.PARTIAL if partial_downside else ValuationCompleteness.COMPLETE,
        )
        ev = ExpectedValueResult(
            status=ExpectedValueStatus.AVAILABLE,
            result_id=f"ev:{action_id}",
            action_id=action_id,
            scenario_analysis_id=scenario.analysis_id,
            source_item_id=scenario.source_item_id,
            gross_expected_outcome_value=normalized_exalted_value(Decimal(net) + Decimal(cost)),
            craft_cost=normalized_exalted_value(cost),
            net_expected_value=normalized_exalted_value(net),
            current_item_value=normalized_exalted_value("100"),
            expected_gain_vs_sell_now=EconomicValue(Decimal(gain), "EXALTED_ECONOMIC_UNIT"),
            roi_on_craft_cost=Decimal(gain) / Decimal(cost) if Decimal(cost) != 0 else None,
            economy_snapshot_ids=("synthetic-economy-snapshot",),
            dataset_versions=("synthetic-dataset",),
            warnings=("synthetic EV-ready proof only",),
        )
        return AdvisorCraftInput(candidate, scenario, ev)

    def _with_synthetic_cost(self, candidate, amount: str):
        cost = CraftMaterialCost(
            lines=(),
            total=normalized_exalted_value(amount),
            complete=True,
            freshness=FreshnessState.FRESH,
            warnings=("synthetic risk cost",),
        )
        return replace(candidate, material_cost=cost, cost_complete=True, cost_freshness=FreshnessState.FRESH)

    def _base_candidate(self, action_id: str):
        action_id = self._action_id(action_id)
        candidate = candidate_by_id(self.candidates, "dc:poe2:craft-action:orb-of-annulment")
        return replace(candidate, action=replace(candidate.action, action_id=action_id), applicability=replace(candidate.applicability, action_id=action_id))

    def _scenario(self, readiness: DecisionReadiness):
        candidate = self._base_candidate("scenario-action")
        outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.item, self.affix_state, candidate.action, candidate.applicability)
        probability_model = CurrentResearchProbabilityProvider().get_probability_model(self.item, outcome_set)
        valuations = tuple(OutcomeValuation(state.outcome_id, self._current_value("100")) for state in outcome_set.hypothetical_states)
        scenario = ScenarioAnalysisService().analyze_action(self._current_value("100"), candidate, outcome_set, probability_model, valuations, AS_OF)
        return replace(
            scenario,
            decision_readiness=readiness,
            ev_readiness=readiness == DecisionReadiness.EV_READY,
            dataset_versions=("synthetic-dataset",),
            economy_snapshot_ids=("synthetic-economy-snapshot",),
        )

    def _current_value(self, amount: str):
        return ValuationResult(
            readiness=ValuationReadiness.READY,
            estimate_type=ValuationEstimateType.LISTING_DERIVED,
            estimated_value=normalized_exalted_value(amount),
            plausible_low=normalized_exalted_value(Decimal(amount) - Decimal("5")),
            plausible_high=normalized_exalted_value(Decimal(amount) + Decimal("5")),
            comparable_count=3,
            source_evidence_ids=("current-evidence",),
            economy_snapshot_ids=("synthetic-economy-snapshot",),
            warnings=("synthetic listing-derived valuation for risk tests",),
        )

    def _action_id(self, action_id: str) -> str:
        return action_id if ":" in action_id else f"dc:test:craft-action:{action_id}"


if __name__ == "__main__":
    unittest.main()
