import importlib.util
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.domain import (
    AffixType,
    ClipboardFormat,
    ItemSpecialState,
    ModifierOrigin,
    Rarity,
)
from packages.shared.donniecraftshell_contracts.parser import (
    parse_clipboard_item,
    parse_roll_values,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "poe2" / "quivers"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class Poe2QuiverParserTests(unittest.TestCase):
    def test_rare_standard_advanced_parses_base_rarity_levels_and_affixes(self):
        result = parse_clipboard_item(fixture("quiver_1_rare_standard_advanced.txt"))
        item = result.item

        self.assertIsNone(result.error)
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.clipboard_format, ClipboardFormat.ADVANCED)
        self.assertEqual(item.item_class, "Quivers")
        self.assertEqual(item.rarity, Rarity.RARE)
        self.assertEqual(item.item_name, "Carrion Arrow")
        self.assertEqual(item.base_type, "Toxic Quiver")
        self.assertEqual(item.required_level, 48)
        self.assertEqual(item.item_level, 68)
        self.assertEqual(len(item.implicit_modifiers), 1)
        self.assertEqual(len(item.affix_state.known_prefixes), 3)
        self.assertEqual(len(item.affix_state.known_suffixes), 3)
        self.assertIsNone(item.affix_state.prefix_capacity)
        self.assertEqual(item.affix_state.observed_prefix_count, 3)

    def test_trade_note_is_preserved(self):
        item = parse_clipboard_item(fixture("quiver_2_rare_trade_note_advanced.txt")).item

        assert item is not None
        self.assertEqual(item.trade_note, "~b/o 1 divine")
        self.assertEqual(item.base_type, "Broadhead Quiver")

    def test_normal_item_advanced_and_normal_parse(self):
        normal = parse_clipboard_item(fixture("quiver_3_normal_normal.txt")).item
        advanced = parse_clipboard_item(fixture("quiver_3_normal_advanced.txt")).item

        assert normal is not None and advanced is not None
        self.assertEqual(normal.rarity, Rarity.NORMAL)
        self.assertEqual(normal.base_type, "Blunt Quiver")
        self.assertEqual(normal.clipboard_format, ClipboardFormat.NORMAL)
        self.assertLess(normal.parser_confidence.score, advanced.parser_confidence.score)
        self.assertEqual(normal.implicit_modifiers[0].tier, None)
        self.assertEqual(advanced.clipboard_format, ClipboardFormat.ADVANCED)

    def test_magic_item_normal_missing_tiers_are_not_invented(self):
        item = parse_clipboard_item(fixture("quiver_4_magic_normal.txt")).item

        assert item is not None
        self.assertEqual(item.rarity, Rarity.MAGIC)
        self.assertEqual(item.base_type, "Penetrating Quiver")
        explicit_tiers = [modifier.tier for modifier in item.explicit_modifiers]
        self.assertEqual(explicit_tiers, [None, None])

    def test_magic_item_advanced_prefix_suffix_tiers_and_tags(self):
        item = parse_clipboard_item(fixture("quiver_4_magic_advanced.txt")).item

        assert item is not None
        prefix = item.affix_state.known_prefixes[0]
        suffix = item.affix_state.known_suffixes[0]
        self.assertEqual(prefix.display_name, "Lacerating")
        self.assertEqual(prefix.tier, "2")
        self.assertEqual(prefix.tags, ("Damage",))
        self.assertEqual(prefix.allowed_range[0].min_value, Decimal("43"))
        self.assertEqual(prefix.allowed_range[0].max_value, Decimal("50"))
        self.assertEqual(suffix.display_name, "of Valour")
        self.assertEqual(suffix.tier, "1")

    def test_corrupted_state_parsed(self):
        item = parse_clipboard_item(fixture("quiver_5_rare_corrupted_advanced.txt")).item

        assert item is not None
        self.assertIn(ItemSpecialState.CORRUPTED, item.special_states)

    def test_crafted_and_desecrated_modifier_origins_are_separate_from_affix_type(self):
        item = parse_clipboard_item(fixture("quiver_6_crafted_desecrated_advanced.txt")).item

        assert item is not None
        crafted = next(
            modifier
            for modifier in item.explicit_modifiers
            if modifier.origin == ModifierOrigin.CRAFTED
        )
        desecrated = next(
            modifier
            for modifier in item.explicit_modifiers
            if modifier.origin == ModifierOrigin.DESECRATED
        )
        self.assertEqual(crafted.affix_type, AffixType.PREFIX)
        self.assertEqual(crafted.display_name, "Lacerating")
        self.assertEqual(crafted.tier, "2")
        self.assertEqual(desecrated.affix_type, AffixType.SUFFIX)
        self.assertEqual(desecrated.display_name, "of the Archer")

    def test_twice_corrupted_and_corruption_enhancements_are_preserved_separately(self):
        item = parse_clipboard_item(fixture("quiver_7_twice_corrupted_advanced.txt")).item

        assert item is not None
        self.assertIn(ItemSpecialState.TWICE_CORRUPTED, item.special_states)
        self.assertEqual(len(item.special_modifiers), 2)
        self.assertEqual(len(item.affix_state.known_prefixes), 3)
        self.assertEqual(len(item.affix_state.known_suffixes), 3)
        self.assertTrue(
            all(
                modifier.origin == ModifierOrigin.CORRUPTION_ENHANCEMENT
                for modifier in item.special_modifiers
            )
        )

    def test_unique_item_granted_skill_and_flavor_text(self):
        item = parse_clipboard_item(fixture("quiver_8_unique_advanced.txt")).item

        assert item is not None
        self.assertEqual(item.rarity, Rarity.UNIQUE)
        self.assertEqual(item.granted_skills, ("Level 18 Bursting Fen Toad",))
        self.assertTrue(
            all("Boiling frogs" not in modifier.raw_text for modifier in item.modifiers)
        )
        self.assertIn("rumour. They're actually for brewing poisons.\"", item.unparsed_lines)

    def test_unknown_lines_are_preserved_with_warning(self):
        raw = fixture("quiver_3_normal_advanced.txt") + "\n--------\nUnrecognized Future Section"
        result = parse_clipboard_item(raw)
        item = result.item

        assert item is not None
        self.assertIn("Unrecognized Future Section", item.unparsed_lines)
        self.assertIn("Unrecognized Future Section", result.unparsed_sections)
        self.assertIn("Some lines were preserved as unparsed text.", item.warnings)
        self.assertIn("Some sections were preserved as wholly unparsed text.", item.warnings)

    def test_partially_parsed_sections_are_not_duplicated_as_unparsed_sections(self):
        raw = fixture("quiver_3_normal_advanced.txt").replace(
            "40(25-40)% increased Stun Buildup",
            "40(25-40)% increased Stun Buildup\nUnrecognized trailing line",
        )
        result = parse_clipboard_item(raw)

        assert result.item is not None
        self.assertIn("Unrecognized trailing line", result.item.unparsed_lines)
        self.assertEqual(result.unparsed_sections, ())

    def test_generated_analysis_id_is_uuid7(self):
        item = parse_clipboard_item(fixture("quiver_1_rare_standard_advanced.txt")).item

        assert item is not None
        generated_uuid = uuid.UUID(item.analysis_id.removeprefix("analysis-"))
        self.assertEqual(generated_uuid.version, 7)

    def test_malformed_modifier_header_fails_gracefully(self):
        raw = fixture("quiver_3_normal_advanced.txt").replace(
            "{ Implicit Modifier }",
            "{ Implicit Modifier",
        )
        result = parse_clipboard_item(raw)

        self.assertIsNone(result.error)
        assert result.item is not None
        self.assertIn("{ Implicit Modifier", result.item.unparsed_lines)

    def test_twice_corrupted_does_not_also_add_corrupted_state(self):
        item = parse_clipboard_item(fixture("quiver_7_twice_corrupted_advanced.txt")).item

        assert item is not None
        self.assertIn(ItemSpecialState.TWICE_CORRUPTED, item.special_states)
        self.assertNotIn(ItemSpecialState.CORRUPTED, item.special_states)

    def test_empty_and_non_poe_inputs_return_structured_errors(self):
        empty = parse_clipboard_item("")
        garbage = parse_clipboard_item("not an item")

        self.assertIsNotNone(empty.error)
        self.assertIsNotNone(garbage.error)
        self.assertTrue(empty.error.reliable_no_result)
        self.assertTrue(garbage.error.reliable_no_result)


