import copy
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.domain import ComparableStrategy
from packages.shared.donniecraftshell_contracts.economy import DIVINE_ASSET_ID, EXALTED_ASSET_ID
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.poe_show_economy import load_normalized_economy_snapshot
from packages.shared.donniecraftshell_contracts.valuation import (
    ListingStatus,
    ManualListingObservation,
    ManualTradeProvider,
    ModifierComparableRole,
    ModifierComparableRoleAssignment,
    ModifierMatchMode,
    ValuationAggregator,
    ValuationEvidencePolicy,
    ValuationReadiness,
    build_comparable_query,
    evidence_set_from_results,
    subject_from_hypothetical_state,
    subject_from_parsed_item,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
CRAFTING_DATASET = ROOT / "data" / "normalized" / "crafting" / "crafting-actions-poe2-quiver-2026-08-12-research" / "actions.json"
AFFIX_CAPACITY_DATASET = ROOT / "data" / "normalized" / "crafting" / "affix-capacity-poe2-2026-08-12-research" / "capacity.json"
GAME_DATASET_VERSION = "poe2db-unknown-version-2026-08-12-task8c-fullx1"
ECONOMY_SNAPSHOT = ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff" / "economy_snapshot.json"
AS_OF = datetime(2026, 8, 11, 13, 30, tzinfo=timezone.utc)
LEAGUE = "Runes of Aldur"


def parsed_fixture(name: str):
    result = parse_clipboard_item((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert result.item is not None
    return result.item


def action_by_id(dataset, action_id: str):
    return next(action for action in dataset.actions if action.action_id == action_id)


def quiver_6_roles(item):
    explicit = item.explicit_modifiers
    return (
        ModifierComparableRoleAssignment(
            modifier=next(modifier for modifier in explicit if modifier.display_name == "Lacerating"),
            role=ModifierComparableRole.VALUE_DRIVING,
            reason="synthetic test-only role; not meta guidance",
        ),
        ModifierComparableRoleAssignment(
            modifier=next(modifier for modifier in explicit if modifier.display_name == "of the Archer"),
            role=ModifierComparableRole.VALUE_DRIVING,
            reason="synthetic test-only role; not meta guidance",
        ),
        ModifierComparableRoleAssignment(
            modifier=next(modifier for modifier in explicit if modifier.display_name == "of Calamity"),
            role=ModifierComparableRole.SUPPORTING,
            reason="synthetic test-only role; not meta guidance",
        ),
        ModifierComparableRoleAssignment(
            modifier=next(modifier for modifier in explicit if modifier.display_name == "of Destruction"),
            role=ModifierComparableRole.IGNORE_FOR_COMPARABLE,
            reason="synthetic test-only role; not meta guidance",
        ),
    )


class ValuationContractTests(unittest.TestCase):
    def setUp(self):
        self.item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        self.provider = ManualTradeProvider()
        self.economy_repo = EconomyRepository((load_normalized_economy_snapshot(ECONOMY_SNAPSHOT),))

    def test_current_item_to_valuation_subject(self):
        subject = subject_from_parsed_item(self.item, dataset_versions=(GAME_DATASET_VERSION,))

        self.assertEqual(subject.item_class, "Quivers")
        self.assertEqual(subject.base_type, "Primed Quiver")
        self.assertEqual(subject.source_item_analysis_id, self.item.analysis_id)
        self.assertIsNone(subject.hypothetical_state_id)
        self.assertIn(GAME_DATASET_VERSION, subject.dataset_versions)

    def test_hypothetical_item_to_valuation_subject(self):
        outcome_state = self._first_annulment_state()

        subject = subject_from_hypothetical_state(self.item, outcome_state, dataset_versions=(GAME_DATASET_VERSION,))

        self.assertEqual(subject.item_class, "Quivers")
        self.assertEqual(subject.source_item_analysis_id, self.item.analysis_id)
        self.assertEqual(subject.hypothetical_state_id, outcome_state.outcome_id)
        self.assertTrue(subject.warnings)

    def test_common_query_builder_works_for_current_and_hypothetical_subjects(self):
        roles = quiver_6_roles(self.item)
        current = subject_from_parsed_item(self.item)
        hypothetical = subject_from_hypothetical_state(self.item, self._first_annulment_state())

        current_query = build_comparable_query(current, roles, ComparableStrategy.STRICT, LEAGUE, AS_OF)
        hypothetical_query = build_comparable_query(hypothetical, roles, ComparableStrategy.STRICT, LEAGUE, AS_OF)

        self.assertEqual(current_query.item_class, hypothetical_query.item_class)
        self.assertEqual(len(current_query.included_modifier_constraints), len(hypothetical_query.included_modifier_constraints))

    def test_modifier_comparable_roles_preserved(self):
        roles = quiver_6_roles(self.item)

        self.assertEqual(roles[0].role, ModifierComparableRole.VALUE_DRIVING)
        self.assertEqual(roles[2].role, ModifierComparableRole.SUPPORTING)
        self.assertEqual(roles[3].role, ModifierComparableRole.IGNORE_FOR_COMPARABLE)
        self.assertIn("synthetic", roles[0].reason)

    def test_strict_query_uses_only_value_driving_constraints(self):
        query = build_comparable_query(
            subject_from_parsed_item(self.item),
            quiver_6_roles(self.item),
            ComparableStrategy.STRICT,
            LEAGUE,
            AS_OF,
        )

        self.assertEqual(len(query.included_modifier_constraints), 2)
        self.assertTrue(all(constraint.role == ModifierComparableRole.VALUE_DRIVING for constraint in query.included_modifier_constraints))
        self.assertTrue(all(constraint.match_mode == ModifierMatchMode.EXACT for constraint in query.included_modifier_constraints))
        self.assertEqual(len(query.ignored_modifiers), 1)

    def test_moderate_query_records_explicit_relaxation(self):
        query = build_comparable_query(
            subject_from_parsed_item(self.item),
            quiver_6_roles(self.item),
            ComparableStrategy.MODERATE,
            LEAGUE,
            AS_OF,
        )

        self.assertTrue(query.relaxation_rules)
        self.assertTrue(all(constraint.match_mode == ModifierMatchMode.RELAXED for constraint in query.included_modifier_constraints))

    def test_no_automatic_build_equivalent_generation(self):
        query = build_comparable_query(
            subject_from_parsed_item(self.item),
            quiver_6_roles(self.item),
            ComparableStrategy.BUILD_EQUIVALENT,
            LEAGUE,
            AS_OF,
        )

        self.assertEqual(query.included_modifier_constraints, ())
        self.assertTrue(any("requires future modifier relevance" in warning for warning in query.warnings))

    def test_manual_trade_provider_makes_no_network_calls(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        workflow = self.provider.prepare_manual_workflow(query)

        self.assertFalse(workflow.capabilities.supports_automatic_search)
        self.assertTrue(workflow.capabilities.supports_manual_observations)
        self.assertIn("no network calls", workflow.warnings[0])
        self.assertIn("Open the official Path of Exile Trade site manually.", workflow.instructions)

    def test_manual_listing_observation_accepts_decimal(self):
        observation = self._observation(Decimal("5"), DIVINE_ASSET_ID)

        self.assertEqual(observation.amount, Decimal("5"))

    def test_divine_listing_converts_through_economy_repository(self):
        result = self.provider.result_from_observation(
            self._observation(Decimal("5"), DIVINE_ASSET_ID),
            self.economy_repo,
            AS_OF,
        )

        self.assertEqual(result.normalized_value.amount, Decimal("1691.0"))
        self.assertEqual(result.economy_snapshot_id, "economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff")

    def test_exalted_listing_remains_one_to_one_normalized(self):
        result = self.provider.result_from_observation(
            self._observation(Decimal("2400"), EXALTED_ASSET_ID),
            self.economy_repo,
            AS_OF,
        )

        self.assertEqual(result.normalized_value.amount, Decimal("2400"))

    def test_missing_conversion_is_unavailable_not_zero(self):
        result = self.provider.result_from_observation(
            self._observation(Decimal("5"), "dc:poe2:economy-asset:currency:missing"),
            self.economy_repo,
            AS_OF,
        )

        self.assertIsNone(result.normalized_value)
        self.assertNotEqual(result.normalized_value, Decimal("0"))
        self.assertTrue(any("Missing economy conversion" in warning for warning in result.warnings))

    def test_listing_is_not_realized_sale(self):
        with self.assertRaises(ValueError):
            self.provider.result_from_observation(
                self._observation(Decimal("5"), DIVINE_ASSET_ID),
                self.economy_repo,
                AS_OF,
            ).__class__(
                comparable_id="sold-test",
                query_id="query",
                provider="manual",
                external_listing_id="listing",
                listing_price=Decimal("5"),
                listing_currency_asset_id=DIVINE_ASSET_ID,
                normalized_value=None,
                item_summary=None,
                matched_constraints=(),
                observed_at=AS_OF,
                retrieved_at=AS_OF,
                league=LEAGUE,
                listing_status=ListingStatus.SOLD,
            )

    def test_duplicate_listing_ids_detected(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        first = self.provider.result_from_observation(self._observation(Decimal("5"), DIVINE_ASSET_ID, listing_id="abc"), self.economy_repo, AS_OF)
        second = self.provider.result_from_observation(self._observation(Decimal("5.5"), DIVINE_ASSET_ID, listing_id="abc"), self.economy_repo, AS_OF)
        evidence = evidence_set_from_results(query, self.provider.provider_name, (first, second))

        self.assertEqual(evidence.duplicate_listing_ids, ("abc",))
        self.assertTrue(any("Duplicate listing IDs" in warning for warning in evidence.warnings))

    def test_zero_comparables_is_insufficient_data(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        evidence = evidence_set_from_results(query, self.provider.provider_name, ())

        self.assertEqual(evidence.readiness, ValuationReadiness.INSUFFICIENT_DATA)

    def test_configurable_readiness_threshold(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        result = self.provider.result_from_observation(self._observation(Decimal("5"), DIVINE_ASSET_ID), self.economy_repo, AS_OF)

        partial = evidence_set_from_results(query, self.provider.provider_name, (result,), ValuationEvidencePolicy(minimum_usable_comparables=2))
        ready = evidence_set_from_results(query, self.provider.provider_name, (result,), ValuationEvidencePolicy(minimum_usable_comparables=1))

        self.assertEqual(partial.readiness, ValuationReadiness.PARTIAL)
        self.assertEqual(ready.readiness, ValuationReadiness.READY)

    def test_unusable_comparable_does_not_count_as_usable_evidence(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        result = self.provider.result_from_observation(self._observation(Decimal("5"), "dc:poe2:economy-asset:currency:missing"), self.economy_repo, AS_OF)
        evidence = evidence_set_from_results(query, self.provider.provider_name, (result,))

        self.assertEqual(len(evidence.usable_results), 0)
        self.assertEqual(evidence.unusable_result_count, 1)
        self.assertEqual(evidence.readiness, ValuationReadiness.INSUFFICIENT_DATA)

    def test_evidence_set_retains_economy_snapshot_identity_and_query(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        result = self.provider.result_from_observation(self._observation(Decimal("5"), DIVINE_ASSET_ID), self.economy_repo, AS_OF)
        evidence = evidence_set_from_results(query, self.provider.provider_name, (result,))

        self.assertIs(evidence.query, query)
        self.assertIn("economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff", evidence.economy_snapshot_ids)

    def test_no_market_estimate_produced_from_evidence_alone(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        result = self.provider.result_from_observation(self._observation(Decimal("5"), DIVINE_ASSET_ID), self.economy_repo, AS_OF)
        evidence = evidence_set_from_results(query, self.provider.provider_name, (result,), ValuationEvidencePolicy(minimum_usable_comparables=1))

        valuation = ValuationAggregator().aggregate(evidence)

        self.assertEqual(valuation.readiness, ValuationReadiness.READY)
        self.assertIsNone(valuation.estimated_value)
        self.assertIn("does not implement", valuation.warnings[0])

    def test_original_item_and_outcome_state_remain_immutable(self):
        item_before = copy.deepcopy(self.item)
        outcome_state = self._first_annulment_state()
        outcome_before = copy.deepcopy(outcome_state)

        subject_from_parsed_item(self.item)
        subject_from_hypothetical_state(self.item, outcome_state)

        self.assertEqual(self.item, item_before)
        self.assertEqual(outcome_state, outcome_before)

    def _observation(self, amount: Decimal, currency_asset_id: str, listing_id: str | None = "synthetic-listing"):
        return ManualListingObservation(
            observation_id=f"synthetic-observation-{amount}-{currency_asset_id}",
            query_id="synthetic-query",
            amount=amount,
            currency_asset_id=currency_asset_id,
            league=LEAGUE,
            observed_at=AS_OF,
            external_listing_id=listing_id,
            item_summary="synthetic test listing observation",
            warnings=("synthetic test-only observation; not production market evidence",),
        )

    def _first_annulment_state(self):
        crafting_dataset = load_crafting_dataset(CRAFTING_DATASET)
        craft_engine = CraftActionEngine(crafting_dataset)
        affix_resolver = AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET))
        action = action_by_id(crafting_dataset, "dc:poe2:craft-action:orb-of-annulment")
        affix_state = affix_resolver.resolve(self.item)
        applicability = craft_engine.evaluate_action(action, self.item, affix_state)
        outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.item, affix_state, action, applicability)
        return outcome_set.hypothetical_states[0]


if __name__ == "__main__":
    unittest.main()
