import copy
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.advisor_decision import AdvisorDecisionType
from packages.shared.donniecraftshell_contracts.advisor_orchestration import (
    AdvisorAnalysisRequest,
    AdvisorAnalysisStatus,
    CraftAdvisorOrchestrator,
    EvidenceReadinessCategory,
    EvidenceReadinessStatus,
    MissingRequirementKind,
)
from packages.shared.donniecraftshell_contracts.advisor_risk import AdvisorRiskContext, RiskProfile
from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.domain import GameContext
from packages.shared.donniecraftshell_contracts.economy import (
    EXALTED_ASSET_ID,
    ORB_OF_ANNULMENT_ASSET_ID,
    EconomyCategory,
    EconomyQuote,
    EconomySnapshot,
    FreshnessState,
    normalized_exalted_value,
)
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.expected_value import ExpectedValueStatus
from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
from packages.shared.donniecraftshell_contracts.parser import ParseResult, parse_clipboard_item
from packages.shared.donniecraftshell_contracts.poe_show_economy import load_normalized_economy_snapshot
from packages.shared.donniecraftshell_contracts.probability import OutcomeProbability, OutcomeProbabilityModel, ProbabilityCompleteness
from packages.shared.donniecraftshell_contracts.scenario_analysis import DecisionReadiness
from packages.shared.donniecraftshell_contracts.valuation import ValuationEstimateType, ValuationReadiness, ValuationResult


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
GAME_DATASET_ID = "poe2db-unknown-version-2026-08-12-task8c-fullx1"
CRAFTING_DATASET_ID = "crafting-actions-poe2-quiver-2026-08-12-research"
AFFIX_CAPACITY_DATASET_ID = "affix-capacity-poe2-2026-08-12-research"
GAME_DATASET = ROOT / "data" / "normalized" / GAME_DATASET_ID / "game_data.json"
CRAFTING_DATASET = ROOT / "data" / "normalized" / "crafting" / CRAFTING_DATASET_ID / "actions.json"
AFFIX_CAPACITY_DATASET = ROOT / "data" / "normalized" / "crafting" / AFFIX_CAPACITY_DATASET_ID / "capacity.json"
CURRENCY_SNAPSHOT = ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff" / "economy_snapshot.json"
RITUAL_SNAPSHOT = ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff11a-0000-7000-8000-000000000001" / "economy_snapshot.json"
ESSENCE_SNAPSHOT = ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff11a-0000-7000-8000-000000000002" / "economy_snapshot.json"
AS_OF = datetime(2026, 8, 11, 13, 30, tzinfo=timezone.utc)
LEAGUE = "Runes of Aldur"


class CompleteSyntheticProbabilityProvider:
    """Synthetic test-only provider proving orchestration plumbing."""

    def get_probability_model(self, item, outcome_set, context=None):
        count = len(outcome_set.hypothetical_states)
        base_probability = Decimal("1") / Decimal(count) if count else Decimal("1")
        probabilities = [base_probability for _ in outcome_set.hypothetical_states]
        if probabilities:
            probabilities[-1] = Decimal("1") - sum(probabilities[:-1], Decimal("0"))
        return OutcomeProbabilityModel(
            action_id=outcome_set.action_id,
            source_outcome_set_id=f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}:synthetic-complete",
            outcome_probabilities=tuple(
                OutcomeProbability(state.outcome_id, probability)
                for state, probability in zip(outcome_set.hypothetical_states, probabilities)
            ),
            probability_completeness=ProbabilityCompleteness.COMPLETE,
            dataset_versions=("synthetic-probability-dataset",),
            warnings=("synthetic complete probability model for orchestration plumbing only",),
        )


class FailingEssenceOutcomeEngine(CraftOutcomeEngine):
    def enumerate_outcomes(self, item, affix_state, action, applicability, game_data_repository=None, game_data_dataset_version=None):
        if action.action_id.endswith(":essence-of-hysteria"):
            raise RuntimeError("synthetic action failure")
        return super().enumerate_outcomes(item, affix_state, action, applicability, game_data_repository, game_data_dataset_version)


class AdvisorOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.raw_quiver_6 = (FIXTURE_DIR / "quiver_6_crafted_desecrated_advanced.txt").read_text(encoding="utf-8")
        self.raw_normal_quiver = (FIXTURE_DIR / "quiver_3_normal_advanced.txt").read_text(encoding="utf-8")
        self.fixed_parse = parse_clipboard_item(self.raw_quiver_6)
        self.assertIsNotNone(self.fixed_parse.item)

    def test_real_quiver_6_without_valuation_stops_at_honest_blockers(self):
        result = self._orchestrator(parser=self._fixed_parser()).analyze(self._request())

        self.assertEqual(result.status, AdvisorAnalysisStatus.ANALYSIS_PARTIAL)
        self.assertEqual(result.parsed_item.base_type, "Primed Quiver")
        self.assertEqual(result.affix_state_resolution.open_prefix_count, 0)
        self.assertEqual(result.affix_state_resolution.open_suffix_count, 0)
        annulment = self._action(result, "dc:poe2:craft-action:orb-of-annulment")
        exalted = self._action(result, "dc:poe2:craft-action:exalted-orb")

        self.assertEqual(annulment.candidate.applicability.status.value, "APPLICABLE")
        self.assertEqual(len(annulment.outcome_set.hypothetical_states), 6)
        self.assertEqual(annulment.probability_model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertEqual(annulment.expected_value_result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertEqual(exalted.candidate.applicability.status.value, "NOT_APPLICABLE")
        self.assertIsNone(exalted.outcome_set)
        self.assertEqual(result.raw_advisor_decision.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        self.assertIsNone(result.risk_adjusted_decision)
        self.assertIn(MissingRequirementKind.CURRENT_VALUATION_EVIDENCE_REQUIRED, self._missing_kinds(result))
        self.assertIn(MissingRequirementKind.PROBABILITY_EVIDENCE_REQUIRED, self._missing_kinds(result))
        self.assertIn(MissingRequirementKind.OUTCOME_VALUATION_EVIDENCE_REQUIRED, self._missing_kinds(result))
        self.assertIn(MissingRequirementKind.ECONOMY_QUOTE_REQUIRED, self._missing_kinds(result))
        readiness = self._readiness(result)
        self.assertEqual(readiness[EvidenceReadinessCategory.CURRENT_ITEM_VALUATION].status, EvidenceReadinessStatus.MISSING)
        self.assertEqual(readiness[EvidenceReadinessCategory.ECONOMY_CRAFTING_COST].status, EvidenceReadinessStatus.MISSING)
        self.assertEqual(readiness[EvidenceReadinessCategory.PROBABILITY].status, EvidenceReadinessStatus.MISSING)
        self.assertEqual(readiness[EvidenceReadinessCategory.OUTCOME_VALUATION].status, EvidenceReadinessStatus.MISSING)
        economy_targets = readiness[EvidenceReadinessCategory.ECONOMY_CRAFTING_COST].targets
        self.assertTrue(any(target.asset_id == ORB_OF_ANNULMENT_ASSET_ID for target in economy_targets))
        probability_targets = readiness[EvidenceReadinessCategory.PROBABILITY].targets
        self.assertTrue(any(target.action_id == "dc:poe2:craft-action:orb-of-annulment" for target in probability_targets))
        outcome_targets = readiness[EvidenceReadinessCategory.OUTCOME_VALUATION].targets
        self.assertEqual(len(outcome_targets[0].outcome_ids), 6)

    def test_real_quiver_6_with_synthetic_valuation_remains_scenario_only(self):
        orchestrator = self._orchestrator(parser=self._fixed_parser())
        initial = orchestrator.analyze(self._request())
        annulment = self._action(initial, "dc:poe2:craft-action:orb-of-annulment")
        valuations = {
            state.outcome_id: self._valuation(state.outcome_id, Decimal("100") + Decimal(index))
            for index, state in enumerate(annulment.outcome_set.hypothetical_states)
        }

        result = orchestrator.analyze(self._request(current=self._valuation("current", "100"), outcome_vals=valuations))
        annulment = self._action(result, "dc:poe2:craft-action:orb-of-annulment")

        self.assertEqual(result.status, AdvisorAnalysisStatus.SCENARIO_READY)
        self.assertEqual(annulment.scenario_analysis.decision_readiness, DecisionReadiness.SCENARIO_ONLY)
        self.assertEqual(annulment.scenario_analysis.valued_outcome_count, 6)
        self.assertEqual(annulment.probability_model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertEqual(annulment.expected_value_result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertEqual(result.raw_advisor_decision.decision_type, AdvisorDecisionType.NO_RECOMMENDATION)
        readiness = self._readiness(result)
        self.assertEqual(readiness[EvidenceReadinessCategory.CURRENT_ITEM_VALUATION].status, EvidenceReadinessStatus.READY)
        self.assertEqual(readiness[EvidenceReadinessCategory.OUTCOME_VALUATION].status, EvidenceReadinessStatus.PARTIAL)
        self.assertEqual(readiness[EvidenceReadinessCategory.PROBABILITY].status, EvidenceReadinessStatus.MISSING)

    def test_fully_synthetic_ev_ready_vertical_pipeline_produces_advisor_and_risk_results(self):
        orchestrator = self._orchestrator(
            economy_repository=self._economy_with_annulment_quote(),
            parser=self._fixed_parser(),
            probability_provider=CompleteSyntheticProbabilityProvider(),
        )
        initial = orchestrator.analyze(self._request())
        annulment = self._action(initial, "dc:poe2:craft-action:orb-of-annulment")
        valuations = {
            state.outcome_id: self._valuation(state.outcome_id, "130")
            for state in annulment.outcome_set.hypothetical_states
        }
        risk = AdvisorRiskContext(bankroll=normalized_exalted_value("1000"), risk_profile=RiskProfile.AGGRESSIVE)

        result = orchestrator.analyze(self._request(current=self._valuation("current", "100"), outcome_vals=valuations, risk=risk))
        annulment = self._action(result, "dc:poe2:craft-action:orb-of-annulment")

        self.assertEqual(result.status, AdvisorAnalysisStatus.DECISION_READY)
        self.assertEqual(annulment.scenario_analysis.decision_readiness, DecisionReadiness.EV_READY)
        self.assertTrue(annulment.expected_value_result.available)
        self.assertEqual(annulment.expected_value_result.net_expected_value.amount, Decimal("120.0000000000000000000000000"))
        self.assertEqual(result.raw_advisor_decision.decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(result.risk_adjusted_decision.risk_adjusted_decision_type, AdvisorDecisionType.CRAFT)
        self.assertIn("synthetic-economy-snapshot-annulment", result.economy_snapshot_ids)

    def test_missing_economy_quote_keeps_action_applicable_but_blocks_ev(self):
        result = self._orchestrator(parser=self._fixed_parser()).analyze(self._request(current=self._valuation("current", "100")))
        annulment = self._action(result, "dc:poe2:craft-action:orb-of-annulment")

        self.assertEqual(annulment.candidate.applicability.status.value, "APPLICABLE")
        self.assertFalse(annulment.candidate.material_cost.complete)
        self.assertIsNone(annulment.candidate.material_cost.total)
        self.assertEqual(annulment.expected_value_result.status, ExpectedValueStatus.NOT_AVAILABLE)
        self.assertTrue(any(item.kind == MissingRequirementKind.ECONOMY_QUOTE_REQUIRED for item in annulment.missing_requirements))

    def test_unsupported_rarity_and_item_class_are_structured_results(self):
        rarity_result = self._orchestrator().analyze(self._request(raw=self.raw_normal_quiver))
        self.assertEqual(rarity_result.status, AdvisorAnalysisStatus.UNSUPPORTED_ITEM)
        self.assertIsNotNone(rarity_result.parsed_item)
        self.assertFalse(rarity_result.action_results)
        self.assertIsNone(rarity_result.raw_advisor_decision)

        non_quiver_parse = ParseResult(
            item=replace(self.fixed_parse.item, item_class="Bows"),
            detected_format=self.fixed_parse.detected_format,
            warnings=self.fixed_parse.warnings,
            unparsed_sections=self.fixed_parse.unparsed_sections,
        )
        non_quiver_result = self._orchestrator(parser=lambda raw, context=None: non_quiver_parse).analyze(self._request())
        self.assertEqual(non_quiver_result.status, AdvisorAnalysisStatus.UNSUPPORTED_ITEM)
        self.assertEqual(non_quiver_result.parsed_item.item_class, "Bows")

    def test_action_failure_isolated_and_other_actions_remain_available(self):
        result = self._orchestrator(parser=self._fixed_parser(), outcome_engine=FailingEssenceOutcomeEngine()).analyze(self._request())

        essence = self._action(result, "dc:poe2:craft-action:essence-of-hysteria")
        annulment = self._action(result, "dc:poe2:craft-action:orb-of-annulment")
        self.assertTrue(any("synthetic action failure" in warning for warning in essence.warnings))
        self.assertIsNotNone(annulment.outcome_set)
        self.assertEqual(len(annulment.outcome_set.hypothetical_states), 6)

    def test_missing_bankroll_risk_context_is_reported_without_changing_raw_decision(self):
        orchestrator = self._orchestrator(
            economy_repository=self._economy_with_annulment_quote(),
            parser=self._fixed_parser(),
            probability_provider=CompleteSyntheticProbabilityProvider(),
        )
        initial = orchestrator.analyze(self._request())
        valuations = {
            state.outcome_id: self._valuation(state.outcome_id, "130")
            for state in self._action(initial, "dc:poe2:craft-action:orb-of-annulment").outcome_set.hypothetical_states
        }

        result = orchestrator.analyze(
            self._request(
                current=self._valuation("current", "100"),
                outcome_vals=valuations,
                risk=AdvisorRiskContext(bankroll=None, risk_profile=RiskProfile.CONSERVATIVE),
            )
        )

        self.assertEqual(result.raw_advisor_decision.decision_type, AdvisorDecisionType.CRAFT)
        self.assertEqual(result.risk_adjusted_decision.risk_adjusted_decision_type, AdvisorDecisionType.SELL_NOW)
        self.assertTrue(any("Bankroll is missing" in reason for item in result.risk_adjusted_decision.risk_adjusted_candidates for reason in item.reasons))

    def test_request_requires_explicit_league_and_dataset_versions(self):
        with self.assertRaises(ValueError):
            AdvisorAnalysisRequest(self.raw_quiver_6, None, "", GAME_DATASET_ID, CRAFTING_DATASET_ID, AFFIX_CAPACITY_DATASET_ID)
        with self.assertRaises(ValueError):
            AdvisorAnalysisRequest(self.raw_quiver_6, None, LEAGUE, "", CRAFTING_DATASET_ID, AFFIX_CAPACITY_DATASET_ID)

    def test_result_retain_versions_league_uuid7_and_stable_component_outputs(self):
        orchestrator = self._orchestrator(parser=self._fixed_parser())
        request = self._request(game_context=GameContext(game="poe2", league=LEAGUE))

        first = orchestrator.analyze(request)
        second = orchestrator.analyze(request)

        self.assertEqual(uuid.UUID(first.analysis_id.removeprefix("advisor-analysis-")).version, 7)
        self.assertEqual(first.dataset_versions, (GAME_DATASET_ID, CRAFTING_DATASET_ID, AFFIX_CAPACITY_DATASET_ID))
        self.assertEqual(first.league, LEAGUE)
        self.assertEqual([item.action_id for item in first.action_results], [item.action_id for item in second.action_results])
        self.assertEqual([(item.kind, item.affected_action_id) for item in first.missing_requirements], [(item.kind, item.affected_action_id) for item in second.missing_requirements])

    def test_underlying_source_objects_remain_immutable(self):
        orchestrator = self._orchestrator(parser=self._fixed_parser())
        request = self._request(current=self._valuation("current", "100"))
        parse_before = copy.deepcopy(self.fixed_parse)
        valuation_before = copy.deepcopy(request.current_valuation)

        orchestrator.analyze(request)

        self.assertEqual(self.fixed_parse, parse_before)
        self.assertEqual(request.current_valuation, valuation_before)

    def _orchestrator(self, economy_repository=None, parser=None, probability_provider=None, outcome_engine=None):
        return CraftAdvisorOrchestrator(
            GameDataRepository.from_json_files((GAME_DATASET,)),
            AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET)),
            CraftActionEngine(load_crafting_dataset(CRAFTING_DATASET)),
            economy_repository or self._default_economy(),
            probability_provider=probability_provider,
            outcome_engine=outcome_engine,
            parser=parser,
        )

    def _request(self, raw=None, current=None, outcome_vals=None, risk=None, game_context=None):
        return AdvisorAnalysisRequest(
            raw_clipboard_text=raw or self.raw_quiver_6,
            game_context=game_context,
            league=LEAGUE,
            game_data_dataset_version=GAME_DATASET_ID,
            crafting_dataset_version=CRAFTING_DATASET_ID,
            affix_capacity_dataset_version=AFFIX_CAPACITY_DATASET_ID,
            current_valuation=current,
            outcome_valuations_by_outcome_id=outcome_vals,
            risk_context=risk,
            as_of=AS_OF,
        )

    def _default_economy(self):
        return EconomyRepository(
            (
                load_normalized_economy_snapshot(CURRENCY_SNAPSHOT),
                load_normalized_economy_snapshot(RITUAL_SNAPSHOT),
                load_normalized_economy_snapshot(ESSENCE_SNAPSHOT),
            )
        )

    def _economy_with_annulment_quote(self):
        quote = EconomyQuote(
            asset_id=ORB_OF_ANNULMENT_ASSET_ID,
            league=LEAGUE,
            normalized_value=normalized_exalted_value("10"),
            source_native_value=Decimal("10"),
            native_reference_asset_id=EXALTED_ASSET_ID,
            source="synthetic-test-economy",
            snapshot_id="synthetic-economy-snapshot-annulment",
            category=EconomyCategory.CURRENCY,
            observed_at=AS_OF,
            retrieved_at=AS_OF,
            freshness=FreshnessState.FRESH,
        )
        snapshot = EconomySnapshot(
            snapshot_id="synthetic-economy-snapshot-annulment",
            provider="synthetic-test-economy",
            game="poe2",
            league=LEAGUE,
            retrieved_at=AS_OF,
            freshness=FreshnessState.FRESH,
            quotes=(quote,),
            exchange_rates=(),
            observed_at=AS_OF,
            warnings=("synthetic test-only economy snapshot",),
        )
        return EconomyRepository((snapshot,))

    def _fixed_parser(self):
        return lambda raw, context=None: self.fixed_parse

    def _valuation(self, label: str, amount):
        amount = Decimal(amount)
        return ValuationResult(
            readiness=ValuationReadiness.READY,
            estimate_type=ValuationEstimateType.LISTING_DERIVED,
            estimated_value=normalized_exalted_value(amount),
            plausible_low=normalized_exalted_value(amount - Decimal("5")),
            plausible_high=normalized_exalted_value(amount + Decimal("5")),
            comparable_count=3,
            source_evidence_ids=(f"synthetic-{label}-evidence",),
            economy_snapshot_ids=("synthetic-economy-snapshot-annulment",),
            league=LEAGUE,
            observed_at=AS_OF,
            warnings=("synthetic test-only valuation; not production market evidence",),
        )

    def _action(self, result, action_id):
        return next(item for item in result.action_results if item.action_id == action_id)

    def _missing_kinds(self, result):
        return {item.kind for item in result.missing_requirements}

    def _readiness(self, result):
        self.assertIsNotNone(result.evidence_readiness)
        return {item.category: item for item in result.evidence_readiness.items}


if __name__ == "__main__":
    unittest.main()
