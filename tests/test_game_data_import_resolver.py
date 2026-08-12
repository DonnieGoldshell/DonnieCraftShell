import json
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.domain import (
    AffixType,
    Confidence,
    DataProvenance,
    GameContext,
    ItemModifier,
    RollValue,
    SourceType,
)
from packages.shared.donniecraftshell_contracts.game_data import (
    GameDataSnapshot,
    ModifierApplicability,
    ModifierFamily,
    ModifierTierDefinition,
    ResolutionStatus,
)
from packages.shared.donniecraftshell_contracts.game_data_import import (
    NormalizedGameDataSet,
    canonical_modifier_tier_id,
    load_normalized_dataset,
    load_raw_poe2db_snapshot,
    normalize_poe2db_snapshot,
    validate_normalized_dataset,
    write_normalized_dataset,
)
from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
from packages.shared.donniecraftshell_contracts.modifier_resolver import (
    CanonicalModifierResolver,
    enrich_item,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from tools.quiver_resolution_coverage import collect_coverage


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "poe2db" / "quiver-modifiers-research-2026-08-11" / "raw_modifiers.json"
DATASET_VERSION = "poe2db-unknown-version-2026-08-11-task5c-quiver"
NORMALIZED_PATH = ROOT / "data" / "normalized" / DATASET_VERSION / "game_data.json"
TASK8C_DATASET_VERSION = "poe2db-unknown-version-2026-08-12-task8c-fullx1"
TASK8C_NORMALIZED_PATH = ROOT / "data" / "normalized" / TASK8C_DATASET_VERSION / "game_data.json"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
SOURCE_KEY = "3ac5789a09e2d27363a60b889aa4dedc668f8e920fb1109617905b626ad921db"
PRIORITY_NAMES = {
    "Shocking",
    "Annealed",
    "Frozen",
    "of the Falcon",
    "of Valour",
    "of Infusion",
    "Glaciated",
    "Polished",
    "Rapid",
    "of the Archer",
    "of Mastery",
    "of the Panther",
    "Entombing",
    "Nimble",
    "Lacerating",
    "of Destruction",
    "of Calamity",
}


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def parsed_mastery():
    parsed = parse_clipboard_item(fixture("quiver_2_rare_trade_note_advanced.txt")).item
    assert parsed is not None
    modifier = next(item for item in parsed.modifiers if item.display_name == "of Mastery")
    return parsed, modifier


def repository() -> GameDataRepository:
    return GameDataRepository.from_json_files((NORMALIZED_PATH,))


class GameDataImportTests(unittest.TestCase):
    def test_raw_snapshot_contains_priority_source_backed_records(self):
        snapshot, records = load_raw_poe2db_snapshot(RAW_PATH)

        self.assertEqual(snapshot.source, "poe2db")
        self.assertEqual(len(records), 17)
        self.assertEqual({record.display_name for record in records}, PRIORITY_NAMES)

    def test_raw_snapshot_preserves_mastery_source_locator(self):
        _, records = load_raw_poe2db_snapshot(RAW_PATH)
        mastery = next(record for record in records if record.display_name == "of Mastery")

        self.assertEqual(mastery.source_record_key, SOURCE_KEY)
        self.assertEqual(mastery.stats[0].min, Decimal("11"))
        self.assertEqual(mastery.stats[0].max, Decimal("13"))

    def test_normalization_preserves_source_key_separate_from_canonical_id(self):
        dataset = normalize_poe2db_snapshot(RAW_PATH)
        tier = next(item for item in dataset.modifier_tiers if item.display_name == "of Mastery")

        self.assertTrue(tier.canonical_id.startswith("dc:poe2:modifier-tier:"))
        self.assertNotEqual(tier.canonical_id, tier.display_name)
        self.assertNotEqual(tier.canonical_id, tier.source_record_key)
        self.assertEqual(tier.source_record_key, SOURCE_KEY)

    def test_normalization_counts_and_version(self):
        dataset = normalize_poe2db_snapshot(RAW_PATH)

        self.assertEqual(dataset.dataset_version, DATASET_VERSION)
        self.assertEqual(len(dataset.modifier_families), 12)
        self.assertEqual(len(dataset.modifier_tiers), 17)

    def test_canonical_ids_are_deterministic_and_order_independent(self):
        _, records = load_raw_poe2db_snapshot(RAW_PATH)
        original = {record.display_name: canonical_modifier_tier_id(record) for record in records}
        reordered = {record.display_name: canonical_modifier_tier_id(record) for record in reversed(records)}

        self.assertEqual(original, reordered)

    def test_normalized_dataset_round_trips_and_validates(self):
        dataset = normalize_poe2db_snapshot(RAW_PATH)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "game_data.json"
            write_normalized_dataset(dataset, path)
            loaded = load_normalized_dataset(path)

        self.assertEqual(loaded.dataset_version, dataset.dataset_version)
        self.assertEqual(
            loaded.modifier_tiers[0].provenance[0].confidence.reasons,
            ("Community source; licensing/source stability needs review.",),
        )

    def test_repository_requires_explicit_dataset_version(self):
        repo = repository()

        self.assertEqual(repo.get_dataset(DATASET_VERSION).dataset_version, DATASET_VERSION)
        with self.assertRaises(KeyError):
            repo.get_dataset("latest")

    def test_duplicate_semantic_raw_records_fail_normalization(self):
        raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
        raw["records"].append(raw["records"][0])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.json"
            path.write_text(json.dumps(raw), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate modifier tier"):
                normalize_poe2db_snapshot(path)

    def test_validation_rejects_duplicate_canonical_ids(self):
        dataset = load_normalized_dataset(NORMALIZED_PATH)
        invalid = replace(dataset, modifier_tiers=(dataset.modifier_tiers[0], dataset.modifier_tiers[0]))

        with self.assertRaisesRegex(ValueError, "duplicate modifier tier"):
            validate_normalized_dataset(invalid)

    def test_validation_rejects_missing_snapshot_identity_and_dataset_version(self):
        dataset = load_normalized_dataset(NORMALIZED_PATH)
        bad_snapshot = replace(dataset.snapshot, snapshot_id="")

        with self.assertRaisesRegex(ValueError, "snapshot identity"):
            validate_normalized_dataset(replace(dataset, snapshot=bad_snapshot))
        with self.assertRaisesRegex(ValueError, "dataset_version"):
            validate_normalized_dataset(replace(dataset, dataset_version=""))

    def test_validation_rejects_invalid_tier_and_roll_range(self):
        dataset = load_normalized_dataset(NORMALIZED_PATH)
        bad_tier = replace(dataset.modifier_tiers[0], tier="two")
        bad_range = replace(
            dataset.modifier_tiers[0],
            roll_ranges=(RollValue(label="attack speed +%", min_value=Decimal("13"), max_value=Decimal("11")),),
        )

        with self.assertRaisesRegex(ValueError, "tier must be numeric"):
            validate_normalized_dataset(replace(dataset, modifier_tiers=(bad_tier,)))
        with self.assertRaisesRegex(ValueError, "min cannot exceed max"):
            validate_normalized_dataset(replace(dataset, modifier_tiers=(bad_range,)))

    def test_validation_rejects_missing_provenance_and_bad_required_level(self):
        dataset = load_normalized_dataset(NORMALIZED_PATH)
        bad_family = replace(dataset.modifier_families[0], provenance=())
        families = (bad_family, *dataset.modifier_families[1:])

        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_normalized_dataset(replace(dataset, modifier_families=families))
        with self.assertRaisesRegex(ValueError, "required_item_level cannot be negative"):
            replace(dataset.modifier_tiers[0], required_item_level=-1)

    def test_invalid_generation_type_fails_normalization(self):
        snapshot, records = load_raw_poe2db_snapshot(RAW_PATH)
        raw = {
            "snapshot": {
                "snapshot_id": snapshot.snapshot_id,
                "source": snapshot.source,
                "retrieved_at": snapshot.retrieved_at.isoformat(),
                "verification_status": "NEEDS_VERIFICATION",
            },
            "records": [
                {
                    "source_uri": records[0].source_uri,
                    "retrieved_at": records[0].retrieved_at.isoformat(),
                    "display_name": records[0].display_name,
                    "family": records[0].family,
                    "generation_type": "UnknownFutureType",
                    "stats": [{"text": "attack speed +%", "min": "11", "max": "13"}],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.json"
            path.write_text(json.dumps(raw), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "invalid affix/generation type"):
                normalize_poe2db_snapshot(path)


class ModifierResolverTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_normalized_dataset(NORMALIZED_PATH)
        self.repo = repository()
        self.resolver = CanonicalModifierResolver(self.repo, self.dataset.dataset_version)
        self.parsed_item, self.modifier = parsed_mastery()

    def test_each_source_backed_modifier_resolves_when_present_in_fixtures(self):
        seen: set[str] = set()
        for path in FIXTURE_DIR.glob("*_advanced.txt"):
            parsed = parse_clipboard_item(path.read_text(encoding="utf-8")).item
            assert parsed is not None
            for modifier in parsed.modifiers:
                if modifier.display_name not in PRIORITY_NAMES:
                    continue
                resolution = self.resolver.resolve_modifier(parsed, modifier)
                self.assertEqual(resolution.status, ResolutionStatus.RESOLVED, modifier.display_name)
                selected = next(
                    tier for tier in self.dataset.modifier_tiers if tier.canonical_id == resolution.selected_canonical_modifier_id
                )
                self.assertEqual(selected.display_name, modifier.display_name)
                self.assertEqual(selected.tier, modifier.tier)
                seen.add(modifier.display_name)

        self.assertTrue(PRIORITY_NAMES - {"of the Panther"} <= seen)

    def test_of_mastery_resolves_with_structured_evidence(self):
        resolution = self.resolver.resolve_modifier(self.parsed_item, self.modifier)
        selected = next(tier for tier in self.dataset.modifier_tiers if tier.display_name == "of Mastery")

        self.assertEqual(resolution.status, ResolutionStatus.RESOLVED)
        self.assertEqual(resolution.selected_canonical_modifier_id, selected.canonical_id)
        self.assertIn("displayed range matched", resolution.match_reasons)

    def test_tag_order_does_not_affect_resolution(self):
        modifier = replace(self.modifier, tags=("Speed", "Attack"))

        resolution = self.resolver.resolve_modifier(self.parsed_item, modifier)

        self.assertEqual(resolution.status, ResolutionStatus.RESOLVED)

    def test_wrong_tier_does_not_resolve(self):
        modifier = replace(self.modifier, tier="7")

        resolution = self.resolver.resolve_modifier(self.parsed_item, modifier)

        self.assertEqual(resolution.status, ResolutionStatus.UNRESOLVED)
        self.assertIsNone(resolution.selected_canonical_modifier_id)

    def test_wrong_range_does_not_resolve(self):
        modifier = replace(
            self.modifier,
            allowed_range=(RollValue(label="attack speed +%", min_value=Decimal("99"), max_value=Decimal("200")),),
        )

        resolution = self.resolver.resolve_modifier(self.parsed_item, modifier)

        self.assertEqual(resolution.status, ResolutionStatus.UNRESOLVED)
        self.assertIsNone(resolution.selected_canonical_modifier_id)
        self.assertIn("displayed range conflicts", resolution.warnings[0])

    def test_similar_family_records_disambiguate_by_tier_and_range(self):
        parsed = parse_clipboard_item(fixture("quiver_2_rare_trade_note_advanced.txt")).item
        assert parsed is not None
        glaciated = next(modifier for modifier in parsed.modifiers if modifier.display_name == "Glaciated")

        resolution = self.resolver.resolve_modifier(parsed, glaciated)
        selected = next(
            tier for tier in self.dataset.modifier_tiers if tier.canonical_id == resolution.selected_canonical_modifier_id
        )

        self.assertEqual(resolution.status, ResolutionStatus.RESOLVED)
        self.assertEqual(selected.display_name, "Glaciated")
        self.assertEqual(selected.tier, "3")

    def test_unknown_modifier_is_unresolved_not_exception(self):
        modifier = ItemModifier(
            raw_text="{ Suffix Modifier \"of Unknown\" (Tier: 1) }\n+999 to Mystery",
            affix_type=AffixType.SUFFIX,
            display_name="of Unknown",
            tier="1",
        )

        resolution = self.resolver.resolve_modifier(self.parsed_item, modifier)

        self.assertEqual(resolution.status, ResolutionStatus.UNRESOLVED)
        self.assertIsNone(resolution.selected_canonical_modifier_id)

    def test_modifier_without_structured_identity_is_unresolved_without_broad_search(self):
        modifier = ItemModifier(
            raw_text="Blind Targets when you Poison them - Unscalable Value",
            normalized_text="Blind Targets when you Poison them - Unscalable Value",
        )

        resolution = self.resolver.resolve_modifier(self.parsed_item, modifier)

        self.assertEqual(resolution.status, ResolutionStatus.UNRESOLVED)
        self.assertIn("Insufficient structured modifier identity", resolution.warnings[0])

    def test_ambiguous_candidates_do_not_select_winner(self):
        repo = GameDataRepository({"synthetic-v1": synthetic_ambiguous_dataset()})
        resolver = CanonicalModifierResolver(repo, "synthetic-v1")

        resolution = resolver.resolve_modifier(self.parsed_item, self.modifier)

        self.assertEqual(resolution.status, ResolutionStatus.AMBIGUOUS)
        self.assertIsNone(resolution.selected_canonical_modifier_id)
        self.assertEqual(len(resolution.candidates), 2)

    def test_enrichment_preserves_parsed_item_and_tolerates_partial_resolution(self):
        before = repr(self.parsed_item)

        enrichment = enrich_item(self.parsed_item, self.repo, self.dataset.dataset_version)

        self.assertEqual(repr(self.parsed_item), before)
        self.assertIs(enrichment.parsed_item, self.parsed_item)
        statuses = [resolution.status for resolution in enrichment.modifier_resolutions]
        self.assertIn(ResolutionStatus.RESOLVED, statuses)
        self.assertIn(ResolutionStatus.UNRESOLVED, statuses)

    def test_quiver_6_has_partial_resolution_coverage_with_current_dataset(self):
        parsed_item = parse_clipboard_item(fixture("quiver_6_crafted_desecrated_advanced.txt")).item
        assert parsed_item is not None

        enrichment = enrich_item(parsed_item, self.repo, self.dataset.dataset_version)
        resolved = [
            resolution
            for resolution in enrichment.modifier_resolutions
            if resolution.status == ResolutionStatus.RESOLVED
        ]

        self.assertEqual(len(resolved), 6)
        self.assertEqual(len(enrichment.modifier_resolutions), len(parsed_item.modifiers))

    def test_rare_fixture_coverage_is_measured_honestly(self):
        rows = collect_coverage(FIXTURE_DIR, NORMALIZED_PATH, DATASET_VERSION)
        by_fixture = {row.fixture: row for row in rows}

        self.assertEqual(by_fixture["quiver_1_rare_standard_advanced.txt"].explicit_resolved, 6)
        self.assertEqual(by_fixture["quiver_5_rare_corrupted_advanced.txt"].explicit_resolved, 1)
        self.assertEqual(by_fixture["quiver_6_crafted_desecrated_advanced.txt"].explicit_resolved, 6)
        self.assertIn("Consistent", by_fixture["quiver_5_rare_corrupted_advanced.txt"].unresolved_modifiers)


class Task8CModifierResolverTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_normalized_dataset(TASK8C_NORMALIZED_PATH)
        self.repo = GameDataRepository.from_json_files((TASK8C_NORMALIZED_PATH,))
        self.resolver = CanonicalModifierResolver(self.repo, self.dataset.dataset_version)

    def test_task8c_dataset_counts(self):
        families = {family.canonical_id: family for family in self.dataset.modifier_families}

        self.assertEqual(self.dataset.dataset_version, TASK8C_DATASET_VERSION)
        self.assertEqual(len(self.dataset.modifier_families), 16)
        self.assertEqual(len(self.dataset.modifier_tiers), 100)
        self.assertEqual(sum(1 for family in self.dataset.modifier_families if family.affix_type == AffixType.PREFIX), 7)
        self.assertEqual(sum(1 for family in self.dataset.modifier_families if family.affix_type == AffixType.SUFFIX), 9)
        self.assertEqual(sum(1 for tier in self.dataset.modifier_tiers if families[tier.modifier_family_id].affix_type == AffixType.PREFIX), 56)
        self.assertEqual(sum(1 for tier in self.dataset.modifier_tiers if families[tier.modifier_family_id].affix_type == AffixType.SUFFIX), 44)

    def test_fixed_value_display_can_match_fixed_canonical_range(self):
        parsed = parse_clipboard_item(fixture("quiver_5_rare_corrupted_advanced.txt")).item
        assert parsed is not None
        humming = next(modifier for modifier in parsed.explicit_modifiers if modifier.display_name == "Humming")

        resolution = self.resolver.resolve_modifier(parsed, humming)

        self.assertEqual(resolution.status, ResolutionStatus.RESOLVED)
        self.assertTrue(any("fixed-value canonical ranges" in reason for reason in resolution.match_reasons))

    def test_task8c_rare_explicit_fixture_coverage_is_complete_for_natural_pool(self):
        rows = collect_coverage(FIXTURE_DIR, TASK8C_NORMALIZED_PATH, TASK8C_DATASET_VERSION)
        by_fixture = {row.fixture: row for row in rows}

        for fixture_name in (
            "quiver_1_rare_standard_advanced.txt",
            "quiver_2_rare_trade_note_advanced.txt",
            "quiver_5_rare_corrupted_advanced.txt",
            "quiver_6_crafted_desecrated_advanced.txt",
            "quiver_7_twice_corrupted_advanced.txt",
        ):
            with self.subTest(fixture=fixture_name):
                self.assertEqual(by_fixture[fixture_name].explicit_coverage_percent, 100.0)

    def test_task8c_keeps_special_modifiers_outside_natural_pool(self):
        rows = collect_coverage(FIXTURE_DIR, TASK8C_NORMALIZED_PATH, TASK8C_DATASET_VERSION)
        by_fixture = {row.fixture: row for row in rows}

        self.assertIn("25(20-30)% increased Critical Hit Chance for Attacks", by_fixture["quiver_7_twice_corrupted_advanced.txt"].unresolved_modifiers)
        self.assertIn("+23(20-25) to maximum Mana", by_fixture["quiver_7_twice_corrupted_advanced.txt"].unresolved_modifiers)


def synthetic_ambiguous_dataset() -> NormalizedGameDataSet:
    provenance = (
        DataProvenance(
            source_id="synthetic-test",
            source_type=SourceType.INTERNAL,
            source_uri="internal:test",
            confidence=Confidence(Decimal("1")),
        ),
    )
    snapshot = GameDataSnapshot(
        snapshot_id="synthetic-ambiguous",
        source="synthetic-test",
        game_context=GameContext(game="Path of Exile 2"),
    )
    family = ModifierFamily(
        canonical_id="dc:test:modifier-family:increased-attack-speed",
        normalized_stat_template="attack speed +%",
        affix_type=AffixType.SUFFIX,
        tags=("Attack", "Speed"),
        modifier_group="SyntheticIncreasedAttackSpeed",
        provenance=provenance,
    )
    tiers = (
        ModifierTierDefinition(
            canonical_id="dc:test:modifier-tier:mastery-a",
            modifier_family_id=family.canonical_id,
            tier="2",
            display_name="of Mastery",
            roll_ranges=(RollValue(label="attack speed +%", min_value=Decimal("11"), max_value=Decimal("13")),),
            provenance=provenance,
            dataset_version="synthetic-v1",
        ),
        ModifierTierDefinition(
            canonical_id="dc:test:modifier-tier:mastery-b",
            modifier_family_id=family.canonical_id,
            tier="2",
            display_name="of Mastery",
            roll_ranges=(RollValue(label="attack speed +%", min_value=Decimal("11"), max_value=Decimal("13")),),
            provenance=provenance,
            dataset_version="synthetic-v1",
        ),
    )
    applicability = tuple(
        ModifierApplicability(
            modifier_id=tier.canonical_id,
            item_class="Quivers",
            tags_or_conditions=("synthetic:test-only",),
            provenance=provenance,
        )
        for tier in tiers
    )
    dataset = NormalizedGameDataSet(
        snapshot=snapshot,
        dataset_version="synthetic-v1",
        modifier_families=(family,),
        modifier_tiers=tiers,
        modifier_applicability=applicability,
    )
    validate_normalized_dataset(dataset)
    return dataset


if __name__ == "__main__":
    unittest.main()
