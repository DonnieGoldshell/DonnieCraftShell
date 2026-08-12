import copy
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import (
    AffixStateResolver,
    load_affix_capacity_dataset,
)
from packages.shared.donniecraftshell_contracts.craft_action_candidates import (
    CraftActionCostService,
    get_action_candidates,
)
from packages.shared.donniecraftshell_contracts.crafting_actions import (
    CraftActionEngine,
    CraftApplicabilityStatus,
    load_crafting_dataset,
)
from packages.shared.donniecraftshell_contracts.domain import AffixState, AffixType
from packages.shared.donniecraftshell_contracts.economy import (
    EXALTED_ASSET_ID,
    OMEN_OF_CATALYSING_EXALTATION_ASSET_ID,
    OMEN_OF_GREATER_EXALTATION_ASSET_ID,
    FreshnessState,
)
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.poe_show_economy import (
    load_normalized_economy_snapshot,
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


def with_prefix_suffix_counts(item, prefix_count: int, suffix_count: int):
    prefixes = [modifier for modifier in item.explicit_modifiers if modifier.affix_type == AffixType.PREFIX]
    suffixes = [modifier for modifier in item.explicit_modifiers if modifier.affix_type == AffixType.SUFFIX]
    explicit = tuple(prefixes[:prefix_count] + suffixes[:suffix_count])
    return replace(
        item,
        explicit_modifiers=explicit,
        modifiers=item.implicit_modifiers + explicit + item.special_modifiers,
        affix_state=AffixState(
            known_prefixes=tuple(prefixes[:prefix_count]),
            known_suffixes=tuple(suffixes[:suffix_count]),
            observed_prefix_count=prefix_count,
            observed_suffix_count=suffix_count,
        ),
    )


def candidate_by_id(candidates, action_id: str):
    return next(candidate for candidate in candidates if candidate.action.action_id == action_id)


class CraftActionCandidateTests(unittest.TestCase):
    def setUp(self):
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

    def candidates_for(self, item):
        return get_action_candidates(
            item,
            self.affix_resolver.resolve(item),
            self.craft_engine,
            self.repository,
            LEAGUE,
            AS_OF,
        )

    def test_applicable_action_with_complete_price(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)
        exalt = candidate_by_id(self.candidates_for(item), "dc:poe2:craft-action:exalted-orb")

        self.assertEqual(exalt.applicability.status, CraftApplicabilityStatus.APPLICABLE)
        self.assertTrue(exalt.cost_complete)
        self.assertEqual(exalt.material_cost.total.amount, 1)
        self.assertEqual(exalt.material_cost.lines[0].asset_id, EXALTED_ASSET_ID)

    def test_applicable_action_with_missing_material_quote_is_incomplete_not_zero(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        essence = candidate_by_id(self.candidates_for(item), "dc:poe2:craft-action:essence-of-hysteria")

        self.assertEqual(essence.applicability.status, CraftApplicabilityStatus.APPLICABLE)
        self.assertFalse(essence.cost_complete)
        self.assertIsNone(essence.material_cost.total)
        self.assertTrue(any("Missing economy quote" in warning for warning in essence.warnings))

    def test_not_applicable_action_does_not_become_applicable_because_price_exists(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        exalt = candidate_by_id(self.candidates_for(item), "dc:poe2:craft-action:exalted-orb")

        self.assertEqual(exalt.applicability.status, CraftApplicabilityStatus.NOT_APPLICABLE)
        self.assertTrue(exalt.cost_complete)

    def test_unknown_applicability_remains_unknown_even_when_materials_have_prices(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)
        catalysing = candidate_by_id(
            self.candidates_for(item),
            "dc:poe2:craft-action:exalted-orb-with-omen-of-catalysing-exaltation",
        )

        self.assertEqual(catalysing.applicability.status, CraftApplicabilityStatus.UNKNOWN)
        self.assertTrue(catalysing.cost_complete)
        self.assertEqual(catalysing.material_cost.total.amount, Decimal("6.968926"))

    def test_full_quiver_blocks_add_modifier_actions(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        candidates = self.candidates_for(item)

        self.assertEqual(
            candidate_by_id(candidates, "dc:poe2:craft-action:exalted-orb").applicability.status,
            CraftApplicabilityStatus.NOT_APPLICABLE,
        )
        self.assertEqual(
            candidate_by_id(candidates, "dc:poe2:craft-action:exalted-orb-with-omen-of-dextral-exaltation").applicability.status,
            CraftApplicabilityStatus.NOT_APPLICABLE,
        )

    def test_three_two_and_two_three_side_specific_omen_behavior(self):
        three_two = self.candidates_for(with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2))
        two_three = self.candidates_for(with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 2, 3))

        self.assertEqual(
            candidate_by_id(three_two, "dc:poe2:craft-action:exalted-orb-with-omen-of-sinistral-exaltation").applicability.status,
            CraftApplicabilityStatus.NOT_APPLICABLE,
        )
        self.assertEqual(
            candidate_by_id(three_two, "dc:poe2:craft-action:exalted-orb-with-omen-of-dextral-exaltation").applicability.status,
            CraftApplicabilityStatus.APPLICABLE,
        )
        self.assertEqual(
            candidate_by_id(two_three, "dc:poe2:craft-action:exalted-orb-with-omen-of-sinistral-exaltation").applicability.status,
            CraftApplicabilityStatus.APPLICABLE,
        )
        self.assertEqual(
            candidate_by_id(two_three, "dc:poe2:craft-action:exalted-orb-with-omen-of-dextral-exaltation").applicability.status,
            CraftApplicabilityStatus.NOT_APPLICABLE,
        )

    def test_greater_exaltation_with_only_one_open_slot_is_unknown_and_missing_price(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)
        greater = candidate_by_id(
            self.candidates_for(item),
            "dc:poe2:craft-action:exalted-orb-with-omen-of-greater-exaltation",
        )

        self.assertEqual(greater.applicability.status, CraftApplicabilityStatus.UNKNOWN)
        self.assertFalse(greater.cost_complete)
        self.assertIn(OMEN_OF_GREATER_EXALTATION_ASSET_ID, tuple(line.asset_id for line in greater.material_cost.lines))

    def test_annul_side_specific_applicability(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 0, 2)
        candidates = self.candidates_for(item)

        self.assertEqual(
            candidate_by_id(candidates, "dc:poe2:craft-action:orb-of-annulment-with-omen-of-sinistral-annulment").applicability.status,
            CraftApplicabilityStatus.NOT_APPLICABLE,
        )
        self.assertEqual(
            candidate_by_id(candidates, "dc:poe2:craft-action:orb-of-annulment-with-omen-of-dextral-annulment").applicability.status,
            CraftApplicabilityStatus.APPLICABLE,
        )

    def test_mixed_currency_ritual_snapshot_cost_preserves_timestamps_and_least_freshness(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)
        catalysing = candidate_by_id(
            self.candidates_for(item),
            "dc:poe2:craft-action:exalted-orb-with-omen-of-catalysing-exaltation",
        )

        self.assertEqual(catalysing.material_cost.oldest_source_timestamp.isoformat(), "2026-08-11T13:10:57.239546+00:00")
        self.assertEqual(catalysing.material_cost.newest_source_timestamp.isoformat(), "2026-08-11T13:26:14.983071+00:00")
        self.assertEqual(catalysing.cost_freshness, FreshnessState.FRESH)

    def test_explicit_league_scope_for_candidate_costs(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)
        candidates = get_action_candidates(
            item,
            self.affix_resolver.resolve(item),
            self.craft_engine,
            self.repository,
            "Different League",
            AS_OF,
        )

        exalt = candidate_by_id(candidates, "dc:poe2:craft-action:exalted-orb")
        self.assertFalse(exalt.cost_complete)
        self.assertIsNone(exalt.material_cost.total)

    def test_item_remains_immutable_and_no_ranking_is_performed(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)
        before = copy.deepcopy(item)

        candidates = self.candidates_for(item)

        self.assertEqual(item, before)
        self.assertFalse(any(hasattr(candidate, "rank") or hasattr(candidate, "selected") for candidate in candidates))

    def test_cost_service_reuses_existing_cost_math(self):
        service = CraftActionCostService(self.repository)
        action = next(action for action in self.crafting_dataset.actions if action.action_id == "dc:poe2:craft-action:exalted-orb-with-omen-of-catalysing-exaltation")

        cost = service.cost_action(action, LEAGUE, AS_OF)

        self.assertTrue(cost.complete)
        self.assertEqual(cost.total.amount, Decimal("6.968926"))


if __name__ == "__main__":
    unittest.main()
