"""Build the Task 8C offline Quiver natural Base modifier raw fixture.

This is a deterministic data-capture helper. It does not perform network I/O.
The captured records are factual structured rows from the selected PoE2DB
Quivers research snapshot and intentionally exclude weights/probabilities.
"""

from __future__ import annotations

import json
from pathlib import Path


SOURCE_URI = "https://poe2db.tw/us/Quivers"
RETRIEVED_AT = "2026-08-12T00:00:00+02:00"
OUTPUT = Path("data/raw/poe2db/quiver-natural-base-modifiers-2026-08-12/raw_modifiers.json")


def stat(text: str, min_value: int, max_value: int) -> dict[str, object]:
    return {"text": text, "min": str(min_value), "max": str(max_value), "scope": "Global"}


def record(
    *,
    display_name: str,
    family: str,
    generation_type: str,
    required_level: int,
    tier: int,
    stats: list[dict[str, object]],
    craft_tags: list[str],
    source_record_key: str | None = None,
) -> dict[str, object]:
    return {
        "source_record_key": source_record_key,
        "source_uri": SOURCE_URI,
        "retrieved_at": RETRIEVED_AT,
        "display_name": display_name,
        "family": family,
        "domain": "Item",
        "generation_type": generation_type,
        "required_level": required_level,
        "tier": str(tier),
        "stats": stats,
        "spawn_tags": {"quiver": 1, "default": 0},
        "craft_tags": craft_tags,
        "notes": [
            "Task 8C manually captured structured natural Base Quiver modifier row.",
            "Weights/probabilities are intentionally excluded.",
        ],
    }


def two_stat_family(
    family: str,
    generation_type: str,
    min_label: str,
    max_label: str,
    craft_tags: list[str],
    rows: list[tuple[int, str, int, tuple[int, int], tuple[int, int]]],
) -> list[dict[str, object]]:
    return [
        record(
            display_name=name,
            family=family,
            generation_type=generation_type,
            required_level=level,
            tier=tier,
            stats=[stat(min_label, *min_range), stat(max_label, *max_range)],
            craft_tags=craft_tags,
        )
        for tier, name, level, min_range, max_range in rows
    ]


def single_stat_family(
    family: str,
    generation_type: str,
    label: str,
    craft_tags: list[str],
    rows: list[tuple[int, str, int, tuple[int, int]]],
) -> list[dict[str, object]]:
    return [
        record(
            display_name=name,
            family=family,
            generation_type=generation_type,
            required_level=level,
            tier=tier,
            stats=[stat(label, *value_range)],
            craft_tags=craft_tags,
        )
        for tier, name, level, value_range in rows
    ]


