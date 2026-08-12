import copy
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.advisor_decision import (
    ADVISOR_ALGORITHM_VERSION,
    AdvisorCandidateStatus,
    AdvisorCraftInput,
    AdvisorDecisionEngine,
    AdvisorDecisionType,
    AdvisorPolicy,
)
from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.craft_action_candidates import get_action_candidates
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, CraftApplicabilityStatus, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.domain import EconomicValue
from packages.shared.donniecraftshell_contracts.economy import normalized_exalted_value
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.expected_value import ExpectedValueEngine, ExpectedValueResult, ExpectedValueStatus
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.poe_show_economy import load_normalized_economy_snapshot
from packages.shared.donniecraftshell_contracts.probability import CurrentResearchProbabilityProvider
from packages.shared.donniecraftshell_contracts.scenario_analysis import DecisionReadiness, OutcomeValuation, ScenarioAnalysisService
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


class AdvisorDecisionTests(unittest.TestCase):
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

    def test_sell_now_is_represented_as_candidate(self):
        decision = AdvisorDecisionEngine().decide(self._current_value("100"), (), generated_at=AS_OF)

        self.assertIsNotNone(decision.sell_now_candidate)
        self.assertEqual(decision.sell_now_candidate.candidate_type.value, "SELL_NOW")
        self.assertEqual(decision.sell_now_candidate.baseline_value.amount, Decimal("100"))
        self.assertEqual(decision.sell_now_candidate.action_cost.amount, Decimal("0"))

    def test_craft_winner_selected_by_net_ev(self):
        craft_a = self._rankable_input("craft-a", net="115", gain="15")
        craft_b = self._rankable_input("craft-b", net="105", gain="5")

        decision = AdvisorDecisionEngine().decide(self._current_value("100"), (craft_b, craft_a), generated_at=AS_OF)

        self.assertEqual(decision.decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(decision.selected_candidate_id, "advisor-candidate:craft:dc:test:craft-action:craft-a")
        self.assertTrue(any("15 Ex above" in reason for reason in decision.decision_reasons))

    def test_negative_ev_crafts_lose_to_sell_now(self):
        craft_a = self._rankable_input("craft-a", net="90", gain="-10")
        craft_b = self._rankable_input("craft-b", net="98", gain="-2")

        decision = AdvisorDecisionEngine().decide(self._current_value("100"), (craft_a, craft_b), generated_at=AS_OF)

        self.assertEqual(decision.decision_type, AdvisorDecisionType.SELL_NOW)
        self.assertEqual(decision.selected_candidate_id, "advisor-candidate:sell-now")

    def test_minimum_improvement_threshold_prevents_microscopic_craft(self):
        policy = AdvisorPolicy(minimum_expected_gain_absolute=Decimal("1"))
        craft = self._rankable_input("craft-a", net="100.01", gain="0.01")

        decision = AdvisorDecisionEngine(policy).decide(self._current_value("100"), (craft,), generated_at=AS_OF)

        self.assertEqual(decision.decision_type, AdvisorDecisionType.SELL_NOW)

    def test_scenario_only_candidate_never_enters_ev_ranking(self):
        scenario = self._scenario(DecisionReadiness.SCENARIO_ONLY)
        scenario = replace(scenario, best_valuated_outcome=None, median_valuated_outcome=normalized_exalted_value("10000"))
        craft = AdvisorCraftInput(self._base_candidate("scenario-only"), scenario, None)

        decision = AdvisorDecisionEngine().decide(self._current_value("100"), (craft,), generated_at=AS_OF)

        self.assertEqual(decision.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(decision.craft_candidates[0].status, AdvisorCandidateStatus.NON_RANKABLE_SCENARIO)
        self.assertFalse(decision.craft_candidates[0].rankable)

    def test_not_applicable_and_unknown_candidates_never_rank(self):
        not_applicable = self._base_candidate("not-applicable", CraftApplicabilityStatus.NOT_APPLICABLE)
        unknown = self._base_candidate("unknown", CraftApplicabilityStatus.UNKNOWN)

        decision = AdvisorDecisionEngine().decide(
            self._current_value("100"),
            (
                AdvisorCraftInput(not_applicable, self._scenario(DecisionReadiness.NOT_APPLICABLE), None),
                AdvisorCraftInput(unknown, None, None),
            ),
            generated_at=AS_OF,
        )

        self.assertEqual(decision.craft_candidates[0].status, AdvisorCandidateStatus.NON_RANKABLE_NOT_APPLICABLE)
        self.assertEqual(decision.craft_candidates[1].status, AdvisorCandidateStatus.NON_RANKABLE_UNKNOWN)
        self.assertEqual(decision.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)

    def test_missing_current_valuation_returns_no_recommendation(self):
        decision = AdvisorDecisionEngine().decide(None, (self._rankable_input("craft-a", net="115", gain="15"),), generated_at=AS_OF)

        self.assertEqual(decision.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertTrue(any("Current listing-derived valuation" in reason for reason in decision.decision_reasons))

    def test_no_ev_ready_craft_defaults_to_no_recommendation_but_policy_can_allow_sell(self):
        scenario_only = AdvisorCraftInput(self._base_candidate("scenario-only"), self._scenario(DecisionReadiness.SCENARIO_ONLY), None)

        default_decision = AdvisorDecisionEngine().decide(self._current_value("100"), (scenario_only,), generated_at=AS_OF)
        sell_policy_decision = AdvisorDecisionEngine(AdvisorPolicy(allow_sell_without_ev_ready_craft=True)).decide(self._current_value("100"), (scenario_only,), generated_at=AS_OF)

        self.assertEqual(default_decision.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(sell_policy_decision.decision_type, AdvisorDecisionType.SELL_NOW)

    def test_current_valuation_partial_does_not_force_sell(self):
        current = replace(self._current_value("100"), readiness=ValuationReadiness.PARTIAL)

        decision = AdvisorDecisionEngine().decide(current, (), generated_at=AS_OF)

        self.assertEqual(decision.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(decision.sell_now_candidate.status, AdvisorCandidateStatus.NON_RANKABLE_INSUFFICIENT_DATA)

    def test_mixed_candidates_only_ev_ready_craft_participates(self):
        ev_ready = self._rankable_input("craft-a", net="115", gain="15")
        scenario_only = AdvisorCraftInput(self._base_candidate("scenario-only"), self._scenario(DecisionReadiness.SCENARIO_ONLY), None)
        not_applicable = AdvisorCraftInput(self._base_candidate("not-applicable", CraftApplicabilityStatus.NOT_APPLICABLE), self._scenario(DecisionReadiness.NOT_APPLICABLE), None)

        decision = AdvisorDecisionEngine().decide(self._current_value("100"), (scenario_only, not_applicable, ev_ready), generated_at=AS_OF)

        self.assertEqual(decision.decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(len(decision.craft_candidates), 3)
        self.assertEqual([candidate.action_id for candidate in decision.rankable_candidates if candidate.action_id], ["dc:test:craft-action:craft-a"])
        self.assertEqual(len(decision.non_rankable_candidates), 2)

    def test_expected_value_result_is_reused_not_recalculated(self):
        craft = self._rankable_input("craft-a", net="999", gain="15")

        decision = AdvisorDecisionEngine().decide(self._current_value("100"), (craft,), generated_at=AS_OF)

        selected = next(candidate for candidate in decision.craft_candidates if candidate.candidate_id == decision.selected_candidate_id)
        self.assertEqual(selected.expected_value_result.net_expected_value.amount, Decimal("999"))
        self.assertEqual(selected.expected_gain_vs_sell_now.amount, Decimal("15"))

    def test_algorithm_version_provenance_and_immutability(self):
        current = self._current_value("100")
        craft = self._rankable_input("craft-a", net="115", gain="15")
        current_before = copy.deepcopy(current)
        craft_before = copy.deepcopy(craft)

        decision = AdvisorDecisionEngine().decide(current, (craft,), generated_at=AS_OF)

        self.assertEqual(current, current_before)
        self.assertEqual(craft, craft_before)
        self.assertEqual(decision.algorithm_version, ADVISOR_ALGORITHM_VERSION)
        self.assertEqual(decision.current_valuation_reference, ("current-evidence",))
        self.assertIn("synthetic-economy-snapshot", decision.economy_snapshot_ids)
        self.assertFalse(hasattr(decision, "expected_value"))

    def test_quiver_6_real_actions_remain_non_rankable_without_fabricated_probability(self):
        annulment = candidate_by_id(self.candidates, "dc:poe2:craft-action:orb-of-annulment")
        outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.item, self.affix_state, annulment.action, annulment.applicability)
        probability_model = CurrentResearchProbabilityProvider().get_probability_model(self.item, outcome_set)
        valuations = tuple(OutcomeValuation(state.outcome_id, self._current_value("100")) for state in outcome_set.hypothetical_states)
        scenario = ScenarioAnalysisService().analyze_action(self._current_value("100"), annulment, outcome_set, probability_model, valuations, AS_OF)
        ev = ExpectedValueEngine().calculate(scenario, probability_model, valuations, AS_OF)
        exalted = candidate_by_id(self.candidates, "dc:poe2:craft-action:exalted-orb")

        decision = AdvisorDecisionEngine().decide(
            self._current_value("100"),
            (AdvisorCraftInput(annulment, scenario, ev), AdvisorCraftInput(exalted, None, None)),
            generated_at=AS_OF,
        )

        self.assertEqual(ev.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertEqual(decision.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertEqual(decision.craft_candidates[0].status, AdvisorCandidateStatus.NON_RANKABLE_SCENARIO)
        self.assertEqual(decision.craft_candidates[1].status, AdvisorCandidateStatus.NON_RANKABLE_NOT_APPLICABLE)

    def _rankable_input(self, action_id: str, net: str, gain: str):
        action_id = self._action_id(action_id)
        candidate = self._base_candidate(action_id)
        scenario = self._scenario(DecisionReadiness.EV_READY)
        ev = ExpectedValueResult(
            status=ExpectedValueStatus.AVAILABLE,
            result_id=f"ev:{action_id}",
            action_id=action_id,
            scenario_analysis_id=scenario.analysis_id,
            source_item_id=scenario.source_item_id,
            gross_expected_outcome_value=normalized_exalted_value(Decimal(net) + Decimal("10")),
            craft_cost=normalized_exalted_value("10"),
            net_expected_value=normalized_exalted_value(net),
            current_item_value=normalized_exalted_value("100"),
            expected_gain_vs_sell_now=normalized_exalted_value(gain) if Decimal(gain) >= 0 else EconomicValue(Decimal(gain), "EXALTED_ECONOMIC_UNIT"),
            roi_on_craft_cost=Decimal(gain) / Decimal("10"),
            economy_snapshot_ids=("synthetic-economy-snapshot",),
            dataset_versions=("synthetic-dataset",),
            warnings=("synthetic EV-ready proof only",),
        )
        return AdvisorCraftInput(candidate, scenario, ev)

    def _base_candidate(self, action_id: str, status: CraftApplicabilityStatus = CraftApplicabilityStatus.APPLICABLE):
        action_id = self._action_id(action_id)
        candidate = candidate_by_id(self.candidates, "dc:poe2:craft-action:orb-of-annulment")
        action = replace(candidate.action, action_id=action_id)
        applicability = replace(candidate.applicability, action_id=action_id, status=status)
        return replace(candidate, action=action, applicability=applicability)

    def _scenario(self, readiness: DecisionReadiness):
        candidate = self._base_candidate("scenario-action")
        outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.item, self.affix_state, candidate.action, candidate.applicability)
        probability_model = CurrentResearchProbabilityProvider().get_probability_model(self.item, outcome_set)
        valuations = tuple(OutcomeValuation(state.outcome_id, self._current_value("100")) for state in outcome_set.hypothetical_states)
        scenario = ScenarioAnalysisService().analyze_action(self._current_value("100"), candidate, outcome_set, probability_model, valuations, AS_OF)
        return replace(
            scenario,
            action_id=candidate.action.action_id,
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
            warnings=("synthetic listing-derived valuation for Advisor tests",),
        )

    def _action_id(self, action_id: str) -> str:
        return action_id if ":" in action_id else f"dc:test:craft-action:{action_id}"


if __name__ == "__main__":
    unittest.main()
