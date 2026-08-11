"""Small explicit economy asset mapping for Task 6B."""

from __future__ import annotations

from .economy import (
    DIVINE_ASSET_ID,
    EXALTED_ASSET_ID,
    GREATER_EXALTED_ASSET_ID,
    PERFECT_EXALTED_ASSET_ID,
    EconomyAsset,
    EconomyCategory,
)


POE_SHOW_ASSET_ALIASES = {
    "exalted": EXALTED_ASSET_ID,
    "divine": DIVINE_ASSET_ID,
    "perfect-exalted-orb": PERFECT_EXALTED_ASSET_ID,
    "greater-exalted-orb": GREATER_EXALTED_ASSET_ID,
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
}


def asset_id_for_poe_show(source_id: str) -> str | None:
    return POE_SHOW_ASSET_ALIASES.get(source_id)
