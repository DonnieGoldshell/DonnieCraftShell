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


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "poe2db" / "quiver-modifiers-research-2026-08-11" / "raw_modifiers.json"
NORMALIZED_PATH = (
    ROOT
    / "data"
    / "normalized"
    / "poe2db-unknown-version-2026-08-11-research-fix"
    / "game_data.json"
)
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
SOURCE_KEY = "3ac5789a09e2d27363a60b889aa4dedc668f8e920fb1109617905b626ad921db"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def mastery_modifier() -> tuple:
    parsed = parse_clipboard_item(fixture("quiver_2_rare_trade_note_advanced.txt")).item
    assert parsed is not None
    modifier = next(item for item in parsed.modifiers if item.display_name == "of Mastery")
    return parsed, modifier


def repository() -> GameDataRepository:
    return GameDataRepository.from_json_files((NORMALIZED_PATH,))


class GameDataImportTests(unittest.TestCase):
    def test_raw_snapshot_parses_source_backed_mastery_record(self):
        snapshot, records = load_raw_poe2db_snapshot(RAW_PATH)

        self.assertEqual(snapshot.source, "poe2db")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].display_name, "of Mastery")
        self.assertEqual(records[0].source_record_key, SOURCE_KEY)
        self.assertEqual(records[0].stats[0].min, Decimal("11"))
        self.assertEqual(records[0].stats[0].max, Decimal("13"))

    def test_normalization_preserves_source_key_separate_from_canonical_id(self):
        dataset = normalize_poe2db_snapshot(RAW_PATH)
        tier = dataset.modifier_tiers[0]

        self.assertTrue(tier.canonical_id.startswith("dc:poe2:modifier-tier:"))
        self.assertNotEqual(tier.canonical_id, tier.display_name)
        self.assertNotEqual(tier.canonical_id, tier.source_record_key)
        self.assertEqual(tier.source_record_key, SOURCE_KEY)

    def test_canonical_ids_are_deterministic(self):
        _, records = load_raw_poe2db_snapshot(RAW_PATH)

        self.assertEqual(
            canonical_modifier_tier_id(records[0]),
            canonical_modifier_tier_id(records[0]),
        )
        self.assertEqual(
            normalize_poe2db_snapshot(RAW_PATH).modifier_tiers[0].canonical_id,
            normalize_poe2db_snapshot(RAW_PATH).modifier_tiers[0].canonical_id,
        )

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
        dataset = load_normalized_dataset(NORMALIZED_PATH)
        repo = repository()

        self.assertIs(repo.get_dataset(dataset.dataset_version), repo.get_dataset(dataset.dataset_version))
        with self.assertRaises(KeyError):
            repo.get_dataset("latest")

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

        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_normalized_dataset(replace(dataset, modifier_families=(bad_family,)))
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
                    "display_name": "of Mastery",
                    "family": "IncreasedAttackSpeed",
                    "generation_type": "UnknownFutureType",
                    "stats": [{"text": "attack speed +%", "min": "11", "max": "13"}],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.json"
            path.write_text(__import__("json").dumps(raw), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "invalid affix/generation type"):
                normalize_poe2db_snapshot(path)


class ModifierResolverTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_normalized_dataset(NORMALIZED_PATH)
        self.repo = repository()
        self.resolver = CanonicalModifierResolver(self.repo, self.dataset.dataset_version)
        self.parsed_item, self.modifier = mastery_modifier()

    def test_of_mastery_resolves_with_structured_evidence(self):
        resolution = self.resolver.resolve_modifier(self.parsed_item, self.modifier)

        self.assertEqual(resolution.status, ResolutionStatus.RESOLVED)
        self.assertEqual(resolution.selected_canonical_modifier_id, self.dataset.modifier_tiers[0].canonical_id)
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

    def test_quiver_6_has_honest_zero_resolution_coverage_with_current_dataset(self):
        parsed_item = parse_clipboard_item(fixture("quiver_6_crafted_desecrated_advanced.txt")).item
        assert parsed_item is not None

        enrichment = enrich_item(parsed_item, self.repo, self.dataset.dataset_version)

        resolved = [
            resolution
            for resolution in enrichment.modifier_resolutions
            if resolution.status == ResolutionStatus.RESOLVED
        ]
        self.assertEqual(len(resolved), 0)
        self.assertEqual(len(enrichment.modifier_resolutions), len(parsed_item.modifiers))


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