def build_records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    records += two_stat_family(
        "PhysicalDamage",
        "Prefix",
        "attack minimum added physical damage",
        "attack maximum added physical damage",
        ["Damage", "Physical", "Attack"],
        [
            (9, "Glinting", 1, (1, 2), (3, 3)),
            (8, "Burnished", 8, (2, 3), (4, 6)),
            (7, "Polished", 16, (2, 4), (5, 8)),
            (6, "Honed", 33, (4, 6), (8, 11)),
            (5, "Gleaming", 46, (5, 7), (9, 13)),
            (4, "Annealed", 54, (6, 10), (12, 17)),
            (3, "Razor-sharp", 60, (7, 11), (14, 20)),
            (2, "Tempered", 65, (10, 15), (18, 26)),
            (1, "Flaring", 75, (12, 19), (22, 32)),
        ],
    )
    records += two_stat_family(
        "FireDamage",
        "Prefix",
        "attack minimum added fire damage",
        "attack maximum added fire damage",
        ["Damage", "Elemental", "Fire", "Attack"],
        [
            (9, "Heated", 1, (1, 2), (3, 3)),
            (8, "Smouldering", 8, (3, 5), (6, 9)),
            (7, "Smoking", 16, (6, 8), (10, 13)),
            (6, "Burning", 33, (9, 11), (14, 17)),
            (5, "Flaming", 46, (12, 13), (18, 20)),
            (4, "Scorching", 54, (11, 16), (21, 26)),
            (3, "Incinerating", 60, (13, 19), (27, 32)),
            (2, "Blasting", 65, (20, 24), (33, 36)),
            (1, "Cremating", 75, (25, 29), (37, 45)),
        ],
    )
    records += two_stat_family(
        "ColdDamage",
        "Prefix",
        "attack minimum added cold damage",
        "attack maximum added cold damage",
        ["Damage", "Elemental", "Cold", "Attack"],
        [
            (9, "Frosted", 1, (1, 1), (2, 3)),
            (8, "Chilled", 8, (3, 4), (5, 8)),
            (7, "Icy", 16, (5, 6), (9, 11)),
            (6, "Frigid", 33, (7, 8), (12, 14)),
            (5, "Freezing", 46, (9, 10), (15, 17)),
            (4, "Frozen", 54, (11, 13), (18, 21)),
            (3, "Glaciated", 60, (14, 15), (22, 24)),
            (2, "Polar", 65, (16, 20), (25, 31)),
            (1, "Entombing", 75, (21, 24), (32, 37)),
        ],
    )
    records += two_stat_family(
        "LightningDamage",
        "Prefix",
        "attack minimum added lightning damage",
        "attack maximum added lightning damage",
        ["Damage", "Elemental", "Lightning", "Attack"],
        [
            (9, "Humming", 1, (1, 1), (4, 6)),
            (8, "Buzzing", 8, (1, 1), (10, 15)),
            (7, "Snapping", 16, (1, 1), (16, 22)),
            (6, "Crackling", 33, (1, 1), (23, 27)),
            (5, "Sparking", 46, (1, 1), (28, 32)),
            (4, "Arcing", 54, (1, 2), (33, 40)),
            (3, "Shocking", 60, (1, 2), (41, 47)),
            (2, "Discharging", 65, (1, 3), (48, 59)),
            (1, "Electrocuting", 75, (1, 4), (60, 71)),
        ],
    )
    records += single_stat_family(
        "IncreasedAccuracy",
        "Prefix",
        "accuracy rating",
        ["Attack"],
        [
            (9, "Precise", 1, (11, 32)),
            (8, "Reliable", 11, (33, 60)),
            (7, "Focused", 18, (61, 84)),
            (6, "Deliberate", 26, (85, 123)),
            (5, "Consistent", 36, (124, 167)),
            (4, "Steady", 48, (168, 236)),
            (3, "Hunter's", 58, (237, 346)),
            (2, "Ranger's", 67, (347, 450)),
            (1, "Amazon's", 76, (451, 550)),
        ],
    )
    records += single_stat_family(
        "ProjectileSpeed",
        "Prefix",
        "base projectile speed +%",
        ["Speed"],
        [
            (5, "Darting", 14, (10, 17)),
            (4, "Brisk", 27, (18, 25)),
            (3, "Quick", 41, (26, 33)),
            (2, "Rapid", 55, (34, 41)),
            (1, "Nimble", 82, (42, 46)),
        ],
    )
    records += single_stat_family(
        "DamageWithWeaponTypeSkill",
        "Prefix",
        "damage +% with bow skills",
        ["Damage"],
        [
            (6, "Acute", 1, (11, 20)),
            (5, "Trenchant", 16, (21, 30)),
            (4, "Perforating", 33, (31, 36)),
            (3, "Incisive", 46, (37, 42)),
            (2, "Lacerating", 60, (43, 50)),
            (1, "Impaling", 81, (51, 59)),
        ],
    )
    records += single_stat_family(
        "Dexterity",
        "Suffix",
        "additional dexterity",
        ["Attribute"],
        [
            (8, "of the Mongoose", 1, (5, 8)),
            (7, "of the Lynx", 11, (9, 12)),
            (6, "of the Fox", 22, (13, 16)),
            (5, "of the Falcon", 33, (17, 20)),
            (4, "of the Panther", 44, (21, 24)),
            (3, "of the Leopard", 55, (25, 27)),
            (2, "of the Jaguar", 66, (28, 30)),
            (1, "of the Phantom", 74, (31, 33)),
        ],
    )
    records += single_stat_family(
        "IncreaseSocketedGemLevel",
        "Suffix",
        "projectile skill gem level +",
        [],
        [(1, "of the Archer", 5, (1, 1))],
    )
    records += single_stat_family(
        "LifeGainedFromEnemyDeath",
        "Suffix",
        "base life gained on enemy death",
        ["Life"],
        [
            (6, "of Success", 1, (4, 6)),
            (5, "of Victory", 11, (7, 9)),
            (4, "of Triumph", 22, (10, 18)),
            (3, "of Conquest", 33, (19, 28)),
            (2, "of Vanquishing", 44, (29, 40)),
            (1, "of Valour", 55, (41, 53)),
        ],
    )
    records += single_stat_family(
        "ManaGainedFromEnemyDeath",
        "Suffix",
        "base mana gained on enemy death",
        ["Mana"],
        [
            (6, "of Absorption", 1, (2, 3)),
            (5, "of Osmosis", 12, (4, 5)),
            (4, "of Infusion", 23, (6, 9)),
            (3, "of Enveloping", 34, (10, 14)),
            (2, "of Consumption", 45, (15, 20)),
            (1, "of Siphoning", 56, (21, 27)),
        ],
    )
    records += single_stat_family(
        "IncreasedAttackSpeed",
        "Suffix",
        "attack speed +%",
        ["Attack", "Speed"],
        [
            (4, "of Skill", 1, (5, 7)),
            (3, "of Ease", 22, (8, 10)),
            (2, "of Mastery", 37, (11, 13)),
            (1, "of Renown", 60, (14, 16)),
        ],
    )
    records += single_stat_family(
        "CriticalStrikeChanceIncrease",
        "Suffix",
        "attack critical strike chance +%",
        ["Attack", "Critical"],
        [
            (6, "of Menace", 5, (10, 14)),
            (5, "of Havoc", 20, (15, 19)),
            (4, "of Disaster", 30, (20, 24)),
            (3, "of Calamity", 44, (25, 29)),
            (2, "of Ruin", 58, (30, 34)),
            (1, "of Unmaking", 72, (35, 38)),
        ],
    )
    records += single_stat_family(
        "CriticalStrikeMultiplier",
        "Suffix",
        "attack critical strike multiplier +",
        ["Damage", "Attack", "Critical"],
        [
            (6, "of Ire", 8, (10, 14)),
            (5, "of Anger", 21, (15, 19)),
            (4, "of Rage", 31, (20, 24)),
            (3, "of Fury", 45, (25, 29)),
            (2, "of Ferocity", 59, (30, 34)),
            (1, "of Destruction", 74, (35, 39)),
        ],
    )
    records += single_stat_family(
        "ChanceToPierce",
        "Suffix",
        "base chance to pierce %",
        [],
        [
            (5, "of Piercing", 11, (12, 14)),
            (4, "of Drilling", 26, (15, 17)),
            (3, "of Puncturing", 44, (18, 20)),
            (2, "of Skewering", 61, (21, 23)),
            (1, "of Penetrating", 77, (24, 26)),
        ],
    )
    records += single_stat_family(
        "AdditionalArrows",
        "Suffix",
        "chance to fire 1 additional projectile % with rollover with bow attacks",
        ["Attack"],
        [
            (2, "of Surplus", 46, (25, 40)),
            (1, "of Splintering", 80, (41, 60)),
        ],
    )
    return records


def main() -> None:
    data = {
        "snapshot": {
            "snapshot_id": "poe2db-quiver-natural-base-modifiers-2026-08-12",
            "source": "poe2db",
            "source_uri": SOURCE_URI,
            "retrieved_at": RETRIEVED_AT,
            "game": "Path of Exile 2",
            "game_version": "unknown-version",
            "locale": "us",
            "checksum": "task8c-fullx1",
            "verification_status": "NEEDS_VERIFICATION",
            "notes": (
                "Task 8C offline manual capture of natural explicit Base Prefix/Base Suffix Quiver modifiers "
                "from PoE2DB structured rows. PoE2DB is a community source, not official GGG data. "
                "Modifier weights/probabilities are deliberately excluded."
            ),
        },
        "records": build_records(),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {len(data['records'])} records to {OUTPUT}")


if __name__ == "__main__":
    main()
