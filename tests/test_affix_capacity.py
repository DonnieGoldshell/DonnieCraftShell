import copy
import unittest
from dataclasses import replace
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import (
    AffixCapacityDatasetSnapshot,
    AffixStateResolver,
    SlotConsumptionStatus,
    load_affix_capacity_dataset,
)
from packages.shared.donniecraftshell_contracts.crafting_actions import (
    CraftActionEngine,
    CraftApplicabilityStatus,
    load_crafting_dataset,
)
from packages.shared.donniecraftshell_contracts.domain import (
    AffixState,
    AffixType,
    ItemModifier,
    ModifierOrigin,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item


ROOT = Path(__file__).resolve().parents[1]
AFFIX_CAPACITY_DATASET = (
    ROOT
    / "data"
    / "normalized"
    / "crafting"
    / "affix-capacity-poe2-2026-08-12-research"
    / "capacity.json"
)
CRAFTING_DATASET = (
    ROOT
    / "data"
    / "normalized"
    / "crafting"
    / "crafting-actions-poe2-quiver-2026-08-12-research"
    / "actions.json"
)
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"


def parsed_fixture(name: str):
    result = parse_clipboard_item((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert result.item is not None
    return result.item


def action_by_id(dataset, action_id: str):
    return next(action for action in dataset.actions if action.action_id == action_id)


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


class AffixCapacityResolutionTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET)
        self.resolver = AffixStateResolver(self.dataset)

    def test_dataset_version_is_explicitly_selected(self):
        self.assertEqual(self.dataset.dataset_id, "affix-capacity-poe2-2026-08-12-research")
        self.assertGreaterEqual(len(self.dataset.definitions), 4)

    def test_rare_quiver_three_prefix_three_suffix_has_no_open_slots(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")

        resolution = self.resolver.resolve(item)

        self.assertEqual(resolution.observed_prefix_count, 3)
        self.assertEqual(resolution.observed_suffix_count, 3)
        self.assertEqual(resolution.prefix_capacity, 3)
        self.assertEqual(resolution.suffix_capacity, 3)
        self.assertEqual(resolution.open_prefix_count, 0)
        self.assertEqual(resolution.open_suffix_count, 0)

    def test_rare_quiver_three_two_has_one_open_suffix(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)

        resolution = self.resolver.resolve(item)

        self.assertEqual(resolution.open_prefix_count, 0)
        self.assertEqual(resolution.open_suffix_count, 1)

    def test_rare_quiver_two_three_has_one_open_prefix(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 2, 3)

        resolution = self.resolver.resolve(item)

        self.assertEqual(resolution.open_prefix_count, 1)
        self.assertEqual(resolution.open_suffix_count, 0)

    def test_rare_quiver_two_two_has_one_open_prefix_and_suffix(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 2, 2)

        resolution = self.resolver.resolve(item)

        self.assertEqual(resolution.open_prefix_count, 1)
        self.assertEqual(resolution.open_suffix_count, 1)

    def test_unique_capacity_unknown_keeps_open_counts_unknown(self):
        item = parsed_fixture("quiver_8_unique_advanced.txt")

        resolution = self.resolver.resolve(item)

        self.assertIsNone(resolution.prefix_capacity)
        self.assertIsNone(resolution.suffix_capacity)
        self.assertIsNone(resolution.open_prefix_count)
        self.assertIsNone(resolution.open_suffix_count)

    def test_observed_count_exceeding_capacity_warns_and_is_not_clamped(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        extra_prefix = next(modifier for modifier in item.explicit_modifiers if modifier.affix_type == AffixType.PREFIX)
        overfull = replace(item, explicit_modifiers=item.explicit_modifiers + (extra_prefix,))

        resolution = self.resolver.resolve(overfull)

        self.assertEqual(resolution.observed_prefix_count, 4)
        self.assertEqual(resolution.open_prefix_count, -1)
        self.assertIn("Observed prefix count exceeds configured prefix capacity.", resolution.warnings)

    def test_implicit_and_corruption_enhancement_do_not_consume_explicit_slots(self):
        item = parsed_fixture("quiver_7_twice_corrupted_advanced.txt")

        resolution = self.resolver.resolve(item)

        self.assertEqual(len(item.implicit_modifiers), 1)
        self.assertEqual(len(item.special_modifiers), 2)
        self.assertEqual(resolution.observed_prefix_count, 3)
        self.assertEqual(resolution.observed_suffix_count, 3)

    def test_crafted_prefix_consumes_normal_prefix_slot(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        crafted = next(modifier for modifier in item.explicit_modifiers if modifier.origin == ModifierOrigin.CRAFTED)

        resolution = self.resolver.resolve(item)

        self.assertEqual(crafted.affix_type, AffixType.PREFIX)
        self.assertEqual(resolution.observed_prefix_count, 3)
        self.assertEqual(resolution.open_prefix_count, 0)

    def test_desecrated_suffix_consumes_slot_when_source_backed(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        desecrated = next(modifier for modifier in item.explicit_modifiers if modifier.origin == ModifierOrigin.DESECRATED)

        resolution = self.resolver.resolve(item)

        self.assertEqual(desecrated.affix_type, AffixType.SUFFIX)
        self.assertEqual(resolution.observed_suffix_count, 3)
        self.assertEqual(resolution.open_suffix_count, 0)

    def test_fractured_slot_consumption_remains_unknown_without_rule(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        fractured = ItemModifier(
            raw_text="{ Fractured Prefix Modifier }\n+1 test",
            affix_type=AffixType.PREFIX,
            origin=ModifierOrigin.FRACTURED,
        )
        with_fractured = replace(item, explicit_modifiers=item.explicit_modifiers + (fractured,))

        resolution = self.resolver.resolve(with_fractured)

        self.assertTrue(any("FRACTURED" in warning for warning in resolution.warnings))

    def test_parsed_item_remains_immutable_after_resolution(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        before = copy.deepcopy(item)

        self.resolver.resolve(item)

        self.assertEqual(item, before)

    def test_unknown_capacity_dataset_keeps_open_counts_unknown(self):
        empty_dataset = AffixCapacityDatasetSnapshot(
            dataset_id="synthetic-empty-affix-capacity",
            source="synthetic-test",
            retrieved_at=self.dataset.retrieved_at,
            game="Path of Exile 2",
            game_version=None,
            definitions=(),
        )
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")

        resolution = AffixStateResolver(empty_dataset).resolve(item)

        self.assertIsNone(resolution.open_prefix_count)
        self.assertIsNone(resolution.open_suffix_count)
        self.assertTrue(resolution.warnings)


class AffixCapacityCraftActionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.capacity_dataset = load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET)
        self.capacity_resolver = AffixStateResolver(self.capacity_dataset)
        self.crafting_dataset = load_crafting_dataset(CRAFTING_DATASET)
        self.engine = CraftActionEngine(self.crafting_dataset)

    def test_exalted_remains_unknown_without_affix_capacity_resolution(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        exalt = action_by_id(self.crafting_dataset, "dc:poe2:craft-action:exalted-orb")

        result = self.engine.evaluate_action(exalt, item)

        self.assertEqual(result.status, CraftApplicabilityStatus.UNKNOWN)

    def test_full_rare_quiver_prevents_add_modifier_action_with_resolution(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        resolution = self.capacity_resolver.resolve(item)
        exalt = action_by_id(self.crafting_dataset, "dc:poe2:craft-action:exalted-orb")

        result = self.engine.evaluate_action(exalt, item, resolution)

        self.assertEqual(result.status, CraftApplicabilityStatus.NOT_APPLICABLE)
        self.assertIn("no any open affix slots", result.failed_preconditions)

    def test_partial_rare_quiver_allows_exalted_when_any_slot_open(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)
        resolution = self.capacity_resolver.resolve(item)
        exalt = action_by_id(self.crafting_dataset, "dc:poe2:craft-action:exalted-orb")

        result = self.engine.evaluate_action(exalt, item, resolution)

        self.assertEqual(result.status, CraftApplicabilityStatus.APPLICABLE)

    def test_prefix_and_suffix_specific_omen_requirements_use_matching_open_side(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)
        resolution = self.capacity_resolver.resolve(item)
        sinistral = action_by_id(
            self.crafting_dataset,
            "dc:poe2:craft-action:exalted-orb-with-omen-of-sinistral-exaltation",
        )
        dextral = action_by_id(
            self.crafting_dataset,
            "dc:poe2:craft-action:exalted-orb-with-omen-of-dextral-exaltation",
        )

        self.assertEqual(
            self.engine.evaluate_action(sinistral, item, resolution).status,
            CraftApplicabilityStatus.NOT_APPLICABLE,
        )
        self.assertEqual(
            self.engine.evaluate_action(dextral, item, resolution).status,
            CraftApplicabilityStatus.APPLICABLE,
        )


if __name__ == "__main__":
    unittest.main()
