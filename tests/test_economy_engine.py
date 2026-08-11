import json
import tempfile
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.economy import (
    DIVINE_ASSET_ID,
    ESSENCE_OF_ENHANCEMENT_ASSET_ID,
    EXALTED_ASSET_ID,
    OMEN_OF_CATALYSING_EXALTATION_ASSET_ID,
    OMEN_OF_PUTREFACTION_ASSET_ID,
    PERFECT_EXALTED_ASSET_ID,
    PERFECT_ESSENCE_OF_BATTLE_ASSET_ID,
    EconomyCategory,
    FreshnessState,
    classify_freshness,
    convert_native_to_exalted,
)
from packages.shared.donniecraftshell_contracts.economy_assets import asset_id_for_poe_show
from packages.shared.donniecraftshell_contracts.economy_costs import (
    CraftMaterialRequirement,
    calculate_craft_material_cost,
)
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.poe_show_economy import (
    load_normalized_economy_snapshot,
    load_raw_poe_show_currency_snapshot,
    load_raw_poe_show_economy_snapshot,
    normalize_poe_show_economy_snapshot,
    normalize_poe_show_currency_snapshot,
    write_normalized_economy_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
RAW_FIXTURE = ROOT / "data" / "raw" / "economy" / "poe-show-poe2-currency-runes-of-aldur-2026-08-11.json"
RITUAL_RAW_FIXTURE = ROOT / "data" / "raw" / "economy" / "poe-show-poe2-ritual-runes-of-aldur-2026-08-11.json"
ESSENCE_RAW_FIXTURE = ROOT / "data" / "raw" / "economy" / "poe-show-poe2-essences-runes-of-aldur-2026-08-11.json"
NORMALIZED_FIXTURE = (
    ROOT
    / "data"
    / "normalized"
    / "economy"
    / "economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff"
    / "economy_snapshot.json"
)
RITUAL_NORMALIZED_FIXTURE = (
    ROOT
    / "data"
    / "normalized"
    / "economy"
    / "economy-snapshot-019ff11a-0000-7000-8000-000000000001"
    / "economy_snapshot.json"
)
ESSENCE_NORMALIZED_FIXTURE = (
    ROOT
    / "data"
    / "normalized"
    / "economy"
    / "economy-snapshot-019ff11a-0000-7000-8000-000000000002"
    / "economy_snapshot.json"
)
AS_OF = datetime(2026, 8, 11, 13, 30, tzinfo=timezone.utc)
LEAGUE = "Runes of Aldur"


class EconomyEngineTests(unittest.TestCase):
    def test_raw_poe_show_fixture_parses_decimal_values(self):
        raw = load_raw_poe_show_currency_snapshot(RAW_FIXTURE)
        divine = next(line for line in raw["response"]["lines"] if line["id"] == "divine")

        self.assertEqual(raw["league"], LEAGUE)
        self.assertIsInstance(raw["response"]["core"]["rates"]["exalted"], Decimal)
        self.assertEqual(divine["primaryValue"], Decimal("1"))

    def test_core_primary_is_divine_and_cross_rate_direction_is_explicit(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)
        rate = snapshot.exchange_rates[0]

        self.assertEqual(rate.base_asset_id, DIVINE_ASSET_ID)
        self.assertEqual(rate.quote_asset_id, EXALTED_ASSET_ID)
        self.assertEqual(rate.rate, Decimal("338.2"))

    def test_exalted_identity_is_one_normalized_unit(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)
        quote = _quote(snapshot, EXALTED_ASSET_ID)

        self.assertEqual(quote.normalized_value.amount, Decimal("1"))

    def test_divine_to_exalted_conversion(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)
        quote = _quote(snapshot, DIVINE_ASSET_ID)

        self.assertEqual(quote.normalized_value.amount, Decimal("338.2"))

    def test_perfect_exalted_conversion_uses_multiplication_not_reverse_rate(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)
        quote = _quote(snapshot, PERFECT_EXALTED_ASSET_ID)

        self.assertEqual(quote.source_native_value, Decimal("2.63"))
        self.assertEqual(quote.normalized_value.amount, Decimal("889.466"))
        self.assertNotEqual(quote.normalized_value.amount, Decimal("2.63") / Decimal("338.2"))

    def test_decimal_only_conversion_rejects_binary_float(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)

        with self.assertRaises(TypeError):
            convert_native_to_exalted(2.63, snapshot.exchange_rates[0])  # type: ignore[arg-type]

    def test_asset_mapping_keeps_provider_ids_separate_from_internal_ids(self):
        self.assertEqual(asset_id_for_poe_show("divine"), DIVINE_ASSET_ID)
        self.assertNotEqual("divine", DIVINE_ASSET_ID)

    def test_unknown_source_asset_is_skipped_with_warning(self):
        raw = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))
        raw["response"]["lines"].append(
            {
                "id": "unknown-future-currency",
                "primaryValue": 1,
                "volumePrimaryValue": 1,
            }
        )

        snapshot = _normalize_temp_raw(raw)

        self.assertIn("Unmapped poe.show asset skipped: unknown-future-currency", snapshot.warnings)

    def test_missing_exalted_rate_fails_without_fabricating_price(self):
        raw = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))
        del raw["response"]["core"]["rates"]["exalted"]

        with self.assertRaisesRegex(ValueError, "missing Exalted cross-rate"):
            _normalize_temp_raw(raw)

    def test_negative_or_zero_rates_and_prices_are_invalid(self):
        raw_rate = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))
        raw_rate["response"]["core"]["rates"]["exalted"] = 0
        with self.assertRaisesRegex(ValueError, "must be positive"):
            _normalize_temp_raw(raw_rate)

        raw_price = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))
        raw_price["response"]["lines"][0]["primaryValue"] = 0
        with self.assertRaisesRegex(ValueError, "source price must be positive"):
            _normalize_temp_raw(raw_price)

    def test_snapshot_id_is_uuid7_and_league_required(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)
        parsed_uuid = uuid.UUID(snapshot.snapshot_id.removeprefix("economy-snapshot-"))

        self.assertEqual(parsed_uuid.version, 7)

        raw = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))
        raw["league"] = ""
        with self.assertRaisesRegex(ValueError, "requires league"):
            _normalize_temp_raw(raw)

    def test_freshness_classification_uses_controlled_time(self):
        retrieved_at = datetime(2026, 8, 11, 10, tzinfo=timezone.utc)

        self.assertEqual(classify_freshness(retrieved_at, retrieved_at + timedelta(hours=2)), FreshnessState.FRESH)
        self.assertEqual(classify_freshness(retrieved_at, retrieved_at + timedelta(hours=3)), FreshnessState.AGING)
        self.assertEqual(classify_freshness(retrieved_at, retrieved_at + timedelta(hours=7)), FreshnessState.STALE)
        self.assertEqual(classify_freshness(None, retrieved_at), FreshnessState.UNAVAILABLE)

    def test_stale_quote_is_retained_as_stale(self):
        snapshot = normalize_poe_show_currency_snapshot(
            RAW_FIXTURE,
            datetime(2026, 8, 11, 21, 0, tzinfo=timezone.utc),
        )
        quote = _quote(snapshot, DIVINE_ASSET_ID)

        self.assertEqual(snapshot.freshness, FreshnessState.STALE)
        self.assertEqual(quote.freshness, FreshnessState.STALE)
        self.assertEqual(quote.normalized_value.amount, Decimal("338.2"))

    def test_repository_current_quote_and_as_of_behavior(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)
        repo = EconomyRepository((snapshot,))

        quote = repo.get_current_quote(LEAGUE, DIVINE_ASSET_ID, AS_OF)
        before_snapshot = repo.get_current_quote(
            LEAGUE,
            DIVINE_ASSET_ID,
            datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        )

        self.assertIsNotNone(quote)
        self.assertEqual(quote.normalized_value.amount, Decimal("338.2"))
        self.assertIsNone(before_snapshot)

    def test_repository_exchange_rate_and_failure_states(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)
        repo = EconomyRepository((snapshot,))

        rate = repo.get_exchange_rate(LEAGUE, DIVINE_ASSET_ID, EXALTED_ASSET_ID, AS_OF)

        self.assertEqual(rate.rate, Decimal("338.2"))
        self.assertIsNone(repo.get_current_quote(LEAGUE, "dc:poe2:economy-asset:currency:missing", AS_OF))
        self.assertTrue(repo.provider_snapshot_unavailable("ggg-cxapi", LEAGUE))

    def test_provenance_retained(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)
        quote = _quote(snapshot, DIVINE_ASSET_ID)

        self.assertEqual(snapshot.provenance[0].source_id, "poe.show")
        self.assertEqual(quote.provenance[0].league, LEAGUE)

    def test_fixture_normalization_reproducibility(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)
        loaded = load_normalized_economy_snapshot(NORMALIZED_FIXTURE)

        self.assertEqual(snapshot.snapshot_id, loaded.snapshot_id)
        self.assertEqual(_quote(snapshot, PERFECT_EXALTED_ASSET_ID).normalized_value.amount, _quote(loaded, PERFECT_EXALTED_ASSET_ID).normalized_value.amount)

    def test_write_and_load_normalized_snapshot_round_trip(self):
        snapshot = normalize_poe_show_currency_snapshot(RAW_FIXTURE, AS_OF)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "economy_snapshot.json"
            write_normalized_economy_snapshot(snapshot, path)
            loaded = load_normalized_economy_snapshot(path)

        self.assertEqual(loaded.snapshot_id, snapshot.snapshot_id)
        self.assertEqual(len(loaded.quotes), len(snapshot.quotes))


