"""Small explicit economy asset mapping for Task 6B."""

from __future__ import annotations

from .economy import (
    DIVINE_ASSET_ID,
    ESSENCE_OF_HYSTERIA_ASSET_ID,
    EXALTED_ASSET_ID,
    GREATER_EXALTED_ASSET_ID,
    ESSENCE_OF_ENHANCEMENT_ASSET_ID,
    ORB_OF_ANNULMENT_ASSET_ID,
    PERFECT_EXALTED_ASSET_ID,
    GREATER_ESSENCE_OF_ICE_ASSET_ID,
    OMEN_OF_CATALYSING_EXALTATION_ASSET_ID,
    OMEN_OF_CHAOTIC_MONSTERS_ASSET_ID,
    OMEN_OF_DEXTRAL_ANNULMENT_ASSET_ID,
    OMEN_OF_DEXTRAL_EXALTATION_ASSET_ID,
    OMEN_OF_LIGHT_ASSET_ID,
    OMEN_OF_PUTREFACTION_ASSET_ID,
    OMEN_OF_SINISTRAL_ANNULMENT_ASSET_ID,
    OMEN_OF_SINISTRAL_EXALTATION_ASSET_ID,
    PERFECT_ESSENCE_OF_ALACRITY_ASSET_ID,
    PERFECT_ESSENCE_OF_BATTLE_ASSET_ID,
    EconomyAsset,
    EconomyCategory,
)


POE_SHOW_ASSET_ALIASES = {
    "exalted": EXALTED_ASSET_ID,
    "divine": DIVINE_ASSET_ID,
    "perfect-exalted-orb": PERFECT_EXALTED_ASSET_ID,
    "greater-exalted-orb": GREATER_EXALTED_ASSET_ID,
    "orb-of-annulment": ORB_OF_ANNULMENT_ASSET_ID,
    "omen-of-sinistral-exaltation": OMEN_OF_SINISTRAL_EXALTATION_ASSET_ID,
    "omen-of-dextral-exaltation": OMEN_OF_DEXTRAL_EXALTATION_ASSET_ID,
    "omen-of-sinistral-annulment": OMEN_OF_SINISTRAL_ANNULMENT_ASSET_ID,
    "omen-of-dextral-annulment": OMEN_OF_DEXTRAL_ANNULMENT_ASSET_ID,
    "omen-of-putrefaction": OMEN_OF_PUTREFACTION_ASSET_ID,
    "omen-of-catalysing-exaltation": OMEN_OF_CATALYSING_EXALTATION_ASSET_ID,
    "omen-of-chaotic-monsters": OMEN_OF_CHAOTIC_MONSTERS_ASSET_ID,
    "omen-of-light": OMEN_OF_LIGHT_ASSET_ID,
    "perfect-essence-of-battle": PERFECT_ESSENCE_OF_BATTLE_ASSET_ID,
    "perfect-essence-of-alacrity": PERFECT_ESSENCE_OF_ALACRITY_ASSET_ID,
    "greater-essence-of-ice": GREATER_ESSENCE_OF_ICE_ASSET_ID,
    "essence-of-enhancement": ESSENCE_OF_ENHANCEMENT_ASSET_ID,
    "essence-of-hysteria": ESSENCE_OF_HYSTERIA_ASSET_ID,
}


