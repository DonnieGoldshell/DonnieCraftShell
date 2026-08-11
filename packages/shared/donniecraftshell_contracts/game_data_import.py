"""Offline game-data import and normalization helpers.

This module reads manually captured raw source snapshots and produces
DonnieCraftShell normalized game-data records. It performs no live network I/O.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .domain import (
    AffixType,
    Confidence,
    ConfidenceLevel,
    DataProvenance,
    GameContext,
    RollValue,
    SourceType,
    VerificationStatus,
)
from .game_data import (
    GameDataSnapshot,
    ModifierApplicability,
    ModifierFamily,
    ModifierTierDefinition,
)


@dataclass(frozen=True)
class RawPoe2DbStat:
    text: str
    min: Decimal | None = None
    max: Decimal | None = None
    scope: str | None = None


@dataclass(frozen=True)
class RawPoe2DbModifierRecord:
    source_record_key: str | None
    source_uri: str
    retrieved_at: datetime
    display_name: str
    family: str
    domain: str | None
    generation_type: str
    required_level: int | None
    tier: str | None
    stats: tuple[RawPoe2DbStat, ...]
    spawn_tags: dict[str, int]
    craft_tags: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizedGameDataSet:
    snapshot: GameDataSnapshot
    dataset_version: str
    modifier_families: tuple[ModifierFamily, ...]
    modifier_tiers: tuple[ModifierTierDefinition, ...]
    modifier_applicability: tuple[ModifierApplicability, ...]


def load_raw_poe2db_snapshot(path: Path) -> tuple[GameDataSnapshot, tuple[RawPoe2DbModifierRecord, ...]]:
    data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    snapshot_data = data["snapshot"]
    snapshot = GameDataSnapshot(
        snapshot_id=snapshot_data["snapshot_id"],
        source=snapshot_data["source"],
        source_uri=snapshot_data.get("source_uri"),
        retrieved_at=_parse_datetime(snapshot_data.get("retrieved_at")),
        game_context=GameContext(
            game=snapshot_data.get("game", "Path of Exile 2"),
            game_version=snapshot_data.get("game_version"),
            locale=snapshot_data.get("locale"),
        ),
        checksum=snapshot_data.get("checksum"),
        verification_status=VerificationStatus[snapshot_data.get("verification_status", "NEEDS_VERIFICATION")],
        notes=snapshot_data.get("notes"),
    )
    records = tuple(_raw_record(record) for record in data.get("records", []))
    return snapshot, records


def normalize_poe2db_snapshot(path: Path) -> NormalizedGameDataSet:
    snapshot, records = load_raw_poe2db_snapshot(path)
    if not snapshot.snapshot_id:
        raise ValueError("snapshot_id is required")
    dataset_version = _dataset_version(snapshot)
    families_by_id: dict[str, ModifierFamily] = {}
    tiers: list[ModifierTierDefinition] = []
    applicability: list[ModifierApplicability] = []

    for record in records:
        affix_type = _affix_type(record.generation_type)
        family_id = canonical_family_id(record.family)
        provenance = (_provenance(record, snapshot),)
        families_by_id.setdefault(
            family_id,
            ModifierFamily(
                canonical_id=family_id,
                normalized_stat_template=_stat_template(record.stats),
                affix_type=affix_type,
                tags=tuple(sorted(set(record.craft_tags))),
                modifier_group=record.family,
                provenance=provenance,
            ),
        )
        tier_id = canonical_modifier_tier_id(record)
        roll_ranges = tuple(
            RollValue(label=stat.text, min_value=stat.min, max_value=stat.max)
            for stat in record.stats
        )
        tiers.append(
            ModifierTierDefinition(
                canonical_id=tier_id,
                modifier_family_id=family_id,
                tier=record.tier,
                display_name=record.display_name,
                required_item_level=record.required_level,
                roll_ranges=roll_ranges,
                source_record_key=record.source_record_key,
                source_locator=record.source_uri,
                provenance=provenance,
                dataset_version=dataset_version,
            )
        )
        for tag, enabled in record.spawn_tags.items():
            if enabled:
                applicability.append(
                    ModifierApplicability(
                        modifier_id=tier_id,
                        item_class=_item_class_from_spawn_tag(tag),
                        tags_or_conditions=(f"spawn_tag:{tag}",),
                        provenance=provenance,
                    )
                )

    dataset = NormalizedGameDataSet(
        snapshot=snapshot,
        dataset_version=dataset_version,
        modifier_families=tuple(families_by_id.values()),
        modifier_tiers=tuple(tiers),
        modifier_applicability=tuple(applicability),
    )
    validate_normalized_dataset(dataset)
    return dataset


def write_normalized_dataset(dataset: NormalizedGameDataSet, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(dataset), indent=2), encoding="utf-8")


def load_normalized_dataset(path: Path) -> NormalizedGameDataSet:
    data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    snapshot_data = data["snapshot"]
    snapshot = GameDataSnapshot(
        snapshot_id=snapshot_data["snapshot_id"],
        source=snapshot_data["source"],
        source_uri=snapshot_data.get("source_uri"),
        retrieved_at=_parse_datetime(snapshot_data.get("retrieved_at")),
        game_context=GameContext(**snapshot_data["game_context"]) if snapshot_data.get("game_context") else None,
        checksum=snapshot_data.get("checksum"),
        verification_status=VerificationStatus[snapshot_data.get("verification_status", "NEEDS_VERIFICATION")],
        notes=snapshot_data.get("notes"),
    )
    dataset = NormalizedGameDataSet(
        snapshot=snapshot,
        dataset_version=data["dataset_version"],
        modifier_families=tuple(
            ModifierFamily(
                canonical_id=item["canonical_id"],
                normalized_stat_template=item["normalized_stat_template"],
                affix_type=AffixType[item.get("affix_type", "UNKNOWN")],
                tags=tuple(item.get("tags", [])),
                modifier_group=item.get("modifier_group"),
                provenance=tuple(_provenance_from_json(p) for p in item.get("provenance", [])),
            )
            for item in data.get("modifier_families", [])
        ),
        modifier_tiers=tuple(
            ModifierTierDefinition(
                canonical_id=item["canonical_id"],
                modifier_family_id=item["modifier_family_id"],
                tier=item.get("tier"),
                display_name=item.get("display_name"),
                required_item_level=item.get("required_item_level"),
                roll_ranges=tuple(
                    RollValue(
                        label=roll.get("label"),
                        min_value=_decimal_or_none(roll.get("min_value")),
                        max_value=_decimal_or_none(roll.get("max_value")),
                    )
                    for roll in item.get("roll_ranges", [])
                ),
                source_record_key=item.get("source_record_key"),
                source_locator=item.get("source_locator"),
                provenance=tuple(_provenance_from_json(p) for p in item.get("provenance", [])),
                dataset_version=item.get("dataset_version"),
            )
            for item in data.get("modifier_tiers", [])
        ),
        modifier_applicability=tuple(
            ModifierApplicability(
                modifier_id=item["modifier_id"],
                item_class=item.get("item_class"),
                base_restrictions=tuple(item.get("base_restrictions", [])),
                tags_or_conditions=tuple(item.get("tags_or_conditions", [])),
                provenance=tuple(_provenance_from_json(p) for p in item.get("provenance", [])),
            )
            for item in data.get("modifier_applicability", [])
        ),
    )
    validate_normalized_dataset(dataset)
    return dataset


def validate_normalized_dataset(dataset: NormalizedGameDataSet) -> None:
    if not dataset.snapshot.snapshot_id:
        raise ValueError("normalized dataset requires snapshot identity")
    if not dataset.dataset_version:
        raise ValueError("normalized dataset requires dataset_version")
    family_id_list = [family.canonical_id for family in dataset.modifier_families]
    if len(family_id_list) != len(set(family_id_list)):
        raise ValueError("duplicate modifier family canonical_id detected")
    tier_ids = [tier.canonical_id for tier in dataset.modifier_tiers]
    if len(tier_ids) != len(set(tier_ids)):
        raise ValueError("duplicate modifier tier canonical_id detected")
    family_ids = set(family_id_list)
    for tier in dataset.modifier_tiers:
        if tier.modifier_family_id not in family_ids:
            raise ValueError(f"unknown modifier family: {tier.modifier_family_id}")
        if tier.required_item_level is not None and tier.required_item_level < 0:
            raise ValueError("required item level cannot be negative")
        if tier.tier is not None and not tier.tier.isdigit():
            raise ValueError("tier must be numeric when present")
        for roll in tier.roll_ranges:
            if (
                roll.min_value is not None
                and roll.max_value is not None
                and roll.min_value > roll.max_value
            ):
                raise ValueError("roll range min cannot exceed max")
    valid_affixes = set(AffixType)
    for family in dataset.modifier_families:
        if family.affix_type not in valid_affixes:
            raise ValueError("invalid affix type")
        if not family.provenance:
            raise ValueError("modifier family provenance is required")
    for applicability in dataset.modifier_applicability:
        if applicability.modifier_id not in set(tier_ids):
            raise ValueError(f"unknown applicability modifier: {applicability.modifier_id}")
        if not applicability.provenance:
            raise ValueError("modifier applicability provenance is required")


def canonical_family_id(family: str) -> str:
    return f"dc:poe2:modifier-family:{_slug(family)}"


def canonical_modifier_tier_id(record: RawPoe2DbModifierRecord) -> str:
    semantic = "|".join(
        [
            "Path of Exile 2",
            record.domain or "",
            record.family,
            record.generation_type,
            record.tier or "",
            _stat_template(record.stats),
            _range_identity(record.stats),
        ]
    )
    digest = hashlib.sha256(semantic.encode("utf-8")).hexdigest()[:16]
    return f"dc:poe2:modifier-tier:{digest}"


def _raw_record(data: dict[str, Any]) -> RawPoe2DbModifierRecord:
    return RawPoe2DbModifierRecord(
        source_record_key=data.get("source_record_key"),
        source_uri=data["source_uri"],
        retrieved_at=_parse_datetime(data["retrieved_at"]),
        display_name=data["display_name"],
        family=data["family"],
        domain=data.get("domain"),
        generation_type=data["generation_type"],
        required_level=data.get("required_level"),
        tier=data.get("tier"),
        stats=tuple(
            RawPoe2DbStat(
                text=stat["text"],
                min=_decimal_or_none(stat.get("min")),
                max=_decimal_or_none(stat.get("max")),
                scope=stat.get("scope"),
            )
            for stat in data.get("stats", [])
        ),
        spawn_tags={key: int(value) for key, value in data.get("spawn_tags", {}).items()},
        craft_tags=tuple(data.get("craft_tags", [])),
        notes=tuple(data.get("notes", [])),
    )


def _provenance(record: RawPoe2DbModifierRecord, snapshot: GameDataSnapshot) -> DataProvenance:
    return DataProvenance(
        source_id=snapshot.source,
        source_type=SourceType.COMMUNITY,
        source_uri=record.source_uri,
        retrieved_at=record.retrieved_at,
        game_version=snapshot.game_context.game_version if snapshot.game_context else None,
        verification_status=VerificationStatus.NEEDS_VERIFICATION,
        confidence=Confidence(Decimal("0.60"), reasons=("Community source; licensing/source stability needs review.",)),
        notes="source_record_key is an external locator, not a canonical game-data ID",
    )


def _provenance_from_json(data: dict[str, Any]) -> DataProvenance:
    confidence_data = data.get("confidence")
    confidence = None
    if confidence_data:
        confidence = Confidence(
            score=_decimal_or_none(confidence_data.get("score")),
            level=ConfidenceLevel[confidence_data["level"]] if confidence_data.get("level") else None,
            reasons=tuple(confidence_data.get("reasons", [])),
            sample_size=confidence_data.get("sample_size"),
        )
    return DataProvenance(
        source_id=data["source_id"],
        source_type=SourceType[data["source_type"]],
        source_uri=data.get("source_uri"),
        retrieved_at=_parse_datetime(data.get("retrieved_at")),
        game_version=data.get("game_version"),
        league=data.get("league"),
        verification_status=VerificationStatus[data.get("verification_status", "NEEDS_VERIFICATION")],
        confidence=confidence,
        notes=data.get("notes"),
    )


def _dataset_version(snapshot: GameDataSnapshot) -> str:
    hash_part = (snapshot.checksum or hashlib.sha256(snapshot.snapshot_id.encode("utf-8")).hexdigest())[:13]
    date_part = snapshot.retrieved_at.date().isoformat() if snapshot.retrieved_at else "unknown-date"
    game_version = snapshot.game_context.game_version if snapshot.game_context and snapshot.game_context.game_version else "unknown-version"
    return f"{snapshot.source}-{game_version}-{date_part}-{hash_part}"


def _affix_type(value: str) -> AffixType:
    normalized = value.upper()
    if normalized == "PREFIX":
        return AffixType.PREFIX
    if normalized == "SUFFIX":
        return AffixType.SUFFIX
    if normalized == "IMPLICIT":
        return AffixType.IMPLICIT
    raise ValueError(f"invalid affix/generation type: {value}")


def _stat_template(stats: tuple[RawPoe2DbStat, ...]) -> str:
    return " | ".join(stat.text for stat in stats)


def _range_identity(stats: tuple[RawPoe2DbStat, ...]) -> str:
    return "|".join(f"{stat.min or ''}-{stat.max or ''}" for stat in stats)


def _item_class_from_spawn_tag(tag: str) -> str:
    return {"quiver": "Quivers", "gloves": "Gloves"}.get(tag, tag)


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _decimal_or_none(value: Any) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.name
    if hasattr(value, "__dataclass_fields__"):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value