class ModifierValueParsingTests(unittest.TestCase):
    def test_single_value_with_range(self):
        rolls = parse_roll_values("+20(17-20) to Dexterity")

        self.assertEqual(rolls[0].value, Decimal("20"))
        self.assertEqual(rolls[0].min_value, Decimal("17"))
        self.assertEqual(rolls[0].max_value, Decimal("20"))

    def test_two_values_with_ranges(self):
        rolls = parse_roll_values(
            "Adds 2(1-2) to 47(41-47) Lightning damage to Attacks"
        )

        self.assertEqual(len(rolls), 2)
        self.assertEqual(rolls[0].value, Decimal("2"))
        self.assertEqual(rolls[1].value, Decimal("47"))

    def test_plain_value_has_unknown_range(self):
        rolls = parse_roll_values("Adds 1 to 3 Physical Damage to Attacks")

        self.assertEqual([roll.value for roll in rolls], [Decimal("1"), Decimal("3")])
        self.assertTrue(all(roll.min_value is None for roll in rolls))


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class FastApiParseRouteTests(unittest.TestCase):
    def test_parse_route_returns_item(self):
        from fastapi.testclient import TestClient
        from services.api.app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/items/parse",
            json={"raw_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["base_type"], "Primed Quiver")

    def test_parse_route_returns_structured_error_for_empty_input(self):
        from fastapi.testclient import TestClient
        from services.api.app.main import app

        client = TestClient(app)
        response = client.post("/api/v1/items/parse", json={"raw_clipboard_text": ""})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["item"])
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")
        self.assertTrue(body["error"]["reliable_no_result"])

    def test_parse_route_returns_structured_error_for_non_item_input(self):
        from fastapi.testclient import TestClient
        from services.api.app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/items/parse",
            json={"raw_clipboard_text": "hello this is not a poe item"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["item"])
        self.assertEqual(body["error"]["code"], "PARSE_FAILURE")
        self.assertTrue(body["error"]["reliable_no_result"])


if __name__ == "__main__":
    unittest.main()
