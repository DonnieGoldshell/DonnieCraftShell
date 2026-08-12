import unittest
from dataclasses import replace
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import (
    AffixStateResolver,
    SlotScope,
    load_affix_capacity_dataset,
)
from packages.shared.donniecraftshell_contracts.domain import AffixState, AffixType, ItemModifier, ModifierOrigin
from packages.shared.donniecraftshell_contracts.game_data_import import (
    RawPoe2DbModifierRecord,
    RawPoe2DbStat,
    canonical_modifier_tier_id,
    load_normalized_dataset,
    normalize_poe2db_snapshot,
    validate_normalized_dataset,
)
from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
from packages.shared.donniecraftshell_contracts.modifier_pool import (
    ModifierPoolCompleteness,
    ModifierPoolResolver,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item


ROOT = Path(__file__).resolve().parents[1]
GAME_DATASET = ROOT / "data" / "normalized" / "poe2db-unknown-version-2026-08-12-task8c-fullx1" / "game_data.json"
RAW_DATASET = ROOT / "data" / "raw" / "poe2db" / "quiver-natural-base-modifiers-2026-08-12" / "raw_modifiers.json"
AFFIX_CAPACITY_DATASET = ROOT / "data" / "normalized" / "crafting" / "affix-capacity-poe2-2026-08-12-research" / "capacity.json"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
DATASET_VERSION = "poe2db-unknown-version-2026-08-12-task8c-fullx1"


PREFIX_FAMILIES = {
    "PhysicalDamage",
    "FireDamage",
    "ColdDamage",
    "LightningDamage",
    "IncreasedAccuracy",
    "ProjectileSpeed",
    "DamageWithWeaponTypeSkill",
}
SUFFIX_FAMILIES = {
    "Dexterity",
    "IncreaseSocketedGemLevel",
    "LifeGainedFromEnemyDeath",
    "ManaGainedFromEnemyDeath",
    "IncreasedAttackSpeed",
    "CriticalStrikeChanceIncrease",
    "CriticalStrikeMultiplier",
    "ChanceToPierce",
    "AdditionalArrows",
}


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


def grouped_modifier(raw_text: str, affix_type: AffixType, family: str) -> ItemModifier:
    return ItemModifier(raw_text=raw_text, affix_type=affix_type, origin=ModifierOrigin.NATURAL, family=family)


def grouped_quiver(item_level: int, prefixes: tuple[str, ...], suffixes: tuple[str, ...]):
    item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
    prefix_mods = tuple(grouped_modifier(f"existing {family}", AffixType.PREFIX, family) for family in prefixes)
    suffix_mods = tuple(grouped_modifier(f"existing {family}", AffixType.SUFFIX, family) for family in suffixes)
    explicit = prefix_mods + suffix_mods
    return replace(
        item,
        item_level=item_level,
        explicit_modifiers=explicit,
        modifiers=item.implicit_modifiers + explicit + item.special_modifiers,
        affix_state=AffixState(
            known_prefixes=prefix_mods,
            known_suffixes=suffix_mods,
            observed_prefix_count=len(prefix_mods),
            observed_suffix_count=len(suffix_mods),
        ),
    )


class ModifierPoolResolverTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_normalized_dataset(GAME_DATASET)
        self.repo = GameDataRepository.from_json_files((GAME_DATASET,))
        self.resolver = ModifierPoolResolver()
        self.affix = AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET))

    def test_normalized_dataset_validation_and_counts(self):
        validate_normalized_dataset(self.dataset)
        self.assertEqual(len(self.dataset.modifier_families), 16)
        self.assertEqual(len(self.dataset.modifier_tiers), 100)
        families = {family.canonical_id: family for family in self.dataset.modifier_families}
        self.assertEqual(sum(1 for family in self.dataset.modifier_families if family.affix_type == AffixType.PREFIX), 7)
        self.assertEqual(sum(1 for family in self.dataset.modifier_families if family.affix_type == AffixType.SUFFIX), 9)
        self.assertEqual(sum(1 for tier in self.dataset.modifier_tiers if families[tier.modifier_family_id].affix_type == AffixType.PREFIX), 56)
        self.assertEqual(sum(1 for tier in self.dataset.modifier_tiers if families[tier.modifier_family_id].affix_type == AffixType.SUFFIX), 44)

    def test_full_raw_dataset_normalization_reproduces_counts(self):
        normalized = normalize_poe2db_snapshot(RAW_DATASET)

        self.assertEqual(normalized.dataset_version, DATASET_VERSION)
        self.assertEqual(len(normalized.modifier_families), len(self.dataset.modifier_families))
        self.assertEqual(len(normalized.modifier_tiers), len(self.dataset.modifier_tiers))

    def test_duplicate_semantic_records_are_detected(self):
        normalized = normalize_poe2db_snapshot(RAW_DATASET)
        duplicate_dataset = replace(
            normalized,
            modifier_tiers=normalized.modifier_tiers + (normalized.modifier_tiers[0],),
        )

        with self.assertRaisesRegex(ValueError, "duplicate modifier tier"):
            validate_normalized_dataset(duplicate_dataset)

    def test_canonical_id_stability(self):
        tier = self.dataset.modifier_tiers[0]
        record = RawPoe2DbModifierRecord(
            source_record_key=tier.source_record_key,
            source_uri=tier.source_locator or "source",
            retrieved_at=tier.provenance[0].retrieved_at,
            display_name=tier.display_name or "",
            family="PhysicalDamage",
            domain="Item",
            generation_type="Prefix",
            required_level=tier.required_item_level,
            tier=tier.tier,
            stats=tuple(RawPoe2DbStat(text=roll.label or "", min=roll.min_value, max=roll.max_value) for roll in tier.roll_ranges),
            spawn_tags={"quiver": 1},
            craft_tags=(),
        )
        self.assertEqual(canonical_modifier_tier_id(record), tier.canonical_id)

    def test_prefix_and_suffix_pool_queries(self):
        item = grouped_quiver(82, prefixes=(), suffixes=())
        affix_state = self.affix.resolve(item)

        prefix = self.resolver.get_legal_candidates(item, affix_state, SlotScope.PREFIX, self.repo, DATASET_VERSION)
        suffix = self.resolver.get_legal_candidates(item, affix_state, SlotScope.SUFFIX, self.repo, DATASET_VERSION)

        self.assertTrue(prefix.candidates)
        self.assertTrue(suffix.candidates)
        self.assertTrue(all(family.affix_type == AffixType.PREFIX for _, family in prefix.candidates))
        self.assertTrue(all(family.affix_type == AffixType.SUFFIX for _, family in suffix.candidates))
        self.assertEqual(prefix.completeness, ModifierPoolCompleteness.COMPLETE)
        self.assertEqual(suffix.completeness, ModifierPoolCompleteness.COMPLETE)

    def test_item_level_filtering_excludes_high_level_tiers(self):
        item = replace(with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 2, 3), item_level=1)
        pool = self.resolver.get_legal_candidates(item, self.affix.resolve(item), SlotScope.PREFIX, self.repo, DATASET_VERSION)

        self.assertTrue(all(tier.required_item_level <= 1 for tier, _ in pool.candidates))
        self.assertTrue(any(excluded.reason == "required item level exceeds item level" for excluded in pool.excluded))

    def test_same_group_conflict_exclusion_and_compatible_groups_retained(self):
        item = grouped_quiver(82, prefixes=("ColdDamage",), suffixes=())
        with_conflict = item

        plain_item = grouped_quiver(82, prefixes=(), suffixes=())
        plain = self.resolver.get_legal_candidates(plain_item, self.affix.resolve(plain_item), SlotScope.PREFIX, self.repo, DATASET_VERSION)
        conflicted = self.resolver.get_legal_candidates(with_conflict, self.affix.resolve(with_conflict), SlotScope.PREFIX, self.repo, DATASET_VERSION)

        self.assertGreater(len(plain.candidates), len(conflicted.candidates))
        self.assertTrue(any(excluded.reason == "same modifier group already present" for excluded in conflicted.excluded))
        self.assertFalse(any(family.modifier_group == "ColdDamage" for _, family in conflicted.candidates))
        self.assertTrue(any(family.modifier_group == "PhysicalDamage" for _, family in conflicted.candidates))

    def test_suffix_same_group_conflict_excludes_attack_speed_ladder(self):
        item = grouped_quiver(82, prefixes=(), suffixes=("IncreasedAttackSpeed",))

        pool = self.resolver.get_legal_candidates(item, self.affix.resolve(item), SlotScope.SUFFIX, self.repo, DATASET_VERSION)

        self.assertFalse(any(family.modifier_group == "IncreasedAttackSpeed" for _, family in pool.candidates))
        self.assertTrue(any(family.modifier_group == "Dexterity" for _, family in pool.candidates))

    def test_unresolved_existing_modifier_warns_about_incomplete_conflict_filtering(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)

        pool = self.resolver.get_legal_candidates(item, self.affix.resolve(item), SlotScope.SUFFIX, self.repo, DATASET_VERSION)

        self.assertTrue(any("lack conflict-group data" in warning for warning in pool.warnings))

    def test_full_side_produces_no_candidates_for_that_side(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)

        pool = self.resolver.get_legal_candidates(item, self.affix.resolve(item), SlotScope.PREFIX, self.repo, DATASET_VERSION)

        self.assertEqual(pool.candidates, ())

    def test_natural_pool_does_not_include_special_origins(self):
        item = grouped_quiver(82, prefixes=(), suffixes=())
        pool = self.resolver.get_legal_candidates(item, self.affix.resolve(item), SlotScope.ANY, self.repo, DATASET_VERSION)

        self.assertTrue(pool.candidates)
        self.assertTrue(all(family.affix_type in {AffixType.PREFIX, AffixType.SUFFIX} for _, family in pool.candidates))

    def test_family_tier_ladders_are_captured(self):
        by_group: dict[str, list[str]] = {}
        families = {family.canonical_id: family for family in self.dataset.modifier_families}
        for tier in self.dataset.modifier_tiers:
            by_group.setdefault(families[tier.modifier_family_id].modifier_group or "", []).append(tier.display_name or "")

        self.assertEqual(set(by_group["ProjectileSpeed"]), {"Darting", "Brisk", "Quick", "Rapid", "Nimble"})
        self.assertIn("of Mastery", by_group["IncreasedAttackSpeed"])
        self.assertEqual(len(by_group["ColdDamage"]), 9)
        self.assertEqual(len(by_group["FireDamage"]), 9)
        self.assertEqual(len(by_group["LightningDamage"]), 9)

    def test_item_level_filtering_at_multiple_levels(self):
        for item_level in (1, 40, 63, 82):
            with self.subTest(item_level=item_level):
                item = grouped_quiver(item_level, prefixes=(), suffixes=())
                pool = self.resolver.get_legal_candidates(item, self.affix.resolve(item), SlotScope.ANY, self.repo, DATASET_VERSION)
                self.assertTrue(all(tier.required_item_level <= item_level for tier, _ in pool.candidates))

    def test_known_fixture_modifiers_are_present_in_natural_pool(self):
        display_names = {tier.display_name for tier in self.dataset.modifier_tiers}

        self.assertTrue(
            {
                "Consistent",
                "Humming",
                "of the Fox",
                "of Victory",
                "of Disaster",
                "Sparking",
                "Impaling",
                "Honed",
                "of Splintering",
            }.issubset(display_names)
        )

    def test_any_scope_excludes_full_side_but_keeps_open_side(self):
        item = grouped_quiver(82, prefixes=("ColdDamage", "ProjectileSpeed", "DamageWithWeaponTypeSkill"), suffixes=("Dexterity", "IncreasedAttackSpeed"))

        pool = self.resolver.get_legal_candidates(item, self.affix.resolve(item), SlotScope.ANY, self.repo, DATASET_VERSION)

        self.assertTrue(pool.candidates)
        self.assertTrue(all(family.affix_type == AffixType.SUFFIX for _, family in pool.candidates))
        self.assertTrue(any(excluded.reason == "affix side is full" for excluded in pool.excluded))

    def test_perfect_exalted_minimum_modifier_level_filter(self):
        item = grouped_quiver(82, prefixes=(), suffixes=())

        ordinary = self.resolver.get_legal_candidates(item, self.affix.resolve(item), SlotScope.PREFIX, self.repo, DATASET_VERSION)
        perfect = self.resolver.get_legal_candidates(
            item,
            self.affix.resolve(item),
            SlotScope.PREFIX,
            self.repo,
            DATASET_VERSION,
            minimum_modifier_level=50,
        )

        self.assertGreater(len(ordinary.candidates), len(perfect.candidates))
        self.assertTrue(all((tier.required_item_level or 0) >= 50 for tier, _ in perfect.candidates))


if __name__ == "__main__":
    unittest.main()
