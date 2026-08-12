import copy
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.craft_action_candidates import get_action_candidates
from packages.shared.donniecraftshell_contracts.economy_costs import CraftMaterialCost
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import (
    CraftActionEngine,
    CraftApplicabilityStatus,
    load_crafting_dataset,
)
from packages.shared.donniecraftshell_contracts.economy import FreshnessState, normalized_exalted_value
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.poe_show_economy import load_normalized_economy_snapshot
from packages.shared.donniecraftshell_contracts.probability import (
    CurrentResearchProbabilityProvider,
    OutcomeProbability,
    OutcomeProbabilityModel,
    ProbabilityCompleteness,
)
from packages.shared.donniecraftshell_contracts.scenario_analysis import (
    DecisionReadiness,
    OutcomeValuation,
    ScenarioAnalysisService,
    ValuationCompleteness,
)
from packages.shared.donniecraftshell_contracts.valuation import (
    ValuationEstimateType,
    ValuationReadiness,
    ValuationResult,
)


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


class ScenarioAnalysisTests(unittest.TestCase):
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
        self.service = ScenarioAnalysisService()
        self.affix_state = self.affix_resolver.resolve(self.item)
        self.candidates = get_action_candidates(self.item, self.affix_state, self.craft_engine, self.repository, LEAGUE, AS_OF)

    def test_quiver_6_annulment_partial_valuations_unknown_probability_is_scenario_only(self):
        candidate, outcome_set, probability_model = self._annulment_case()
        valuations = self._outcome_valuations(outcome_set, ("1200", "1300", "1500", "1600"))

        analysis = self.service.analyze_action(self._valuation("current", "1400"), candidate, outcome_set, probability_model, valuations, AS_OF)

        self.assertEqual(candidate.applicability.status, CraftApplicabilityStatus.APPLICABLE)
        self.assertEqual(outcome_set.hypothetical_states.__len__(), 6)
        self.assertEqual(analysis.decision_readiness, DecisionReadiness.SCENARIO_ONLY)
        self.assertEqual(analysis.valuation_completeness, ValuationCompleteness.PARTIAL)
        self.assertEqual(analysis.valued_outcome_count, 4)
        self.assertEqual(analysis.unvalued_outcome_count, 2)
        self.assertEqual(analysis.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertFalse(analysis.ev_readiness)
        self.assertEqual(analysis.best_valuated_outcome.gross_value.amount, Decimal("1600"))
        self.assertEqual(analysis.worst_valuated_outcome.gross_value.amount, Decimal("1200"))
        self.assertEqual(analysis.median_valuated_outcome.amount, Decimal("1400"))
        self.assertTrue(any("valuated outcomes only" in warning for warning in analysis.warnings))
        self.assertFalse(hasattr(analysis, "recommendation"))

    def test_complete_valuations_unknown_probability_remains_scenario_only(self):
        candidate, outcome_set, probability_model = self._annulment_case()
        valuations = self._outcome_valuations(outcome_set, ("1100", "1200", "1300", "1400", "1500", "1600"))

        analysis = self.service.analyze_action(self._valuation("current", "1400"), candidate, outcome_set, probability_model, valuations, AS_OF)

        self.assertEqual(analysis.valuation_completeness, ValuationCompleteness.COMPLETE)
        self.assertEqual(analysis.decision_readiness, DecisionReadiness.SCENARIO_ONLY)
        self.assertFalse(analysis.probability_readiness)
        self.assertFalse(analysis.ev_readiness)

    def test_synthetic_complete_probability_detects_ev_ready_without_calculating_ev(self):
        candidate, outcome_set, _ = self._annulment_case()
        candidate = self._with_synthetic_complete_cost(candidate)
        valuations = self._outcome_valuations(outcome_set, ("1100", "1200", "1300", "1400", "1500", "1600"))
        probability_model = self._complete_probability_model(outcome_set)

        analysis = self.service.analyze_action(self._valuation("current", "1400"), candidate, outcome_set, probability_model, valuations, AS_OF)

        self.assertEqual(analysis.decision_readiness, DecisionReadiness.EV_READY)
        self.assertTrue(analysis.probability_readiness)
        self.assertTrue(analysis.valuation_readiness)
        self.assertTrue(analysis.ev_readiness)
        self.assertFalse(hasattr(analysis, "expected_value"))
        self.assertTrue(any("does not calculate EV" in warning for warning in analysis.warnings))

    def test_partial_probability_mass_is_not_ev_ready(self):
        candidate, outcome_set, _ = self._annulment_case()
        valuations = self._outcome_valuations(outcome_set, ("1100", "1200", "1300", "1400", "1500", "1600"))
        probability_model = OutcomeProbabilityModel(
            action_id=outcome_set.action_id,
            source_outcome_set_id=f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}:synthetic-partial",
            outcome_probabilities=(OutcomeProbability(outcome_set.hypothetical_states[0].outcome_id, Decimal("0.5")),),
            probability_completeness=ProbabilityCompleteness.PARTIAL,
            warnings=("synthetic incomplete probability mass",),
        )

        analysis = self.service.analyze_action(self._valuation("current", "1400"), candidate, outcome_set, probability_model, valuations, AS_OF)

        self.assertEqual(analysis.decision_readiness, DecisionReadiness.SCENARIO_ONLY)
        self.assertFalse(analysis.probability_readiness)
        self.assertFalse(analysis.ev_readiness)

    def test_zero_usable_valuations_is_insufficient_data(self):
        candidate, outcome_set, probability_model = self._annulment_case()

        analysis = self.service.analyze_action(self._valuation("current", "1400"), candidate, outcome_set, probability_model, (), AS_OF)

        self.assertEqual(analysis.decision_readiness, DecisionReadiness.INSUFFICIENT_DATA)
        self.assertEqual(analysis.valuation_completeness, ValuationCompleteness.NONE)
        self.assertEqual(analysis.valued_outcome_count, 0)

    def test_full_quiver_exalted_not_applicable_does_not_attempt_executable_scenario(self):
        candidate = candidate_by_id(self.candidates, "dc:poe2:craft-action:exalted-orb")
        action = candidate.action
        applicability = candidate.applicability
        outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.item, self.affix_state, action, applicability)
        probability_model = CurrentResearchProbabilityProvider().get_probability_model(self.item, outcome_set)

        analysis = self.service.analyze_action(self._valuation("current", "1400"), candidate, outcome_set, probability_model, (), AS_OF)

        self.assertEqual(candidate.applicability.status, CraftApplicabilityStatus.NOT_APPLICABLE)
        self.assertEqual(analysis.decision_readiness, DecisionReadiness.NOT_APPLICABLE)
        self.assertEqual(analysis.outcome_count, 0)
        self.assertFalse(analysis.ev_readiness)

    def test_missing_action_cost_never_ev_ready(self):
        candidate, outcome_set, _ = self._annulment_case()
        missing_cost = replace(candidate.material_cost, complete=False, total=None, freshness=FreshnessState.UNAVAILABLE)
        candidate = replace(candidate, material_cost=missing_cost, cost_complete=False, cost_freshness=FreshnessState.UNAVAILABLE)
        valuations = self._outcome_valuations(outcome_set, ("1100", "1200", "1300", "1400", "1500", "1600"))

        analysis = self.service.analyze_action(self._valuation("current", "1400"), candidate, outcome_set, self._complete_probability_model(outcome_set), valuations, AS_OF)

        self.assertEqual(analysis.decision_readiness, DecisionReadiness.SCENARIO_ONLY)
        self.assertFalse(analysis.ev_readiness)
        self.assertTrue(any("cost is incomplete" in reason for reason in analysis.reasons))

    def test_missing_current_valuation_never_ev_ready(self):
        candidate, outcome_set, _ = self._annulment_case()
        valuations = self._outcome_valuations(outcome_set, ("1100", "1200", "1300", "1400", "1500", "1600"))

        analysis = self.service.analyze_action(None, candidate, outcome_set, self._complete_probability_model(outcome_set), valuations, AS_OF)

        self.assertEqual(analysis.decision_readiness, DecisionReadiness.SCENARIO_ONLY)
        self.assertFalse(analysis.ev_readiness)
        self.assertTrue(any("Current item" in reason for reason in analysis.reasons))

    def test_net_scenario_value_subtracts_action_cost_with_decimal(self):
        candidate, outcome_set, probability_model = self._annulment_case()
        candidate = self._with_synthetic_complete_cost(candidate, "25")
        valuations = self._outcome_valuations(outcome_set, ("1200", "1300", "1500", "1600"))

        analysis = self.service.analyze_action(self._valuation("current", "1400"), candidate, outcome_set, probability_model, valuations, AS_OF)

        self.assertIsNotNone(candidate.material_cost.total)
        self.assertEqual(
            analysis.best_valuated_outcome.net_after_action_cost.amount,
            analysis.best_valuated_outcome.gross_value.amount - candidate.material_cost.total.amount,
        )

    def test_provenance_dataset_identities_and_immutability_are_retained(self):
        candidate, outcome_set, probability_model = self._annulment_case()
        valuations = self._outcome_valuations(outcome_set, ("1100", "1200", "1300", "1400", "1500", "1600"))
        item_before = copy.deepcopy(self.item)
        outcome_before = copy.deepcopy(outcome_set)
        probability_before = copy.deepcopy(probability_model)
        valuation_before = copy.deepcopy(valuations)

        analysis = self.service.analyze_action(self._valuation("current", "1400"), candidate, outcome_set, probability_model, valuations, AS_OF)

        self.assertEqual(self.item, item_before)
        self.assertEqual(outcome_set, outcome_before)
        self.assertEqual(probability_model, probability_before)
        self.assertEqual(valuations, valuation_before)
        self.assertEqual(analysis.outcome_set_id, f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}")
        self.assertIn("current-evidence", analysis.valuation_evidence_ids)
        self.assertTrue(analysis.economy_snapshot_ids)
        self.assertFalse(hasattr(analysis, "rank"))

    def _annulment_case(self):
        candidate = candidate_by_id(self.candidates, "dc:poe2:craft-action:orb-of-annulment")
        outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.item, self.affix_state, candidate.action, candidate.applicability)
        probability_model = CurrentResearchProbabilityProvider().get_probability_model(self.item, outcome_set)
        return candidate, outcome_set, probability_model

    def _valuation(self, label: str, amount: str):
        return ValuationResult(
            readiness=ValuationReadiness.READY,
            estimate_type=ValuationEstimateType.LISTING_DERIVED,
            estimated_value=normalized_exalted_value(Decimal(amount)),
            plausible_low=normalized_exalted_value(Decimal(amount) - Decimal("50")),
            plausible_high=normalized_exalted_value(Decimal(amount) + Decimal("50")),
            comparable_count=3,
            source_evidence_ids=(f"{label}-evidence",),
            economy_snapshot_ids=("synthetic-economy-snapshot",),
            warnings=("synthetic test-only listing-derived valuation; not production market evidence",),
        )

    def _outcome_valuations(self, outcome_set, amounts: tuple[str, ...]):
        return tuple(
            OutcomeValuation(
                outcome_id=state.outcome_id,
                valuation=self._valuation(f"outcome-{index}", amount),
                warnings=("synthetic test-only outcome valuation",),
            )
            for index, (state, amount) in enumerate(zip(outcome_set.hypothetical_states, amounts), start=1)
        )

    def _complete_probability_model(self, outcome_set):
        probability = Decimal("1") / Decimal(len(outcome_set.hypothetical_states))
        probabilities = tuple(
            OutcomeProbability(state.outcome_id, probability)
            for state in outcome_set.hypothetical_states
        )
        return OutcomeProbabilityModel(
            action_id=outcome_set.action_id,
            source_outcome_set_id=f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}:synthetic-complete",
            outcome_probabilities=probabilities,
            probability_completeness=ProbabilityCompleteness.COMPLETE,
            dataset_versions=("synthetic-probability-dataset",),
            warnings=("synthetic complete probability model for readiness gate only",),
        )

    def _with_synthetic_complete_cost(self, candidate, amount: str = "25"):
        cost = CraftMaterialCost(
            lines=(),
            total=normalized_exalted_value(Decimal(amount)),
            complete=True,
            freshness=FreshnessState.FRESH,
            warnings=("synthetic complete action cost for readiness gate only",),
        )
        return replace(candidate, material_cost=cost, cost_complete=True, cost_freshness=FreshnessState.FRESH)


if __name__ == "__main__":
    unittest.main()
