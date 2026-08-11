import unittest
from decimal import Decimal

from packages.shared.donniecraftshell_contracts.domain import (
    AffixType,
    GameContext,
    ItemModifier,
    ParsedItem,
    Rarity,
)
from packages.shared.donniecraftshell_contracts.game_data import (
    GameDataSnapshot,
    ItemEnrichment,
    ModifierFamily,
    ModifierResolution,
    ModifierResolutionCandidate,
    ModifierTierDefinition,
    ModifierWeight,
    ResolutionStatus,
)


class GameDataContractTests(unittest.TestCase):
    def test_unresolved_modifier_can_exist_without_canonical_id(self):
        resolution = ModifierResolution(
            parsed_modifier=ItemModifier(raw_text="13% increased Attack Speed"),
            status=ResolutionStatus.UNRESOLVED,
            warnings=("No verified snapshot match.",),
        )

        self.assertIsNone(resolution.selected_canonical_modifier_id)

    def test_ambiguous_resolution_cannot_select_fake_canonical_id(self):
        candidates = (
            ModifierResolutionCandidate(canonical_modifier_id="poe2db:mod:a"),
            ModifierResolutionCandidate(canonical_modifier_id="poe2db:mod:b"),
        )

        with self.assertRaises(ValueError):
            ModifierResolution(
                parsed_modifier=ItemModifier(raw_text="13% increased Attack Speed"),
                status=ResolutionStatus.AMBIGUOUS,
                selected_canonical_modifier_id="poe2db:mod:a",
                candidates=candidates,
            )

    def test_weight_missing_is_not_zero(self):
        weight = ModifierWeight(modifier_id="poe2db:mod:increased_attack_speed")

        self.assertIsNone(weight.weight)

    def test_original_parsed_item_remains_unchanged_after_enrichment(self):
        parsed_item = ParsedItem(
            analysis_id="analysis-test",
            raw_clipboard_text="raw",
            game_context=GameContext(game="Path of Exile 2"),
            rarity=Rarity.RARE,
            modifiers=(ItemModifier(raw_text="13% increased Attack Speed"),),
        )
        enrichment = ItemEnrichment(
            enrichment_id="enrichment-test",
            parsed_item=parsed_item,
            snapshot_id="snapshot-test",
            modifier_resolutions=(
                ModifierResolution(
                    parsed_modifier=parsed_item.modifiers[0],
                    status=ResolutionStatus.RESOLVED,
                    selected_canonical_modifier_id="poe2db:mod:3ac5789",
                ),
            ),
        )

        self.assertIs(enrichment.parsed_item, parsed_item)
        self.assertIsNone(parsed_item.modifiers[0].canonical_id)

    def test_canonical_ids_must_be_source_backed_not_display_names(self):
        with self.assertRaises(ValueError):
            ModifierTierDefinition(
                canonical_id="of Mastery",
                modifier_family_id="poe2db:family:IncreasedAttackSpeed",
                display_name="of Mastery",
            )

        tier = ModifierTierDefinition(
            canonical_id="poe2db:mod:3ac5789",
            modifier_family_id="poe2db:family:IncreasedAttackSpeed",
            display_name="of Mastery",
            required_item_level=37,
        )

        self.assertEqual(tier.display_name, "of Mastery")

    def test_family_id_is_namespaced_and_affix_type_explicit(self):
        family = ModifierFamily(
            canonical_id="poe2db:family:IncreasedAttackSpeed",
            normalized_stat_template="#% increased Attack Speed",
            affix_type=AffixType.SUFFIX,
        )

        self.assertEqual(family.affix_type, AffixType.SUFFIX)

    def test_negative_weight_is_rejected_when_weight_exists(self):
        with self.assertRaises(ValueError):
            ModifierWeight(
                modifier_id="poe2db:mod:increased_attack_speed",
                weight=Decimal("-1"),
            )

    def test_snapshot_can_be_provisional_community_data(self):
        snapshot = GameDataSnapshot(
            snapshot_id="snapshot-test",
            source="poe2db",
            source_uri="https://poe2db.tw/us/Quivers",
        )

        self.assertEqual(snapshot.source, "poe2db")


if __name__ == "__main__":
    unittest.main()
