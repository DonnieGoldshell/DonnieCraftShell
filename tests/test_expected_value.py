import copy
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.craft_action_candidates import get_action_candidates
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.domain import EconomicValue
from packages.shared.donniecraftshell_contracts.economy import FreshnessState, normalized_exalted_value
from packages.shared.donniecraftshell_contracts.economy_costs import CraftMaterialCost
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.expected_value import (
    EXPECTED_VALUE_ALGORITHM_VERSION,
    ExpectedValueEngine,
    ExpectedValueStatus,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.poe_show_economy import load_normalized_economy_snapshot
from packages.shared.donniecraftshell_contracts.probability import (
    CurrentResearchProbabilityProvider,
    OutcomeProbability,
    OutcomeProbabilityModel,
    ProbabilityCompleteness,
)
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


class ExpectedValueEngineTests(unittest.TestCase):
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
        self.scenario_service = ScenarioAnalysisService()
        self.ev_engine = ExpectedValueEngine()

    def test_synthetic_expected_value_formula(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.AVAILABLE)
        self.assertEqual(result.gross_expected_outcome_value.amount, Decimal("125.00"))
        self.assertEqual(result.craft_cost.amount, Decimal("10"))
        self.assertEqual(result.net_expected_value.amount, Decimal("115.00"))
        self.assertEqual(result.current_item_value.amount, Decimal("100"))
        self.assertEqual(result.expected_gain_vs_sell_now.amount, Decimal("15.00"))
        self.assertEqual(result.roi_on_craft_cost, Decimal("1.50"))
        self.assertEqual(result.methodology_version, EXPECTED_VALUE_ALGORITHM_VERSION)

    def test_outcome_contribution_breakdown_and_sum_invariant(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        contributions = {item.outcome_id: item for item in result.outcome_contributions}
        self.assertEqual(contributions["outcome-a"].weighted_contribution.amount, Decimal("20.00"))
        self.assertEqual(contributions["outcome-b"].weighted_contribution.amount, Decimal("105.00"))
        self.assertEqual(sum((item.weighted_contribution.amount for item in result.outcome_contributions), Decimal("0")), result.gross_expected_outcome_value.amount)

    def test_deterministic_probability_one_outcome(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case(
            probabilities=(("outcome-a", "1"),),
            values=(("outcome-a", "140"),),
        )

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.gross_expected_outcome_value.amount, Decimal("140"))
        self.assertEqual(result.net_expected_value.amount, Decimal("130"))

    def test_zero_probability_outcome_is_retained_with_zero_contribution(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case(
            probabilities=(("outcome-a", "0"), ("outcome-b", "1")),
            values=(("outcome-a", "80"), ("outcome-b", "140")),
        )

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        zero = next(item for item in result.outcome_contributions if item.outcome_id == "outcome-a")
        self.assertEqual(zero.probability, Decimal("0"))
        self.assertEqual(zero.weighted_contribution.amount, Decimal("0"))
        self.assertEqual(len(result.outcome_contributions), 2)

    def test_zero_craft_cost_has_no_roi(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case(cost="0")

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertIsNone(result.roi_on_craft_cost)

    def test_ev_bounds_when_all_valuation_bounds_exist(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.low_net_expected_value.amount, Decimal("110.00"))
        self.assertEqual(result.high_net_expected_value.amount, Decimal("120.00"))

    def test_missing_bound_makes_ev_range_unavailable(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()
        first = valuations[0].valuation
        valuations = (replace(valuations[0], valuation=replace(first, plausible_low=None)), valuations[1])

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.AVAILABLE)
        self.assertIsNone(result.low_net_expected_value)
        self.assertIsNone(result.high_net_expected_value)

    def test_scenario_not_ev_ready_blocks_calculation(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()
        scenario = replace(scenario, decision_readiness=DecisionReadiness.SCENARIO_ONLY, ev_readiness=False)

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertIn("ScenarioAnalysis is not EV_READY.", result.unavailable_reasons)

    def test_incomplete_probability_blocks_ev(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()
        probability_model = OutcomeProbabilityModel(
            action_id=probability_model.action_id,
            source_outcome_set_id=probability_model.source_outcome_set_id,
            outcome_probabilities=(OutcomeProbability("outcome-a", Decimal("0.25")),),
            probability_completeness=ProbabilityCompleteness.PARTIAL,
        )

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertTrue(any("Probability model is not COMPLETE" in reason for reason in result.unavailable_reasons))

    def test_missing_outcome_valuation_blocks_ev(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()

        result = self.ev_engine.calculate(scenario, probability_model, valuations[:1], AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertTrue(any("Outcome IDs do not align" in reason for reason in result.unavailable_reasons))

    def test_mismatched_outcome_ids_block_ev(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()
        valuations = (replace(valuations[0], outcome_id="wrong-outcome"), valuations[1])

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertTrue(any("Outcome IDs do not align" in reason for reason in result.unavailable_reasons))

    def test_missing_current_valuation_blocks_ev(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()
        scenario = replace(scenario, current_valuation=None, ev_readiness=True, decision_readiness=DecisionReadiness.EV_READY)

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertTrue(any("Current item valuation is missing" in reason for reason in result.unavailable_reasons))

    def test_incomplete_craft_cost_blocks_ev(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()
        cost = replace(scenario.action_material_cost, complete=False, total=None)
        scenario = replace(scenario, action_material_cost=cost, ev_readiness=True, decision_readiness=DecisionReadiness.EV_READY)

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertTrue(any("Craft material cost is incomplete" in reason for reason in result.unavailable_reasons))

    def test_unnormalized_economic_value_blocks_ev(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()
        bad_valuation = replace(valuations[0].valuation, estimated_value=EconomicValue(Decimal("80"), "DIVINE"))
        valuations = (replace(valuations[0], valuation=bad_valuation), valuations[1])

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertTrue(any("not normalized" in reason for reason in result.unavailable_reasons))

    def test_missing_dataset_references_block_ev(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()
        scenario = replace(scenario, dataset_versions=(), ev_readiness=True, decision_readiness=DecisionReadiness.EV_READY)

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertTrue(any("dataset version" in reason for reason in result.unavailable_reasons))

    def test_quiver_6_real_annulment_remains_ev_unavailable(self):
        candidate = candidate_by_id(self.candidates, "dc:poe2:craft-action:orb-of-annulment")
        outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.item, self.affix_state, candidate.action, candidate.applicability)
        probability_model = CurrentResearchProbabilityProvider().get_probability_model(self.item, outcome_set)
        valuations = tuple(
            OutcomeValuation(state.outcome_id, self._valuation(state.outcome_id, "100"))
            for state in outcome_set.hypothetical_states
        )
        scenario = self.scenario_service.analyze_action(self._valuation("current", "100"), candidate, outcome_set, probability_model, valuations, AS_OF)

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(probability_model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertEqual(result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertTrue(any("ScenarioAnalysis is not EV_READY" in reason for reason in result.unavailable_reasons))

    def test_no_ranking_or_recommendation_and_inputs_immutable(self):
        scenario, probability_model, valuations = self._synthetic_ev_ready_case()
        scenario_before = copy.deepcopy(scenario)
        probability_before = copy.deepcopy(probability_model)
        valuations_before = copy.deepcopy(valuations)

        result = self.ev_engine.calculate(scenario, probability_model, valuations, AS_OF)

        self.assertEqual(scenario, scenario_before)
        self.assertEqual(probability_model, probability_before)
        self.assertEqual(valuations, valuations_before)
        self.assertFalse(hasattr(result, "rank"))
        self.assertFalse(hasattr(result, "recommendation"))

    def _synthetic_ev_ready_case(
        self,
        probabilities: tuple[tuple[str, str], ...] = (("outcome-a", "0.25"), ("outcome-b", "0.75")),
        values: tuple[tuple[str, str], ...] = (("outcome-a", "80"), ("outcome-b", "140")),
        cost: str = "10",
    ):
        candidate, outcome_set, _ = self._annulment_case()
        candidate = self._with_synthetic_complete_cost(candidate, cost)
        probability_model = OutcomeProbabilityModel(
            action_id=outcome_set.action_id,
            source_outcome_set_id=f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}:synthetic-ev-ready",
            outcome_probabilities=tuple(
                OutcomeProbability(outcome_id, Decimal(probability))
                for outcome_id, probability in probabilities
            ),
            probability_completeness=ProbabilityCompleteness.COMPLETE,
            dataset_versions=("synthetic-probability-dataset",),
            warnings=("synthetic complete probability model for EV gate only",),
        )
        valuations = tuple(
            OutcomeValuation(outcome_id, self._valuation(outcome_id, amount))
            for outcome_id, amount in values
        )
        synthetic_outcome_ids = tuple(outcome_id for outcome_id, _ in values)
        synthetic_states = tuple(
            replace(state, outcome_id=outcome_id)
            for state, outcome_id in zip(outcome_set.hypothetical_states, synthetic_outcome_ids)
        )
        outcome_set = replace(outcome_set, hypothetical_states=synthetic_states)
        scenario = self.scenario_service.analyze_action(
            self._valuation("current", "100"),
            candidate,
            outcome_set,
            probability_model,
            valuations,
            AS_OF,
        )
        scenario = replace(
            scenario,
            decision_readiness=DecisionReadiness.EV_READY,
            ev_readiness=True,
            probability_readiness=True,
            valuation_readiness=True,
            dataset_versions=("synthetic-crafting-dataset", "synthetic-probability-dataset"),
            economy_snapshot_ids=("synthetic-economy-snapshot",),
            valuation_evidence_ids=("current-evidence", "outcome-a-evidence", "outcome-b-evidence"),
        )
        return scenario, probability_model, valuations

    def _annulment_case(self):
        candidate = candidate_by_id(self.candidates, "dc:poe2:craft-action:orb-of-annulment")
        outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.item, self.affix_state, candidate.action, candidate.applicability)
        probability_model = CurrentResearchProbabilityProvider().get_probability_model(self.item, outcome_set)
        return candidate, outcome_set, probability_model

    def _with_synthetic_complete_cost(self, candidate, amount: str):
        cost = CraftMaterialCost(
            lines=(),
            total=normalized_exalted_value(Decimal(amount)),
            complete=True,
            freshness=FreshnessState.FRESH,
            warnings=("synthetic complete action cost for EV gate only",),
        )
        return replace(candidate, material_cost=cost, cost_complete=True, cost_freshness=FreshnessState.FRESH)

    def _valuation(self, label: str, amount: str):
        return ValuationResult(
            readiness=ValuationReadiness.READY,
            estimate_type=ValuationEstimateType.LISTING_DERIVED,
            estimated_value=normalized_exalted_value(Decimal(amount)),
            plausible_low=normalized_exalted_value(Decimal(amount) - Decimal("5")),
            plausible_high=normalized_exalted_value(Decimal(amount) + Decimal("5")),
            comparable_count=3,
            source_evidence_ids=(f"{label}-evidence",),
            economy_snapshot_ids=("synthetic-economy-snapshot",),
            warnings=("synthetic test-only valuation; not production market evidence",),
        )


if __name__ == "__main__":
    unittest.main()