ASSETS_BY_ID = {
    EXALTED_ASSET_ID: EconomyAsset(
        asset_id=EXALTED_ASSET_ID,
        game="Path of Exile 2",
        display_name="Exalted Orb",
        category=EconomyCategory.CURRENCY,
        source_aliases={"poe.show": "exalted"},
    ),
    DIVINE_ASSET_ID: EconomyAsset(
        asset_id=DIVINE_ASSET_ID,
        game="Path of Exile 2",
        display_name="Divine Orb",
        category=EconomyCategory.CURRENCY,
        source_aliases={"poe.show": "divine"},
    ),
    PERFECT_EXALTED_ASSET_ID: EconomyAsset(
        asset_id=PERFECT_EXALTED_ASSET_ID,
        game="Path of Exile 2",
        display_name="Perfect Exalted Orb",
        category=EconomyCategory.CURRENCY,
        source_aliases={"poe.show": "perfect-exalted-orb"},
    ),
    GREATER_EXALTED_ASSET_ID: EconomyAsset(
        asset_id=GREATER_EXALTED_ASSET_ID,
        game="Path of Exile 2",
        display_name="Greater Exalted Orb",
        category=EconomyCategory.CURRENCY,
        source_aliases={"poe.show": "greater-exalted-orb"},
    ),
    ORB_OF_ANNULMENT_ASSET_ID: EconomyAsset(
        asset_id=ORB_OF_ANNULMENT_ASSET_ID,
        game="Path of Exile 2",
        display_name="Orb of Annulment",
        category=EconomyCategory.CURRENCY,
        source_aliases={"poe.show": "orb-of-annulment", "poe2db": "Orb of Annulment"},
    ),
    OMEN_OF_SINISTRAL_EXALTATION_ASSET_ID: EconomyAsset(
        asset_id=OMEN_OF_SINISTRAL_EXALTATION_ASSET_ID,
        game="Path of Exile 2",
        display_name="Omen of Sinistral Exaltation",
        category=EconomyCategory.RITUAL,
        source_aliases={"poe.show": "omen-of-sinistral-exaltation", "poe2db": "Omen of Sinistral Exaltation"},
    ),
    OMEN_OF_DEXTRAL_EXALTATION_ASSET_ID: EconomyAsset(
        asset_id=OMEN_OF_DEXTRAL_EXALTATION_ASSET_ID,
        game="Path of Exile 2",
        display_name="Omen of Dextral Exaltation",
        category=EconomyCategory.RITUAL,
        source_aliases={"poe.show": "omen-of-dextral-exaltation", "poe2db": "Omen of Dextral Exaltation"},
    ),
    OMEN_OF_SINISTRAL_ANNULMENT_ASSET_ID: EconomyAsset(
        asset_id=OMEN_OF_SINISTRAL_ANNULMENT_ASSET_ID,
        game="Path of Exile 2",
        display_name="Omen of Sinistral Annulment",
        category=EconomyCategory.RITUAL,
        source_aliases={"poe.show": "omen-of-sinistral-annulment", "poe2db": "Omen of Sinistral Annulment"},
    ),
    OMEN_OF_DEXTRAL_ANNULMENT_ASSET_ID: EconomyAsset(
        asset_id=OMEN_OF_DEXTRAL_ANNULMENT_ASSET_ID,
        game="Path of Exile 2",
        display_name="Omen of Dextral Annulment",
        category=EconomyCategory.RITUAL,
        source_aliases={"poe.show": "omen-of-dextral-annulment", "poe2db": "Omen of Dextral Annulment"},
    ),
    OMEN_OF_PUTREFACTION_ASSET_ID: EconomyAsset(
        asset_id=OMEN_OF_PUTREFACTION_ASSET_ID,
        game="Path of Exile 2",
        display_name="Omen of Putrefaction",
        category=EconomyCategory.RITUAL,
        source_aliases={"poe.show": "omen-of-putrefaction"},
    ),
    OMEN_OF_CATALYSING_EXALTATION_ASSET_ID: EconomyAsset(
        asset_id=OMEN_OF_CATALYSING_EXALTATION_ASSET_ID,
        game="Path of Exile 2",
        display_name="Omen of Catalysing Exaltation",
        category=EconomyCategory.RITUAL,
        source_aliases={"poe.show": "omen-of-catalysing-exaltation"},
    ),
    OMEN_OF_CHAOTIC_MONSTERS_ASSET_ID: EconomyAsset(
        asset_id=OMEN_OF_CHAOTIC_MONSTERS_ASSET_ID,
        game="Path of Exile 2",
        display_name="Omen of Chaotic Monsters",
        category=EconomyCategory.RITUAL,
        source_aliases={"poe.show": "omen-of-chaotic-monsters"},
    ),
    OMEN_OF_LIGHT_ASSET_ID: EconomyAsset(
        asset_id=OMEN_OF_LIGHT_ASSET_ID,
        game="Path of Exile 2",
        display_name="Omen of Light",
        category=EconomyCategory.RITUAL,
        source_aliases={"poe.show": "omen-of-light"},
    ),
    PERFECT_ESSENCE_OF_BATTLE_ASSET_ID: EconomyAsset(
        asset_id=PERFECT_ESSENCE_OF_BATTLE_ASSET_ID,
        game="Path of Exile 2",
        display_name="Perfect Essence of Battle",
        category=EconomyCategory.ESSENCES,
        source_aliases={"poe.show": "perfect-essence-of-battle"},
    ),
    PERFECT_ESSENCE_OF_ALACRITY_ASSET_ID: EconomyAsset(
        asset_id=PERFECT_ESSENCE_OF_ALACRITY_ASSET_ID,
        game="Path of Exile 2",
        display_name="Perfect Essence of Alacrity",
        category=EconomyCategory.ESSENCES,
        source_aliases={"poe.show": "perfect-essence-of-alacrity"},
    ),
    GREATER_ESSENCE_OF_ICE_ASSET_ID: EconomyAsset(
        asset_id=GREATER_ESSENCE_OF_ICE_ASSET_ID,
        game="Path of Exile 2",
        display_name="Greater Essence of Ice",
        category=EconomyCategory.ESSENCES,
        source_aliases={"poe.show": "greater-essence-of-ice"},
    ),
    ESSENCE_OF_ENHANCEMENT_ASSET_ID: EconomyAsset(
        asset_id=ESSENCE_OF_ENHANCEMENT_ASSET_ID,
        game="Path of Exile 2",
        display_name="Essence of Enhancement",
        category=EconomyCategory.ESSENCES,
        source_aliases={"poe.show": "essence-of-enhancement"},
    ),
    ESSENCE_OF_HYSTERIA_ASSET_ID: EconomyAsset(
        asset_id=ESSENCE_OF_HYSTERIA_ASSET_ID,
        game="Path of Exile 2",
        display_name="Essence of Hysteria",
        category=EconomyCategory.ESSENCES,
        source_aliases={"poe.show": "essence-of-hysteria", "poe2db": "Essence of Hysteria"},
    ),
}


def asset_id_for_poe_show(source_id: str) -> str | None:
    return POE_SHOW_ASSET_ALIASES.get(source_id)