class CraftingMaterialEconomyTests(unittest.TestCase):
    def test_ritual_and_essence_raw_fixtures_parse(self):
        ritual = load_raw_poe_show_economy_snapshot(RITUAL_RAW_FIXTURE)
        essence = load_raw_poe_show_economy_snapshot(ESSENCE_RAW_FIXTURE)

        self.assertEqual(ritual["category"], "Ritual")
        self.assertEqual(essence["category"], "Essences")
        self.assertEqual(ritual["response"]["core"]["primary"], "divine")
        self.assertEqual(essence["response"]["core"]["primary"], "divine")
        self.assertIn("volumePrimaryValue", ritual["response"]["lines"][0])
        self.assertIn("volumePrimaryValue", essence["response"]["lines"][0])

    def test_omen_and_essence_asset_mappings_are_explicit(self):
        self.assertEqual(asset_id_for_poe_show("omen-of-putrefaction"), OMEN_OF_PUTREFACTION_ASSET_ID)
        self.assertEqual(asset_id_for_poe_show("perfect-essence-of-battle"), PERFECT_ESSENCE_OF_BATTLE_ASSET_ID)
        self.assertIsNone(asset_id_for_poe_show("not-captured-material"))

    def test_omen_and_essence_normalize_to_exalted(self):
        ritual = normalize_poe_show_economy_snapshot(RITUAL_RAW_FIXTURE, AS_OF)
        essence = normalize_poe_show_economy_snapshot(ESSENCE_RAW_FIXTURE, AS_OF)

        omen = _quote(ritual, OMEN_OF_PUTREFACTION_ASSET_ID)
        battle = _quote(essence, PERFECT_ESSENCE_OF_BATTLE_ASSET_ID)

        self.assertEqual(ritual.exchange_rates[0].rate, Decimal("337.8"))
        self.assertEqual(omen.normalized_value.amount, Decimal("0.21693516"))
        self.assertEqual(battle.normalized_value.amount, Decimal("6.489138"))
        self.assertEqual(omen.category, EconomyCategory.RITUAL)
        self.assertEqual(battle.category, EconomyCategory.ESSENCES)

    def test_category_query_returns_only_category_assets(self):
        repo = _repository_with_all_snapshots()

        ritual_quotes = repo.get_category_quotes(LEAGUE, EconomyCategory.RITUAL, AS_OF)
        essence_quotes = repo.get_category_quotes(LEAGUE, EconomyCategory.ESSENCES, AS_OF)

        self.assertEqual(len(ritual_quotes), 4)
        self.assertEqual(len(essence_quotes), 4)
        self.assertTrue(all(quote.category == EconomyCategory.RITUAL for quote in ritual_quotes))
        self.assertTrue(all(quote.category == EconomyCategory.ESSENCES for quote in essence_quotes))

    def test_missing_rate_for_material_category_fails_honestly(self):
        raw = json.loads(RITUAL_RAW_FIXTURE.read_text(encoding="utf-8"))
        del raw["response"]["core"]["rates"]["exalted"]

        with self.assertRaisesRegex(ValueError, "missing Exalted cross-rate"):
            _normalize_temp_raw(raw)

    def test_multi_material_cost_sums_currency_omen_and_essence(self):
        repo = _repository_with_all_snapshots()

        cost = calculate_craft_material_cost(
            repo,
            LEAGUE,
            (
                CraftMaterialRequirement(PERFECT_EXALTED_ASSET_ID, Decimal("1")),
                CraftMaterialRequirement(OMEN_OF_CATALYSING_EXALTATION_ASSET_ID, Decimal("1")),
                CraftMaterialRequirement(PERFECT_ESSENCE_OF_BATTLE_ASSET_ID, Decimal("2")),
            ),
            AS_OF,
        )

        self.assertTrue(cost.complete)
        self.assertEqual(cost.total.amount, Decimal("908.413202"))
        self.assertEqual(cost.freshness, FreshnessState.FRESH)
        self.assertEqual(len(cost.lines), 3)

    def test_missing_required_material_price_makes_cost_incomplete(self):
        repo = _repository_with_all_snapshots()

        cost = calculate_craft_material_cost(
            repo,
            LEAGUE,
            (
                CraftMaterialRequirement(PERFECT_EXALTED_ASSET_ID, Decimal("1")),
                CraftMaterialRequirement("dc:poe2:economy-asset:ritual:not-captured", Decimal("1")),
            ),
            AS_OF,
        )

        self.assertFalse(cost.complete)
        self.assertIsNone(cost.total)
        self.assertIn("Missing economy quote", cost.warnings[0])

    def test_stale_material_quote_propagates_to_cost(self):
        stale_as_of = datetime(2026, 8, 11, 21, 0, tzinfo=timezone.utc)
        repo = EconomyRepository(
            (
                normalize_poe_show_economy_snapshot(RAW_FIXTURE, stale_as_of),
                normalize_poe_show_economy_snapshot(RITUAL_RAW_FIXTURE, stale_as_of),
            )
        )

        cost = calculate_craft_material_cost(
            repo,
            LEAGUE,
            (
                CraftMaterialRequirement(PERFECT_EXALTED_ASSET_ID, Decimal("1")),
                CraftMaterialRequirement(OMEN_OF_CATALYSING_EXALTATION_ASSET_ID, Decimal("1")),
            ),
            stale_as_of,
        )

        self.assertEqual(cost.freshness, FreshnessState.STALE)
        self.assertTrue(all(line.freshness == FreshnessState.STALE for line in cost.lines))

    def test_explicit_league_scope_for_material_quotes(self):
        repo = _repository_with_all_snapshots()

        self.assertIsNone(repo.get_current_quote("Different League", OMEN_OF_PUTREFACTION_ASSET_ID, AS_OF))

    def test_material_fixture_normalization_reproducibility(self):
        ritual = normalize_poe_show_economy_snapshot(RITUAL_RAW_FIXTURE, AS_OF)
        essence = normalize_poe_show_economy_snapshot(ESSENCE_RAW_FIXTURE, AS_OF)
        loaded_ritual = load_normalized_economy_snapshot(RITUAL_NORMALIZED_FIXTURE)
        loaded_essence = load_normalized_economy_snapshot(ESSENCE_NORMALIZED_FIXTURE)

        self.assertEqual(_quote(ritual, OMEN_OF_CATALYSING_EXALTATION_ASSET_ID).normalized_value.amount, _quote(loaded_ritual, OMEN_OF_CATALYSING_EXALTATION_ASSET_ID).normalized_value.amount)
        self.assertEqual(_quote(essence, PERFECT_ESSENCE_OF_BATTLE_ASSET_ID).normalized_value.amount, _quote(loaded_essence, PERFECT_ESSENCE_OF_BATTLE_ASSET_ID).normalized_value.amount)


def _quote(snapshot, asset_id):
    return next(quote for quote in snapshot.quotes if quote.asset_id == asset_id)


def _normalize_temp_raw(raw):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "raw.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return normalize_poe_show_currency_snapshot(path, AS_OF)


def _repository_with_all_snapshots():
    return EconomyRepository(
        (
            load_normalized_economy_snapshot(NORMALIZED_FIXTURE),
            load_normalized_economy_snapshot(RITUAL_NORMALIZED_FIXTURE),
            load_normalized_economy_snapshot(ESSENCE_NORMALIZED_FIXTURE),
        )
    )


if __name__ == "__main__":
    unittest.main()
