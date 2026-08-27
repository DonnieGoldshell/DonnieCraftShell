import copy
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.domain import ComparableStrategy
from packages.shared.donniecraftshell_contracts.economy import DIVINE_ASSET_ID, EXALTED_ASSET_ID, FreshnessState
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.poe_show_economy import load_normalized_economy_snapshot
from packages.shared.donniecraftshell_contracts.valuation import (
    ComparableQualityDeltaAssessor,
    ComparableExclusionReason,
    ComparableRelevanceAssessor,
    ComparableRelevanceBand,
    ComparableResult,
    ListingStatus,
    LiquidityStatus,
    ManualListingObservation,
    ManualTradeProvider,
    ModifierComparableRole,
    ModifierComparableRoleAssignment,
    ModifierMatchMode,
    ModifierQualityRelationship,
    ModifierRelevanceRelationship,
    StructuredComparableItem,
    ValuationAggregator,
    ValuationAggregationPolicy,
    ValuationEvidencePolicy,
    ValuationEstimateType,
    ValuationReadiness,
    build_comparable_query,
    decimal_median,
    decimal_quantile,
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


def structured_comparable(name: str) -> StructuredComparableItem:
    raw = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    result = parse_clipboard_item(raw)
    assert result.item is not None
    return StructuredComparableItem(
        raw_clipboard_text=result.item.raw_clipboard_text,
        parsed_item=result.item,
        detected_format=result.detected_format.value,
        warnings=result.warnings,
        unparsed_sections=result.unparsed_sections,
    )


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

    def test_gloom_barb_is_high_relevance_structural_comparable_for_quiver_6(self):
        comparable = structured_comparable("gloom_barb_visceral_quiver_comparable_advanced.txt")

        relevance = ComparableRelevanceAssessor().assess(self.item, comparable)

        self.assertEqual(relevance.band, ComparableRelevanceBand.HIGH)
        self.assertGreaterEqual(relevance.score, Decimal("0.75"))
        self.assertTrue(any("Both items are Quivers" in reason for reason in relevance.base_similarity))
        self.assertTrue(any("Base type differs" in reason for reason in relevance.base_similarity))
        self.assertTrue(any("Special item states differ" in reason for reason in relevance.base_similarity))
        self.assertGreaterEqual(len(relevance.matched_modifiers), 3)
        projectile_speed = next(
            item for item in relevance.matched_modifiers
            if item.current_display_name == "Nimble"
        )
        self.assertTrue(projectile_speed.tag_match)
        self.assertFalse(projectile_speed.roll_observation_match)
        self.assertTrue(projectile_speed.current_roll_values)
        self.assertTrue(projectile_speed.comparable_roll_values)
        relationships = {item.relationship for item in relevance.differing_modifiers}
        self.assertIn(ModifierRelevanceRelationship.TIER_DIFFERENCE, relationships)
        self.assertIn(ModifierRelevanceRelationship.ORIGIN_DIFFERENCE, relationships)
        crit_difference = next(
            item for item in relevance.differing_modifiers
            if item.current_display_name == "of Calamity"
        )
        self.assertEqual(crit_difference.comparable_display_name, "of Unmaking")
        self.assertEqual(crit_difference.current_tier, "3")
        self.assertEqual(crit_difference.comparable_tier, "1")
        destruction_difference = next(
            item for item in relevance.differing_modifiers
            if item.current_display_name == "of Destruction"
        )
        self.assertEqual(destruction_difference.current_origin, "NATURAL")
        self.assertEqual(destruction_difference.comparable_origin, "FRACTURED")

    def test_weaker_same_class_quiver_scores_lower_than_gloom_barb(self):
        assessor = ComparableRelevanceAssessor()
        strong = assessor.assess(self.item, structured_comparable("gloom_barb_visceral_quiver_comparable_advanced.txt"))
        weak = assessor.assess(self.item, structured_comparable("quiver_4_magic_advanced.txt"))

        assert strong.score is not None and weak.score is not None
        self.assertLess(weak.score, strong.score)
        self.assertIn(weak.band, {ComparableRelevanceBand.LOW, ComparableRelevanceBand.MEDIUM})
        self.assertTrue(weak.missing_modifiers)

    def test_structurally_unrelated_quiver_scores_low(self):
        relevance = ComparableRelevanceAssessor().assess(
            self.item,
            structured_comparable("quiver_1_rare_standard_advanced.txt"),
        )

        self.assertEqual(relevance.band, ComparableRelevanceBand.LOW)
        self.assertLess(relevance.score, Decimal("0.45"))
        self.assertGreaterEqual(len(relevance.missing_modifiers), 5)
        self.assertGreaterEqual(len(relevance.extra_modifiers), 5)

    def test_unrelated_non_quiver_is_not_comparable(self):
        comparable_item = replace(
            self.item,
            item_class="Rings",
            base_type="Ruby Ring",
            item_level=10,
            explicit_modifiers=(),
            modifiers=(),
        )
        comparable = StructuredComparableItem(
            raw_clipboard_text=comparable_item.raw_clipboard_text,
            parsed_item=comparable_item,
            detected_format="ADVANCED",
        )

        relevance = ComparableRelevanceAssessor().assess(self.item, comparable)

        self.assertEqual(relevance.band, ComparableRelevanceBand.INSUFFICIENT_STATE)
        self.assertIsNone(relevance.score)

    def test_price_only_observation_has_no_fabricated_relevance(self):
        result = self.provider.result_from_observation(
            self._observation(Decimal("450"), DIVINE_ASSET_ID),
            self.economy_repo,
            AS_OF,
        )

        self.assertIsNone(result.comparable_item)
        self.assertIsNone(result.comparable_relevance)
        self.assertTrue(any("not structurally verified" in warning for warning in result.warnings))

    def test_gloom_barb_quality_delta_exposes_tier_roll_and_origin_differences(self):
        comparable = structured_comparable("gloom_barb_visceral_quiver_comparable_advanced.txt")

        delta = ComparableQualityDeltaAssessor().assess(self.item, comparable)

        crit_chance = next(item for item in delta.modifier_deltas if item.current_display_name == "of Calamity")
        self.assertEqual(crit_chance.relationship, ModifierQualityRelationship.COMPARABLE_BETTER)
        self.assertEqual(crit_chance.current_tier, "3")
        self.assertEqual(crit_chance.comparable_tier, "1")
        self.assertTrue(any("stronger parsed tier" in reason for reason in crit_chance.reasons))
        crit_multi = next(item for item in delta.modifier_deltas if item.current_display_name == "of Destruction")
        self.assertEqual(crit_multi.relationship, ModifierQualityRelationship.COMPARABLE_BETTER)
        self.assertTrue(crit_multi.origin_difference)
        self.assertEqual(crit_multi.current_origin, "NATURAL")
        self.assertEqual(crit_multi.comparable_origin, "FRACTURED")
        self.assertEqual(crit_multi.current_roll_quality, Decimal("0.7500"))
        self.assertEqual(crit_multi.comparable_roll_quality, Decimal("1.0000"))

    def test_skull_quill_keeps_high_structural_relevance_but_current_better_quality_delta(self):
        skull = structured_comparable("skull_quill_primed_quiver_comparable_advanced.txt")
        relevance = ComparableRelevanceAssessor().assess(self.item, skull)

        delta = ComparableQualityDeltaAssessor().assess(self.item, skull)

        self.assertEqual(relevance.band, ComparableRelevanceBand.HIGH)
        self.assertEqual(len(relevance.matched_modifiers), 1)
        self.assertEqual(len(relevance.differing_modifiers), 5)
        self.assertGreaterEqual(delta.current_better_count, 3)
        self.assertGreaterEqual(delta.comparable_better_count, 1)
        cold = next(item for item in delta.modifier_deltas if item.current_display_name == "Entombing")
        self.assertEqual(cold.comparable_display_name, "Glaciated")
        self.assertEqual(cold.relationship, ModifierQualityRelationship.CURRENT_BETTER)
        self.assertEqual(cold.current_tier, "1")
        self.assertEqual(cold.comparable_tier, "3")
        speed = next(item for item in delta.modifier_deltas if item.current_display_name == "Nimble")
        self.assertEqual(speed.comparable_display_name, "Rapid")
        self.assertEqual(speed.relationship, ModifierQualityRelationship.CURRENT_BETTER)
        crit = next(item for item in delta.modifier_deltas if item.current_display_name == "of Calamity")
        self.assertEqual(crit.relationship, ModifierQualityRelationship.COMPARABLE_BETTER)

    def test_missing_and_extra_modifiers_are_not_ranked_as_tier_quality(self):
        relevance = ComparableRelevanceAssessor().assess(
            self.item,
            structured_comparable("quiver_1_rare_standard_advanced.txt"),
        )
        delta = ComparableQualityDeltaAssessor().assess(
            self.item,
            structured_comparable("quiver_1_rare_standard_advanced.txt"),
        )

        self.assertTrue(relevance.missing_modifiers)
        missing = [item for item in delta.modifier_deltas if item.relationship == ModifierQualityRelationship.MISSING_FROM_COMPARABLE]
        extra = [item for item in delta.modifier_deltas if item.relationship == ModifierQualityRelationship.EXTRA_ON_COMPARABLE]
        self.assertTrue(missing)
        self.assertTrue(extra)
        self.assertTrue(all(item.current_tier is not None and item.comparable_tier is None for item in missing))
        self.assertTrue(all(item.current_tier is None and item.comparable_tier is not None for item in extra))

    def test_price_only_observation_has_no_fabricated_quality_delta(self):
        result = self.provider.result_from_observation(
            self._observation(Decimal("45"), DIVINE_ASSET_ID),
            self.economy_repo,
            AS_OF,
        )

        self.assertIsNone(result.comparable_item)
        self.assertIsNone(result.comparable_quality_delta)

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

    def test_default_policy_does_not_estimate_from_one_listing(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        result = self.provider.result_from_observation(self._observation(Decimal("5"), DIVINE_ASSET_ID), self.economy_repo, AS_OF)
        evidence = evidence_set_from_results(query, self.provider.provider_name, (result,), ValuationEvidencePolicy(minimum_usable_comparables=1))

        valuation = ValuationAggregator().aggregate(evidence)

        self.assertEqual(valuation.readiness, ValuationReadiness.INSUFFICIENT_DATA)
        self.assertIsNone(valuation.estimated_value)
        self.assertEqual(valuation.estimate_type, ValuationEstimateType.NONE)

    def test_single_listing_can_estimate_only_when_policy_explicitly_allows(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        result = self.provider.result_from_observation(self._observation(Decimal("5"), DIVINE_ASSET_ID), self.economy_repo, AS_OF)
        evidence = evidence_set_from_results(query, self.provider.provider_name, (result,), ValuationEvidencePolicy(minimum_usable_comparables=1))

        valuation = ValuationAggregator(ValuationAggregationPolicy(minimum_ready_comparables=1, minimum_partial_comparables=1)).aggregate(evidence)

        self.assertEqual(valuation.readiness, ValuationReadiness.READY)
        self.assertEqual(valuation.estimate_type, ValuationEstimateType.LISTING_DERIVED)
        self.assertEqual(valuation.estimated_value.amount, Decimal("1691.0"))

    def test_decimal_median_odd_and_even(self):
        self.assertEqual(decimal_median((Decimal("1"), Decimal("9"), Decimal("5"))), Decimal("5"))
        self.assertEqual(decimal_median((Decimal("1"), Decimal("9"), Decimal("5"), Decimal("7"))), Decimal("6"))

    def test_decimal_quantile_uses_nearest_lower_index_rule(self):
        values = (Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50"))

        self.assertEqual(decimal_quantile(values, Decimal("0.25")), Decimal("20"))
        self.assertEqual(decimal_quantile(values, Decimal("0.75")), Decimal("40"))
        self.assertEqual(decimal_quantile(values, Decimal("1")), Decimal("50"))

    def test_synthetic_quiver_median_range_and_outlier_policy(self):
        evidence = self._evidence(ComparableStrategy.STRICT, ("4.0", "4.5", "5.0", "5.0", "5.5", "20.0"))

        valuation = ValuationAggregator().aggregate(evidence)

        self.assertEqual(valuation.readiness, ValuationReadiness.READY)
        self.assertEqual(valuation.estimate_type, ValuationEstimateType.LISTING_DERIVED)
        self.assertEqual(valuation.estimated_value.amount, Decimal("1691.00"))
        self.assertLessEqual(valuation.plausible_low.amount, valuation.estimated_value.amount)
        self.assertLessEqual(valuation.estimated_value.amount, valuation.plausible_high.amount)
        self.assertEqual(valuation.excluded_comparables[0].reason, ComparableExclusionReason.OUTLIER_POLICY)
        self.assertTrue(any("excluded by deterministic policy" in warning for warning in valuation.warnings))

    def test_arithmetic_mean_is_not_primary_estimator(self):
        evidence = self._evidence(ComparableStrategy.STRICT, ("4.0", "4.5", "5.0", "5.0", "5.5", "20.0"))

        valuation = ValuationAggregator().aggregate(evidence)

        arithmetic_mean_with_outlier = Decimal("2479.466666666666666666666667")
        self.assertNotEqual(valuation.estimated_value.amount, arithmetic_mean_with_outlier)
        self.assertEqual(valuation.estimated_value.amount, Decimal("1691.00"))

    def test_duplicate_listing_ids_are_not_counted_as_independent_evidence(self):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        results = (
            self.provider.result_from_observation(self._observation(Decimal("5"), DIVINE_ASSET_ID, listing_id="dup"), self.economy_repo, AS_OF),
            self.provider.result_from_observation(self._observation(Decimal("5.5"), DIVINE_ASSET_ID, listing_id="dup"), self.economy_repo, AS_OF),
            self.provider.result_from_observation(self._observation(Decimal("6"), DIVINE_ASSET_ID, listing_id="unique"), self.economy_repo, AS_OF),
        )
        evidence = evidence_set_from_results(query, self.provider.provider_name, results)

        valuation = ValuationAggregator().aggregate(evidence)

        self.assertEqual(valuation.comparable_count, 2)
        self.assertEqual(valuation.excluded_comparables[0].reason, ComparableExclusionReason.DUPLICATE_LISTING)

    def test_strict_precedence_uses_strict_when_sufficient(self):
        strict = self._evidence(ComparableStrategy.STRICT, ("4", "5", "6"), listing_prefix="strict")
        moderate = self._evidence(ComparableStrategy.MODERATE, ("3", "4", "5", "6", "7", "8", "9", "10"), listing_prefix="moderate")

        valuation = ValuationAggregator().aggregate_evidence_sets((strict, moderate))

        self.assertEqual(valuation.strategy, ComparableStrategy.STRICT)
        self.assertEqual(valuation.source_evidence_ids, (strict.evidence_set_id,))
        self.assertEqual(valuation.strategy_composition[0].strategy, ComparableStrategy.STRICT)

    def test_moderate_fallback_is_explicit_when_strict_insufficient(self):
        strict = self._evidence(ComparableStrategy.STRICT, ("5",), listing_prefix="strict")
        moderate = self._evidence(ComparableStrategy.MODERATE, ("4", "5", "6"), listing_prefix="moderate")

        valuation = ValuationAggregator().aggregate_evidence_sets((strict, moderate))

        self.assertEqual(valuation.strategy, ComparableStrategy.OTHER)
        self.assertEqual({entry.strategy for entry in valuation.strategy_composition}, {ComparableStrategy.STRICT, ComparableStrategy.MODERATE})
        self.assertTrue(any("MODERATE comparable evidence used as fallback" in warning for warning in valuation.warnings))

    def test_stale_evidence_warns_and_reduces_confidence(self):
        evidence = self._evidence(ComparableStrategy.STRICT, ("4", "5", "6"))
        stale_results = tuple(replace(result, economy_freshness=FreshnessState.STALE) for result in evidence.results)
        stale_evidence = evidence_set_from_results(evidence.query, self.provider.provider_name, stale_results)

        valuation = ValuationAggregator().aggregate(stale_evidence)

        self.assertTrue(any("stale economy" in warning.lower() for warning in valuation.warnings))
        self.assertTrue(any("Stale economy conversion" in reason for reason in valuation.confidence.reasons))

    def test_liquidity_is_evidence_based_not_sale_velocity(self):
        low = ValuationAggregator().aggregate(self._evidence(ComparableStrategy.STRICT, ("4", "5")))
        high = ValuationAggregator().aggregate(self._evidence(ComparableStrategy.STRICT, ("4", "4.5", "5", "5.5", "6", "6.5", "7", "7.5"), listing_prefix="dense"))

        self.assertEqual(low.liquidity, LiquidityStatus.LOW)
        self.assertEqual(high.liquidity, LiquidityStatus.HIGH)
        self.assertFalse(hasattr(high, "time_to_sale"))

    def test_current_item_aggregation_retains_reproducible_evidence(self):
        evidence = self._evidence(ComparableStrategy.STRICT, ("4", "5", "6"))

        valuation = ValuationAggregator().aggregate(evidence)

        self.assertEqual(valuation.source_evidence_ids, (evidence.evidence_set_id,))
        self.assertEqual(valuation.economy_snapshot_ids, ("economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff",))
        self.assertEqual(valuation.league, LEAGUE)
        self.assertEqual(valuation.estimate_type, ValuationEstimateType.LISTING_DERIVED)
        self.assertFalse(hasattr(valuation, "realized_sale_value"))

    def test_hypothetical_item_aggregation_uses_same_flow(self):
        subject = subject_from_hypothetical_state(self.item, self._first_annulment_state())
        query = build_comparable_query(subject, quiver_6_roles(self.item), ComparableStrategy.STRICT, LEAGUE, AS_OF)
        results = tuple(
            self.provider.result_from_observation(self._observation(Decimal(amount), DIVINE_ASSET_ID, listing_id=f"hyp-{index}"), self.economy_repo, AS_OF)
            for index, amount in enumerate(("4", "5", "6"), start=1)
        )
        evidence = evidence_set_from_results(query, self.provider.provider_name, results)

        valuation = ValuationAggregator().aggregate(evidence)

        self.assertEqual(valuation.readiness, ValuationReadiness.READY)
        self.assertEqual(valuation.estimate_type, ValuationEstimateType.LISTING_DERIVED)
        self.assertFalse(hasattr(valuation, "expected_value"))

    def test_original_item_and_outcome_state_remain_immutable(self):
        item_before = copy.deepcopy(self.item)
        outcome_state = self._first_annulment_state()
        outcome_before = copy.deepcopy(outcome_state)

        subject_from_parsed_item(self.item)
        subject_from_hypothetical_state(self.item, outcome_state)

        self.assertEqual(self.item, item_before)
        self.assertEqual(outcome_state, outcome_before)

    def _evidence(self, strategy: ComparableStrategy, amounts: tuple[str, ...], listing_prefix: str = "listing"):
        query = build_comparable_query(subject_from_parsed_item(self.item), quiver_6_roles(self.item), strategy, LEAGUE, AS_OF)
        results = tuple(
            self.provider.result_from_observation(
                self._observation(Decimal(amount), DIVINE_ASSET_ID, listing_id=f"{listing_prefix}-{index}"),
                self.economy_repo,
                AS_OF,
            )
            for index, amount in enumerate(amounts, start=1)
        )
        return evidence_set_from_results(query, self.provider.provider_name, results)

    def _observation(self, amount: Decimal, currency_asset_id: str, listing_id: str | None = "synthetic-listing"):
        return ManualListingObservation(
            observation_id=f"synthetic-observation-{amount}-{currency_asset_id}-{listing_id or 'manual'}",
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
